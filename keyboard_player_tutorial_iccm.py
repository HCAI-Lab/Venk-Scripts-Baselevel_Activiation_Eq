import math
import json
import numpy as np
import gzip
import os
from typing import Sequence
from tqdm import tqdm
import re
import time
import cv2
from moviepy.editor import ImageSequenceClip
import ai2thor
from ai2thor.controller import Controller
import constants_JC as constants 
import WorkingMemory as WM
import requests
from eval_user_tutorial import GameStatus, MAIN_TASK
from flask import Flask, render_template, request
import threading
import sys
import random

# Initialize Flask app
app = Flask(__name__)
printed_logs = []

@app.route('/')
def index():
    return render_template('index.html', logs=printed_logs)

@app.route('/update', methods=['POST'])
def update():
    log_entry = request.form['log']
    printed_logs.append(log_entry)
    return "", 204

def run_flask_app():
    app.run(debug=True, use_reloader=False)


def log_and_print(message, update_index=False):
    print(message)  # Redirect output to Flask server
    try:
        if update_index:
            requests.post('http://127.0.0.1:5001/update', data={'log': f"UPDATE_INDEX::{message}"})
        else:
            requests.post('http://127.0.0.1:5001/update', data={'log': message})
    except requests.exceptions.RequestException as e:
        print(f"Error logging message: {e}")



## Start Flask app in a separate thread
flask_thread = threading.Thread(target=run_flask_app)
flask_thread.daemon = True
flask_thread.start()


actionList = {
    ## Navigation
    "MoveTo": "e",
    # "RotateLeft": "a",
    # "RotateRight": "d",
    "LookUp": "w",
    "LookDown": "s",

    ## Interact action
    "PickupObject": "j",
    "PutObject": "k",
    "OpenObject": "l",
    "CloseObject": ";",
    "ToggleObjectOn": "i",
    "ToggleObjectOff": "o",
    "SliceObject": "p",

    "ObjectState": "q", 
    "GameStatus" : "g", 

    # "QUICK_FINISH": "v", 
}


def assign_unique_ids(env):
    """
    Assign unique IDs to all objects in the scene.
    This function creates a mapping of objectType to sequential IDs (e.g., Drawer_1, Drawer_2).
    """
    unique_id_map = {}
    category_counts = {}  # To keep track of counts for each category
    for obj in env.last_event.metadata["objects"]:
        if obj["objectType"] == "Floor": # Skip objects of type 'Floor'
            continue
        category = obj["objectType"] # Get the object category (type)

        ## Increment the count for this category
        if category not in category_counts:
            category_counts[category] = 0
        category_counts[category] += 1

        ## Assign a unique ID
        unique_id = f"{category}_{category_counts[category]}"
        unique_id_map[obj["objectId"]] = unique_id

    return unique_id_map


def get_seen_objects(event, unique_id_map, exclude_type="Floor"):
    """
    Returns a list of unique IDs for visible objects, excluding those of a specified objectType.
    """
    return [unique_id_map[obj["objectId"]] for obj in event.metadata["objects"] if obj["visible"] and obj["objectType"] != exclude_type]




def log_json(event, elapsed_time_as, elapsed_time_ae, action, result, seen_objects=None, candidate_objects=None, selected_object=None, held_object=None, game_status=None, completed_task=None):
    """
    elapsed_time_as = Action started
    elapsed_time_ae = Action ended
    """
    if seen_objects is None:
        raise ValueError("The 'seen_objects' argument is required but was not provided to 'log_json'.")
    if action == 'Pass':
        action = 'ObjectStateCheck'   

    # Set completed_task to None if it is empty or not provided
    completed_task = None if not completed_task else completed_task

    excluded_keys = {'axisAlignedBoundingBox', 'center', 'size', 'objectOrientedBoundingBox'}
    object_info = {
        obj['objectId']: {k: v for k, v in obj.items() if k not in excluded_keys}
        for obj in event.metadata['objects']
    }

    log = {
        "elapsed_time_as": round(elapsed_time_as, 2),
        "elapsed_time_ae": round(elapsed_time_ae, 2),
        "action": action,
        "result": result,
        "candidate_objects": candidate_objects if candidate_objects else 'None',
        "selected_object": selected_object if selected_object else "None",
        "held_object" : held_object if held_object else "None",
        "object_seen": seen_objects,
        "completed_tasks": completed_task, 
        "game_status": {'metadata': object_info, 'agent': event.metadata['agent']},
    }

    return log


def agent_pos_rot(event):
    agent = {'pos_x': event.metadata['agent']['position']['x']
    ,'pos_z' : event.metadata['agent']['position']['z']
    , 'rotation' : event.metadata['agent']['rotation']['y']
    }

    return agent


def save_json(logs, output_dir, filename="action_logs.json"):
    log_file = os.path.join(output_dir, filename)
    with open(log_file, mode='w') as file:
        json.dump(logs, file, indent=4)


def get_interact_object(env, action, unique_id_map, pickup=None):
    agent_position = env.last_event.metadata['agent']['position']  # Get the agent's current position
    reachable_distance = 2.0  # Define the maximum reachable distance

    ## Get currently held object
    held_object = None
    if env.last_event.metadata.get("inventoryObjects", []):
        held_object = env.last_event.metadata["inventoryObjects"][0]["objectId"]

    ## Prevent SliceObject action if the agent is not holding a knife
    if action == 'SliceObject' and not held_object:
        return "NO_KNIFE", []

    if action == 'SliceObject' and held_object:
        held_object_name = held_object.split('|')[0]
        if action == 'SliceObject' and held_object_name != "Knife":
            return "NO_KNIFE", []

    candidates = []
    interactable_obj_list = []
    
    ## Determine the list of interactable objects based on the action
    if action == 'PickupObject':
        interactable_obj_list = constants.VAL_ACTION_OBJECTS['Pickupable']
    elif action == 'PutObject':
        for recep, objs in constants.VAL_RECEPTACLE_OBJECTS.items():
            if pickup in objs:
                interactable_obj_list.append(recep)
    elif action in ['OpenObject', 'CloseObject']:
        interactable_obj_list = constants.VAL_ACTION_OBJECTS['Openable']
    elif action in ['ToggleObjectOn', 'ToggleObjectOff']:
        interactable_obj_list = constants.VAL_ACTION_OBJECTS['Toggleable']
    elif action == 'SliceObject':
        interactable_obj_list = constants.VAL_ACTION_OBJECTS['Sliceable']

    ## Collect interactable objects with full metadata
    for obj in env.last_event.metadata["objects"]:
        if (obj["objectId"] in env.last_event.instance_masks.keys() and obj["visible"] and obj["objectId"].split('|')[0] in interactable_obj_list):

            if obj["objectId"].startswith('Sink') and not obj["objectId"].endswith('SinkBasin'):
                continue

            if obj["objectId"].startswith('Bathtub') and not obj["objectId"].endswith('BathtubBasin'):
                continue

            ## Exclude currently held objects unless the action is 'StateCheck'
            if action != 'Pass' and obj["objectId"] == held_object: 
                continue

            ## Exclude objects that are already open for the OpenObject action
            if action == 'OpenObject' and obj.get("isOpen", False):
                 continue

            ## Exclude objects that are already closed for the CloseObject action
            if action == 'CloseObject' and not obj.get("isOpen", False):
                continue

            ## Check if the object is openable but not open (for PutObject action)
            if action == 'PutObject' and obj["objectId"].split('|')[0] in constants.VAL_ACTION_OBJECTS['Openable']:
                if not obj.get("isOpen", False):  # Skip if the object is not open
                    continue

            ## Prevent ToggleObjectOn action if the object is already on
            if action == 'ToggleObjectOn' and obj.get("isToggled", False):
                continue

            ## Prevent ToggleObjectOn action if the object is open.
            if (action == 'ToggleObjectOn' and obj.get("isOpen", False) and obj["objectType"] in constants.VAL_ACTION_OBJECTS['Openable']):
                continue

            ## Prevent ToggleObjectOff action if the object is already off
            if action == 'ToggleObjectOff' and not obj.get("isToggled", False):
                continue

            if action == 'SliceObject':
                # slice_pattern = re.compile(r'\bSlice\b', re.IGNORECASE) # Regular expression to match "Slice" in the object ID, case-insensitive
                # if slice_pattern.search(obj["objectId"]) or obj.get("isSliced", False):
                if "Sliced" in obj["objectId"] or not obj.get("sliceable", False):
                    continue  # Skip sliced objects or objects with 'Slice' in their ID

            ## Calculate Euclidean distance
            obj_position = obj["position"]
            distance = math.sqrt(
                (agent_position["x"] - obj_position["x"]) ** 2 +
                (agent_position["y"] - obj_position["y"]) ** 2 +
                (agent_position["z"] - obj_position["z"]) ** 2
            )
            ## Only include objects within the reachable distance
            if distance <= reachable_distance:
                candidates.append((obj, distance))  # Store object and distance as a tuple

    ## Return a distinct value when no candidates are found
    if len(candidates) == 0:
        return "NOT_FOUND", []
 
    ## Draw bounding boxes for candidates on the same frame
    frame = env.last_event.frame.copy()  # Create a writable copy of the frame
    

    if action == 'OpenObject':
        for obj, _ in candidates:
            object_id = obj["objectId"]
            if object_id in env.last_event.instance_detections2D:
                x1, y1, x2, y2 = map(int, env.last_event.instance_detections2D[object_id])
            text = unique_id_map[obj['objectId']] # Get the unique ID text
            text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 1.0, 2)[0]
            text_x = x1 + (x2 - x1 - text_size[0]) // 2
            text_y = y1 + (y2 - y1 + text_size[1]) // 2
            frame = cv2.putText(frame, text, (text_x, text_y), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)  # Unique ID text


    ## Display the frame with bounding boxes
    cv2.imshow("first_view", cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
    cv2.waitKey(1)  # Update the display

    ## Print the list of candidates
    log_and_print('<b>============================================================================</b>')
    log_and_print(f"<b>For '<span style='color:red;'>{action}</span>' - Choose an object by typing the corresponding two-digit index</b>")
    
    ## Format objects as a single line without distance information
    formatted_objects = ", ".join(f"[{index:02d}] '<span style='color:blue;'>{unique_id_map[obj['objectId']]}</span>'" for index, (obj, _) in enumerate(candidates, start=1))
    log_and_print(f"<b>- {formatted_objects}</b>")
    log_and_print("<b>- Press '<span style='color:purple;'>[Space]</span>' key after typing the two-digit index to confirm your selection.</b>")
    log_and_print("<b>- Press '<span style='color:purple;'>[ESC]</span>' key to cancel the action.</b>")

    ## Wait for user input
    selected_index = ""
    while True:
        keystroke = cv2.waitKey(0)

        if keystroke == 27:  # ESC key
            log_and_print(f"<b>  ==> Action '<span style='color:red;'>{action}</span>' cancelled by pressing [ESC].</b>")
            log_and_print('<b>============================================================================</b>')
            log_and_print("UPDATE_INDEX::CLEAR")  # Clear input when ESC is pressed
            return "CANCEL", candidates

        char = chr(keystroke)
        if keystroke in (8, 127):  # Backspace
            selected_index = selected_index[:-1]  # Remove last character
            log_and_print(selected_index or "(empty)", update_index=True)

        elif char.isdigit():
            if len(selected_index) < 2:
                selected_index += char
                log_and_print(selected_index, update_index=True)
            else:
                log_and_print("<b>\n!!! Only two-digit indices are allowed. Press [Space] to confirm or [ESC] to cancel.</b>")

        elif char == ' ':
            if len(selected_index) != 2:
                log_and_print("<b>\n!!! Please enter a valid two-digit index before confirming.</b>")
                continue

            selected_index = int(selected_index)
            if 1 <= selected_index <= len(candidates):
                selected_obj, distance = candidates[selected_index - 1]
                objectId = selected_obj["objectId"]
                object_name = unique_id_map[objectId]

                if action not in ['OpenObject', 'CloseObject', 'PutObject']:
                    x1, y1, x2, y2 = map(int, env.last_event.instance_detections2D[objectId])
                    text_size = cv2.getTextSize(object_name, cv2.FONT_HERSHEY_SIMPLEX, 1.0, 2)[0]
                    text_x = x1 + (x2 - x1 - text_size[0]) // 2
                    text_y = y1 + (y2 - y1 + text_size[1]) // 2
                    frame = cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)  
                    frame = cv2.putText(frame, object_name, (text_x, text_y), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2) 
                    cv2.imshow("first_view", cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
                    cv2.waitKey(1)  # Update the display
                    ## Clear previous messages related to invalid inputs
                    log_and_print("UPDATE_INDEX::CLEAR")  # Clears the input display
                    log_and_print(f"<b> ==> You want to select '<span style='color:blue;'>{object_name}</span>'? (Y/N)</b>")

                else:
                    x1, y1, x2, y2 = map(int, env.last_event.instance_detections2D[objectId])
                    text_size = cv2.getTextSize(object_name, cv2.FONT_HERSHEY_SIMPLEX, 1.0, 2)[0]
                    text_x = x1 + (x2 - x1 - text_size[0]) // 2
                    text_y = y1 + (y2 - y1 + text_size[1]) // 2
                    frame = cv2.putText(frame, object_name, (text_x, text_y), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2) 
                    cv2.imshow("first_view", cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
                    cv2.waitKey(1)  # Update the display
                    ## Clear previous messages related to invalid inputs
                    log_and_print("UPDATE_INDEX::CLEAR")  # Clears the input display
                    log_and_print(f"<b> ==> You want to select '<span style='color:blue;'>{object_name}</span>'? (Y/N)</b>")


                while True:
                    confirmation_key = cv2.waitKey(0)
                    confirmation_char = chr(confirmation_key).lower()
                    if confirmation_char == 'y':
                        log_and_print(f"<b> ==> Select: <span style='color:blue;'>{object_name}</span> </b>")
                        log_and_print('<b>============================================================================</b>')
                        return objectId, candidates
                    elif confirmation_char == 'n':
                        log_and_print(f"<b>  ==> Action cancelled by pressing [N].</b>")
                        log_and_print('<b>============================================================================</b>')
                        return "CANCEL", candidates
            else:
                log_and_print("UPDATE_INDEX::CLEAR")  # Clear previous input
                log_and_print("<b>!!! Invalid input. Please press a valid two-digit index !!!</b>")
                selected_index = ""
        else:
            continue



def select_destination(env, locations, unique_id_map):
    log_and_print('<b>============================================================================</b>')
    log_and_print("<b>Select a destination by typing the corresponding two-digit index</b>")
    
    formatted_locations = ", ".join(f"[{index:02d}] '<span style='color:blue;'>{key}</span>'" for index, key in enumerate(locations.keys(), start=1))
    log_and_print(f"<b>- {formatted_locations}</b>")
    log_and_print("<b>- Press '<span style='color:purple;'>[Space]</span>' key after typing the two-digit index to confirm your selection.</b>")
    log_and_print("<b>- Press '<span style='color:purple;'>[ESC]</span>' key to cancel the action.</b>")
    
    selected_index = ""
    while True:
        keystroke = cv2.waitKey(0)
        if keystroke == 27:  # ESC key
            log_and_print(f"<b>  ==> Destination selection cancelled by pressing [ESC].</b>")
            log_and_print('<b>============================================================================</b>')
            return "CANCEL"
        
        char = chr(keystroke)
        if keystroke in (8, 127):  # Backspace
            selected_index = selected_index[:-1]
            log_and_print(selected_index or "(empty)", update_index=True)
        elif char.isdigit():
            if len(selected_index) < 2:
                selected_index += char
                log_and_print(selected_index, update_index=True)
            else:
                log_and_print("<b>!!! Only two-digit indices are allowed. Press [Space] to confirm or [ESC] to cancel.</b>")
        elif char == ' ':
            if len(selected_index) != 2:
                log_and_print("<b>!!! Please enter a valid two-digit index before confirming.</b>")
                continue

            selected_index = int(selected_index)
            if 1 <= selected_index <= len(locations):
                selected_key = list(locations.keys())[selected_index - 1]
                log_and_print("UPDATE_INDEX::CLEAR")  # Clear the index display before confirmation
                log_and_print(f"<b> ==> You want to move to '<span style='color:blue;'>{selected_key}</span>'? (Y/N)</b>")
                
                while True:
                    confirmation_key = cv2.waitKey(0)
                    confirmation_char = chr(confirmation_key).lower()
                    if confirmation_char == 'y':
                        destination = locations[selected_key]
                        log_and_print(f"<b> ==> Moving to: <span style='color:blue;'>{selected_key}</span> </b>")
                        log_and_print('<b>============================================================================</b>')
                        return destination
                    elif confirmation_char == 'n':
                        log_and_print(f"<b>  ==> Action cancelled by pressing [N].</b>")
                        log_and_print('<b>============================================================================</b>')
                        return "CANCEL"
            else:
                log_and_print("UPDATE_INDEX::CLEAR")  # Clear previous input
                log_and_print("<b>!!! Invalid input. Please press a valid two-digit index !!!</b>")
                selected_index = ""
        else:
            continue



def keyboard_play(env, first_view_frames, is_rotate, rotate_per_frame):
    ## use keyboard control agent
    log_and_print(f"<b>=</b>" * 70)
    log_and_print(f"<b>! WELCOME TO THE HOUSEHOLD TASK TUTORIAL !</b>")
    log_and_print(f" -- You will be asked to complete 5 household tasks in order.")
    log_and_print(f" -- Each task consists of sub-tasks.")
    log_and_print(f" -- Sub-tasks of each task have to be completed to complete the corresponding task.")
    log_and_print(f" -- Please press 'Q' to check object states (i.e., its capability or current states)")
    log_and_print(f" -- Please press 'G' to check the current game status (i.e., Task completion status)")
    log_and_print(f" -- Please try a different location if 'PutObject' action fails.")
    log_and_print(f" -- A task will be completed only if you do it correctly (i.e. correct location).")
    log_and_print(f" -- The game will be finished (submitted) right away if all the taskes are completed when 'G' is pressed.")
    log_and_print(f"<b>=</b>" * 70)

    logs = {}

    main_task_completion = False

    # Create a blank screen and wait for "t" key to start
    frame_height, frame_width = 1600, 1600  # Adjust based on your window size
    blank_frame = np.zeros((frame_height, frame_width, 3), dtype=np.uint8)
    cv2.putText(blank_frame, "Press 'T' to start the game", 
                (frame_width // 4, frame_height // 2),
                cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 3, cv2.LINE_AA)

    while True:
        cv2.imshow("first_view", blank_frame)
        if cv2.waitKey(1) & 0xFF == ord('t'):
            break

    # Once 't' is pressed, show the initial environment frame

    first_view_frame = env.last_event.frame
    cv2.imshow("first_view", cv2.cvtColor(first_view_frame, cv2.COLOR_RGB2BGR))

    unique_id_map = assign_unique_ids(env)

    start_time = time.time()  # Record the start time

    ## Initial state ############################################################
    event = env.step(action="Pass")
    seen_objects = get_seen_objects(event, unique_id_map)
    reachable_distance =  2.0  # Define the maximum reachable distance


    log_and_print(f"> t={0:03d}({0.00}s)|BEGIN|")
    logs = {}
    logs[0] = log_json(event, 0, 0, None, "BEGIN", seen_objects)

    completed_tasks = set()
    situation_board = set()

    time_frame = 1
    while True: 
        keystroke = cv2.waitKey(0)

        # ## Finish the game ############################################################
        # if keystroke == ord(actionList["QUICK_FINISH"]):
        #     event = env.last_event
        #     env.stop()
        #     cv2.destroyAllWindows()
        #     return False, False

        ## CHECK GAME STATUS ############################################################
        if keystroke == ord(actionList["GameStatus"]):
            event = env.last_event
            elapsed_time = time.time() - start_time 
            game_status_data = {
                unique_id_map[obj['objectId']]: {
                    'objectId': obj['objectId'],
                    'objectType': obj['objectType'],
                    # 'parentReceptacles': obj['parentReceptacles'][-1] if obj.get('parentReceptacles') and obj['parentReceptacles'][-1] is not None else None,
                    'parentReceptacles': obj['parentReceptacles'],
                    'temperature': obj['temperature'],
                    'isCooked': obj['isCooked'],
                    'isDirty': obj['isDirty'],
                    'isSliced': obj['isSliced'],
                    'isPickedUp': obj['isPickedUp'],
                    'isToggled': obj['isToggled'],
                    'isOpen': obj['isOpen'],
                    'assetId': obj['assetId']
                }
                for obj in event.metadata['objects'] if obj['objectId'] in unique_id_map
            }
            ## Walk through tutorials
            ## Define a set to track permanently completed tasks
            game_status_evaluator = GameStatus(game_status_data, MAIN_TASK)
            all_completed, report = game_status_evaluator.evaluate_task_completion()
            num_total_tasks = len(report)
            num_completed_tasks = sum(1 for details in report.values() if details['completed'])
            num_incomplete_tasks = num_total_tasks - num_completed_tasks

            log_and_print(f"<b>{'=' * 70}</b>")
            ## Track completed tasks in the situation board
            for task, details in report.items():
                if details['completed']: 
                    situation_board.add(task)  # Add completed task to the board

            log_and_print(f"<b>* [GAME STATUS CHECK] Current Game status = {len(situation_board)} out of {num_total_tasks} tasks were done!</b>")
            if len(situation_board) == num_total_tasks:
                log_and_print(f"<b>* All the main tasks were completed!</b>")
                log_and_print("-" * 70)
                log_and_print(f"<b>************************** END THE TUTORIAL **************************</b>")

                held_obj_name = unique_id_map[held_object[0]["objectId"]] if (held_object := env.last_event.metadata.get("inventoryObjects", [])) else None
                elapsed_time = time.time() - start_time  
                seen_objects = get_seen_objects(event, unique_id_map)
                logs[time_frame] = log_json(event, elapsed_time, elapsed_time, "END_TUTORIAL", "SUCCESS", seen_objects, None, None, held_obj_name, completed_task=list(situation_board))

                all_completed = True
                env.stop()
                cv2.destroyAllWindows()
                break
            else:
                ## Find the first incomplete task based on situation board
                for idx, (task, details) in enumerate(report.items(), start=1):
                    if task in situation_board:
                        continue  # Skip tasks already marked as completed
                    
                    ## Display the first incomplete task
                    log_and_print(f"<b> * Task {idx}: '<span style='color:green;'>{task}</span>' | "
                                  f"Completed: <span style='color:red;'>{details['completed']}</span> & "
                                  f"Conditions Met: <span style='color:red;'>{details['completed_conditions']}/{details['total_conditions']}</span> ")

                    for sub_idx, sub_task_desc in enumerate(details.get('all_subtasks', []), start=1):
                        completion_status = "True" if sub_task_desc in details.get('completed_texts', []) else "False"
                        color = "green" if completion_status == "True" else "red"
                        log_and_print(f" - Sub-task {idx}-{sub_idx}: \"{sub_task_desc}\" | Completed: <span style='color:{color};'>{completion_status}</span>")

                    break 

            log_and_print(f"<b>{'=' * 70}</b>")
            held_obj_name = unique_id_map[held_object[0]["objectId"]] if (held_object := env.last_event.metadata.get("inventoryObjects", [])) else None
            elapsed_time = time.time() - start_time  
            seen_objects = get_seen_objects(event, unique_id_map)
            logs[time_frame] = log_json(event, elapsed_time, elapsed_time, "GameStatusCheck", "SUCCESS", seen_objects, None, None, held_obj_name, completed_task=list(situation_board))
            time_frame += 1

            continue      


        ## Check Object State (Modified) ############################################################################################################################
        elif keystroke == ord(actionList["ObjectState"]):
            """
            Check the objects' state without executing a keyboard action (i.e., No need to press ESC to cancel the action)
            toggleable, cookable, slicable, openable, heatable = constants.VAL_ACTION_OBJECTS['Heatable'], coolable = constants.VAL_ACTION_OBJECTS['Ceatable']
            """
            action = "CheckObjectState"
            event = env.last_event
            held_object_id = held_object[0]["objectId"] if (held_object := event.metadata.get("inventoryObjects", [])) else None
            held_obj_name = unique_id_map[held_object_id] if held_object_id else "None"

            interactable_obj_list  = list(constants.CHANGABLE_OBJECTS)

            ## Collect interactable objects with full metadata
            frame = env.last_event.frame.copy() 

            objects_inView = [obj["objectId"] for obj in event.metadata["objects"] if obj["visible"] and obj["objectType"] != "Floor"]

            # for obj_id in objects_inView:
            #     if re.search(r'Sliced', obj_id, re.IGNORECASE):
            #         continue  # Skip to the next object
            #     object_name = unique_id_map[obj_id]
            #     x1, y1, x2, y2 = map(int, env.last_event.instance_detections2D[obj_id])
            #     text_size = cv2.getTextSize(object_name, cv2.FONT_HERSHEY_SIMPLEX, 1.0, 2)[0]
            #     text_x = x1 + (x2 - x1 - text_size[0]) // 2
            #     text_y = y1 + (y2 - y1 + text_size[1]) // 2
            #     if re.match(r'.*Counter.*', obj_id, re.IGNORECASE):
            #         frame = cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)  
            #         frame = cv2.putText(frame, object_name, (text_x, text_y), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 0, 0), 2) 
            #     else:
            #         frame = cv2.putText(frame, object_name, (text_x, text_y), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2) 
            
            # Group sliced objects based on their base names
            sliced_objects = [obj_id for obj_id in objects_inView if re.match(r'.*Sliced.*', obj_id, re.IGNORECASE)]
            grouped_sliced_objects = {}

            # Group sliced objects based on their base name (e.g. 'AppleSliced_1' -> 'Apple')
            for obj_id in sliced_objects:
                base_name = re.sub(r'Sliced_\d+', '', obj_id)  # Remove the sliced suffix (e.g., 'AppleSliced_1' -> 'Apple')
                if base_name not in grouped_sliced_objects:
                    grouped_sliced_objects[base_name] = []
                grouped_sliced_objects[base_name].append(obj_id)

            # Select one random sliced object from each base group
            selected_sliced = {base: random.choice(objects) for base, objects in grouped_sliced_objects.items()}

            # Keep only the selected sliced objects and remove the rest
            objects_inView = [obj for obj in objects_inView if obj not in sliced_objects or obj in selected_sliced.values()]

            # Process remaining objects in view (including one from each sliced type)
            for obj_id in objects_inView:
                object_name = unique_id_map[obj_id]
                x1, y1, x2, y2 = map(int, env.last_event.instance_detections2D[obj_id])
                text_size = cv2.getTextSize(object_name, cv2.FONT_HERSHEY_SIMPLEX, 1.0, 2)[0]
                text_x = x1 + (x2 - x1 - text_size[0]) // 2
                text_y = y1 + (y2 - y1 + text_size[1]) // 2

                if re.match(r'.*Counter.*', obj_id, re.IGNORECASE):
                    # Highlight objects containing 'Counter'
                    frame = cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)  
                    frame = cv2.putText(frame, object_name, (text_x, text_y), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 0, 0), 2) 
                elif obj_id in selected_sliced.values():
                    # Highlight the randomly selected 'Sliced' object from each group
                    frame = cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)  # Red rectangle
                    frame = cv2.putText(frame, object_name, (text_x, text_y), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)
                else:
                    # Default text for other objects
                    frame = cv2.putText(frame, object_name, (text_x, text_y), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2) 

            # Display the updated frame
            cv2.imshow("first_view", cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
            cv2.waitKey(1)  # Update the display



            ## Collect interactable objects with full metadata
            candidates = []
            agent_position = event.metadata['agent']['position']
            for obj in env.last_event.metadata["objects"]:
                if (obj["objectId"] in env.last_event.instance_masks.keys() and obj["visible"] and obj["objectId"].split('|')[0] in interactable_obj_list):
                    if obj["objectId"].startswith('Sink') and not obj["objectId"].endswith('SinkBasin'):
                        continue
                    if obj["objectId"].startswith('Bathtub') and not obj["objectId"].endswith('BathtubBasin'):
                        continue

                    if (obj.get('cookable') == False and obj.get('objectType') not in constants.VAL_ACTION_OBJECTS['Heatable'] and obj.get('objectType') not in constants.VAL_ACTION_OBJECTS['Coolable']
                        and obj.get('dirtyable') == False and obj.get('sliceable') == False and obj.get('toggleable') == False ):
                        continue

                    ## Calculate Euclidean distance
                    obj_position = obj["position"]
                    distance = math.sqrt(
                        (agent_position["x"] - obj_position["x"]) ** 2 +
                        (agent_position["y"] - obj_position["y"]) ** 2 +
                        (agent_position["z"] - obj_position["z"]) ** 2
                    )
                    ## Only include objects within the reachable distance
                    if distance <= reachable_distance:
                        candidates.append((obj, distance))  # Store object and distance as a tuple

            elapsed_time = time.time() - start_time 

            ## Return a distinct value when no candidates are found
            if not candidates:
                log_and_print(f"> t={time_frame:03d}({elapsed_time:.2f}s)|<span style='color:red;'>FAIL</span>| action = CheckObjectState  <span style='color: red;'>&lt;! WARNING: No objects capable of state changes found within reachable distance in view !&gt;</span>")
                logs[time_frame] = log_json(event, elapsed_time, elapsed_time, action, "FAIL", get_seen_objects(event, unique_id_map), None, None, held_obj_name, completed_task=list(situation_board))
                time_frame += 1
            else:
                log_and_print(f"<b>{'=' * 70}</b>")
                log_and_print(f"<b>* [OBJECT STATE CHECK] Check the state of each object in view!</b>")

                for index, (obj, distance) in enumerate(candidates, start=1):  # Start indices at 1
                    obj_capability = []
                    obj_details = []

                    if obj.get('objectType') in constants.VAL_ACTION_OBJECTS['Heatable'] or obj.get('objectType') in constants.VAL_ACTION_OBJECTS['Coolable']:
                        temp_status = obj.get('temperature', 'Unknown')
                        obj_details.append(f"{temp_status}")

                        if obj.get('objectType') in constants.VAL_ACTION_OBJECTS['Heatable'] and obj.get('objectType') in constants.VAL_ACTION_OBJECTS['Coolable']:
                            obj_capability.append(f"Heatable & Coolable")
                        else:
                            if obj.get('objectType') in constants.VAL_ACTION_OBJECTS['Heatable']:
                                obj_capability.append(f"Heatable")
                            else:
                                obj_capability.append(f"Coolable")

                    if obj.get('cookable', False):
                        cooked_status = "Cooked" if obj.get('isCooked') else "NotCooked"
                        obj_details.append(f"{cooked_status}")
                        obj_capability.append(f"Cookable")

                    if obj.get('dirtyable', False):
                        dirty_status = "Dirty" if obj.get('isDirty') else "Clean"
                        obj_details.append(f"{dirty_status}")
                        obj_capability.append(f"Cleanable")

                    if obj.get('sliceable', False):
                        sliced_status = "Sliced" if obj.get('isSliced') else "NotSliced"
                        obj_details.append(f"{sliced_status}")
                        obj_capability.append(f"Sliceable")

                    if obj.get('toggleable', False):
                        toggle_status = "Toggled" if obj.get('isToggled') else "NotToggled"
                        obj_details.append(f"{toggle_status}")
                        obj_capability.append(f"Toggleable")

                    if obj_details:
                        log_and_print(f"<b> - <span style='color:blue;'>{unique_id_map[obj['objectId']]}</span></b> ({' & '.join(obj_capability)}) - <b>State(s):</b> {' | '.join(obj_details)}</b>")

            log_and_print(f"<b>{'=' * 70}</b>")

            # log_and_print(f"> t={time_frame:03d}({elapsed_time:.2f}s)|SUCCESS| action = CheckObjectState")
            # logs[time_frame] = log_json(event, elapsed_time, action, "SUCCESS", get_seen_objects(event, unique_id_map), None, held_obj_name, completed_task=list(completed_tasks) if completed_tasks else None)
            logs[time_frame] = log_json(event, elapsed_time, elapsed_time, action, "SUCCESS", get_seen_objects(event, unique_id_map), candidates, None, held_obj_name, completed_task=list(situation_board))
            time_frame += 1

        ## MoveTo ########################################################################################################################
        LOCATIONS = {
            "Sink":{ "action": "TeleportFull", "position":{"x": -3.0, 'y':0.9, "z": 3.5}, "rotation": {"x": 0, 'y':270, "z": 0}, "horizon": 30 ,'standing': True}
            , "Stove": {"action": "TeleportFull", "position":{"x": -2.75, 'y':0.9, "z": 3.00}, "rotation": {"x": 0, 'y':180, "z": 0}, "horizon": 30 ,'standing': True}
            , "Fridge": {"action": "TeleportFull", "position":{"x": -1.5, 'y':0.9, "z": 3.75}, "rotation": {"x": 0, 'y':90, "z": 0}, "horizon": 30 ,'standing': True}
            , "Door": {"action": "TeleportFull", "position":{"x": -0.75, 'y':0.9, "z": 1.0}, "rotation": {"x": 0, 'y':270, "z": 0}, "horizon": 30 ,'standing': True}
            , "CoffeeMachine": {"action": "TeleportFull", "position":{"x": -1.5, 'y':0.9, "z": 5.75}, "rotation": {"x": 0, 'y':90, "z": 0}, "horizon": 30 ,'standing': True}
            , "CounterTop": {"action": "TeleportFull", "position":{"x": -3.5, 'y':0.9, "z": 4.25}, "rotation": {"x": 0, 'y':0, "z": 0}, "horizon": 30 ,'standing': True}
        }

        if keystroke == ord(actionList["MoveTo"]):
            action = "MoveTo"
            elapsed_time = time.time() - start_time 
            destination = select_destination(env, LOCATIONS, unique_id_map)
            held_obj_name = unique_id_map[held_object[0]["objectId"]] if (held_object := env.last_event.metadata.get("inventoryObjects", [])) else None
            if destination == "CANCEL":
                event = env.last_event
                elapsed_time2 = time.time() - start_time 
                log_and_print(f"> t={time_frame:03d}({elapsed_time:.2f}s-{elapsed_time2:.2f}s)|CANCEL| action = {action}")
                logs[time_frame] = log_json(event, elapsed_time, elapsed_time2, action, "CANCEL", get_seen_objects(event, unique_id_map), None, None, held_obj_name, completed_task=list(situation_board))
                time_frame += 1
                continue  # Skip the rest of the loop if the action was canceled

            event = env.step(destination)
            elapsed_time2 = time.time() - start_time
            seen_objects = get_seen_objects(event, unique_id_map)
            if event.metadata['lastActionSuccess']:
                # log_and_print(f"> t={time_frame:03d}({elapsed_time:.2f}s)|SUCCESS| action = {action}")
                agent_info = agent_pos_rot(event)
                log_and_print(f"> t={time_frame:03d}({elapsed_time:.2f}s-{elapsed_time2:.2f}s)|SUCCESS| action = {action} & {agent_info}")
                logs[time_frame] = log_json(event, elapsed_time, elapsed_time2, action, "SUCCESS", seen_objects, None, None, held_obj_name, completed_task=list(situation_board))
            else:
                event = env.step(action="Pass")
                openable_objects = [obj for obj in event.metadata['objects'] if obj.get('openable', False) and obj.get('isOpen', False)]
                for obj in openable_objects:
                    object_id = obj['objectId']
                    env.step(action="CloseObject", objectId=object_id, forceAction=True)
                event = env.step(destination)    
                # cv2.imshow("first_view", cv2.cvtColor(env.last_event.frame, cv2.COLOR_RGB2BGR))
                # cv2.waitKey(1)  # Update the display    
                log_and_print(f"> t={time_frame:03d}({elapsed_time:.2f}s-{elapsed_time2:.2f}s)|SUCCESS| action = {action} & {agent_info}")
                logs[time_frame] = log_json(event, elapsed_time, elapsed_time2, action, "SUCCESS", seen_objects, None, None, held_obj_name, completed_task=list(situation_board))
                # raise ValueError(f"Debugging is required for '{action}'!")
            time_frame += 1


        elif keystroke == ord(actionList["LookUp"]): 
            action = "LookUp"
            if env.last_event.metadata["agent"]["cameraHorizon"] > -30:
                event = env.step(action=action)
                elapsed_time = time.time() - start_time  
                held_obj_name = unique_id_map[held_object[0]["objectId"]] if (held_object := env.last_event.metadata.get("inventoryObjects", [])) else None
                seen_objects = get_seen_objects(event, unique_id_map)
                log_and_print(f"> t={time_frame:03d}({elapsed_time:.2f}s)|SUCCESS| action = {action}")
                logs[time_frame] = log_json(event, elapsed_time, elapsed_time, action, "SUCCESS", seen_objects, None, None, held_obj_name, completed_task=list(situation_board))
            else:
                event = env.last_event
                elapsed_time = time.time() - start_time  
                held_obj_name = unique_id_map[held_object[0]["objectId"]] if (held_object := env.last_event.metadata.get("inventoryObjects", [])) else None
                seen_objects = get_seen_objects(event, unique_id_map)
                log_and_print(f"> t={time_frame:03d}({elapsed_time:.2f}s)|<span style='color:red;'>FAIL</span>| action = {action}  <span style='color: red;'>&lt;!!!WARNING: CANNOT LOOK UP FURTHER!!!&gt;</span>")
                logs[time_frame] = log_json(event, elapsed_time, elapsed_time, action, "FAIL", seen_objects, None, None, held_obj_name, completed_task=list(situation_board))
            time_frame += 1
 

        elif keystroke == ord(actionList["LookDown"]): 
            action = "LookDown"
            if env.last_event.metadata["agent"]["cameraHorizon"] < 30:
                event = env.step(action=action)
                held_obj_name = unique_id_map[held_object[0]["objectId"]] if (held_object := env.last_event.metadata.get("inventoryObjects", [])) else None
                elapsed_time = time.time() - start_time  
                seen_objects = get_seen_objects(event, unique_id_map)
                log_and_print(f"> t={time_frame:03d}({elapsed_time:.2f}s)|SUCCESS| action = {action}")
                logs[time_frame] = log_json(event, elapsed_time, elapsed_time, action, "SUCCESS", seen_objects, None, None, held_obj_name, completed_task=list(situation_board))
            else:
                event = env.last_event
                held_obj_name = unique_id_map[held_object[0]["objectId"]] if (held_object := env.last_event.metadata.get("inventoryObjects", [])) else None
                elapsed_time = time.time() - start_time
                seen_objects = get_seen_objects(event, unique_id_map)
                log_and_print(f"> t={time_frame:03d}({elapsed_time:.2f}s)|<span style='color:red;'>FAIL</span>| action = {action}  <span style='color: red;'>&lt;!!!WARNING: CANNOT LOOK DOWN FURTHER!!!&gt;</span>")
                logs[time_frame] = log_json(event, elapsed_time, elapsed_time, action, "FAIL", seen_objects, None, None, held_obj_name, completed_task=list(situation_board))
            time_frame += 1


        ## INTERACTION = PickupObject ########################################################################################################################
        elif keystroke == ord(actionList["PickupObject"]):
            action = "PickupObject"

            ## Check if the agent is already holding an object
            event = env.last_event
            held_obj_name = unique_id_map[held_object[0]["objectId"]] if (held_object := env.last_event.metadata.get("inventoryObjects", [])) else None
            held_object = env.last_event.metadata.get("inventoryObjects", [])
            elapsed_time = time.time() - start_time
            if held_object:
                holding_object = held_object[0]["objectId"]  # Assuming the agent can hold one obsject at a time
                held_obj_name = unique_id_map[holding_object]
                log_and_print(f"> t={time_frame:03d}({elapsed_time:.2f}s)|<span style='color:red;'>FAIL</span>| action = {action}  <span style='color: red;'>&lt;!!!WARNING: You are holding {held_obj_name}!!!&gt;</span>")
                logs[time_frame] = log_json(event, elapsed_time, elapsed_time, action, "FAIL", get_seen_objects(event, unique_id_map), None, None, held_obj_name, completed_task=list(situation_board))
                time_frame += 1
                continue  # Skip the rest of the loop

            ## Execute the PickupObject action if no object is held
            objectId, candidates = get_interact_object(env, action, unique_id_map)
            if objectId == "NOT_FOUND":
                log_and_print(f"> t={time_frame:03d}({elapsed_time:.2f}s)|<span style='color:red;'>FAIL</span>| action = {action}  <span style='color: red;'>&lt;!!!WARNING: No valid interactable objects found within reachable distance in view!!!&gt;</span>")
                logs[time_frame] = log_json(event, elapsed_time, elapsed_time, action, "FAIL", get_seen_objects(event, unique_id_map), None , None, held_obj_name, completed_task=list(situation_board))
                time_frame += 1
                continue  # Skip the rest of the loop if no object was found

            if objectId == "CANCEL":
                elapsed_time2 = time.time() - start_time
                log_and_print(f"> t={time_frame:03d}({elapsed_time:.2f}s-{elapsed_time2:.2f}s)|CANCEL| action = {action}")
                logs[time_frame] = log_json(event, elapsed_time, elapsed_time2, action, "CANCEL", get_seen_objects(event, unique_id_map), candidates, None, held_obj_name, completed_task=list(situation_board))
                time_frame += 1
                continue  # Skip the rest of the loop if the action was canceled

            ## Attempt to pick up the selected object
            # pickup = objectId.split('|')[0]
            event = env.step(action=action, objectId=objectId, forceAction=True)
            elapsed_time2 = time.time() - start_time
            obj_name = unique_id_map[objectId]
            if event.metadata['lastActionSuccess']:
                log_and_print(f"> t={time_frame:03d}({elapsed_time:.2f}s-{elapsed_time2:.2f}s)|SUCCESS| action = {action} & object = {obj_name}")
                logs[time_frame] = log_json(event, elapsed_time, elapsed_time2, action, "SUCCESS", get_seen_objects(event, unique_id_map), candidates, obj_name, held_obj_name, completed_task=list(situation_board))
            else:
                raise ValueError(f"Debugging is required for '{action}'!")
            time_frame += 1


        ## Interaction = PutObject ############################################################################################   
        elif keystroke == ord(actionList["PutObject"]):
            action = "PutObject"
            held_obj_name = unique_id_map[held_object[0]["objectId"]] if (held_object := env.last_event.metadata.get("inventoryObjects", [])) else None
            held_object = env.last_event.metadata.get("inventoryObjects", [])
            event = env.last_event
            elapsed_time = time.time() - start_time
            if held_object:
                ## Extract the objectId of the currently held object
                holding_object_id = held_object[0]["objectId"]  # Assuming the agent can hold only one object
                obj_name = unique_id_map[holding_object_id]
                holding_object_type = re.match(r"^[A-Za-z]+", obj_name).group()
                objectId, candidates = get_interact_object(env, action, unique_id_map, pickup=holding_object_type)
                if objectId == "CANCEL":  # User pressed '0' to cancel the action
                    elapsed_time2 = time.time() - start_time
                    log_and_print(f"> t={time_frame:03d}({elapsed_time:.2f}s-{elapsed_time2:.2f}s)|CANCEL| action = PutObject")
                    logs[time_frame] = log_json(event, elapsed_time, elapsed_time2, action, "CANCEL", get_seen_objects(event, unique_id_map), candidates, None, held_obj_name, completed_task=list(situation_board))

                    time_frame += 1
                    continue

                if objectId == "NOT_FOUND":
                    elapsed_time = time.time() - start_time
                    log_and_print(f"> t={time_frame:03d}({elapsed_time:.2f}s)|<span style='color:red;'>FAIL</span>| action = {action}  <span style='color: red;'>&lt;!!!WARNING: No valid interactable receptacles found within reachable distance in view!!!&gt;</span>")
                    logs[time_frame] = log_json(event, elapsed_time, elapsed_time, action, "FAIL", get_seen_objects(event, unique_id_map), None, None, held_obj_name, completed_task=list(situation_board))
                    time_frame += 1
                    continue

                receptacle_name = unique_id_map[objectId]
                receptacle_type = re.match(r"^[A-Za-z]+", receptacle_name).group()
                event = env.step(action=action, objectId=objectId, forceAction=receptacle_type in {"SinkBasin", "Drawer", "Cabinet"})
                elapsed_time2 = time.time() - start_time
                if event.metadata['lastActionSuccess']:
                    log_and_print(f"> t={time_frame:03d}({elapsed_time:.2f}s-{elapsed_time2:.2f}s)|SUCCESS| action = PutObject ({obj_name} -> {receptacle_name})")
                    logs[time_frame] = log_json(event, elapsed_time, elapsed_time2, action, "SUCCESS", get_seen_objects(event, unique_id_map), candidates, receptacle_name, held_obj_name, completed_task=list(situation_board))
                    
                    ## Update the receptacle's 'isDirty' state in the metadata
                    for obj in event.metadata['objects']:
                        if obj['objectId'] == objectId and obj.get('dirtyable', False):
                             env.step(action="DirtyObject", objectId=objectId, forceAction=True)

                else:
                    event = env.step(action="GetSpawnCoordinatesAboveReceptacle", objectId=objectId, anywhere=False)
                    new_loc = {
                        'x': np.round(np.mean([item['x'] for item in event.metadata["actionReturn"]]), 2),
                        'y': np.round(np.mean([item['y'] for item in event.metadata["actionReturn"]]), 2),
                        'z': np.round(np.mean([item['z'] for item in event.metadata["actionReturn"]]), 2)
                    }
                    event = env.step(action="PlaceObjectAtPoint", objectId=holding_object_id, position=new_loc)
                    if event.metadata['lastActionSuccess']:
                        log_and_print(f"> t={time_frame:03d}({elapsed_time:.2f}s-{elapsed_time2:.2f}s)|SUCCESS| action = PutObject ({obj_name} -> {receptacle_name})")
                        logs[time_frame] = log_json(event, elapsed_time, elapsed_time2, "PutObject", "SUCCESS", get_seen_objects(event, unique_id_map), candidates, receptacle_name, held_obj_name, completed_task=list(situation_board))
                        ## Update the receptacle's 'isDirty' state in the metadata
                        for obj in event.metadata['objects']:
                            if obj['objectId'] == objectId and obj.get('dirtyable', False):
                                env.step(action="DirtyObject", objectId=objectId, forceAction=True)
                    else:
                        log_and_print(f"> t={time_frame:03d}({elapsed_time:.2f}s-{elapsed_time2:.2f}s)|<span style='color:red;'>FAIL</span>| action = {action}  <span style='color: red;'>&lt;!!!WARNING: Action failed!!!&gt;</span>")
                        # logs[time_frame] = log_json(elapsed_time, "PutObject", "FAIL", get_seen_objects(event, unique_id_map), obj_name, held_obj_name)
                        logs[time_frame] = log_json(event, elapsed_time, elapsed_time2, "PutObject", "FAIL", get_seen_objects(event, unique_id_map), candidates, receptacle_name, held_obj_name, completed_task=list(situation_board))

                time_frame += 1
            else:
                objectId, candidates = get_interact_object(env, action, unique_id_map)
                log_and_print(f"> t={time_frame:03d}({elapsed_time:.2f}s)|<span style='color:red;'>FAIL</span>| action = PutObject  <!!!WARNING: No object is being held!!!>")
                logs[time_frame] = log_json(event, elapsed_time, elapsed_time, "PutObject", "FAIL", get_seen_objects(event, unique_id_map), candidates, None, held_obj_name, completed_task=list(situation_board))
                time_frame += 1


        ## Interaction = OpenObject ############################################################################################  
        elif keystroke == ord(actionList["OpenObject"]):
            action="OpenObject"
            held_obj_name = unique_id_map[held_object[0]["objectId"]] if (held_object := env.last_event.metadata.get("inventoryObjects", [])) else None
            held_object = env.last_event.metadata.get("inventoryObjects", [])
            event = env.last_event
            elapsed_time = time.time() - start_time
            objectId, candidates = get_interact_object(env, action, unique_id_map)
            if objectId == "NOT_FOUND":
                log_and_print(f"> t={time_frame:03d}({elapsed_time:.2f}s)|<span style='color:red;'>FAIL</span>| action = {action}  <span style='color: red;'>&lt;!!!WARNING: No valid interactable objects found within reachable distance in view!!!!&gt;</span>")
                logs[time_frame] = log_json(event, elapsed_time, elapsed_time, action, "FAIL", get_seen_objects(event, unique_id_map), None, None, held_obj_name, completed_task=list(situation_board))
                time_frame += 1
                continue  # Skip the rest of the loop if no object was found
            
            if objectId == "CANCEL":
                elapsed_time2 = time.time() - start_time
                log_and_print(f"> t={time_frame:03d}({elapsed_time:.2f}s-{elapsed_time2:.2f}s)|CANCEL| action = {action}")
                logs[time_frame] = log_json(event, elapsed_time, elapsed_time2, action, "CANCEL", get_seen_objects(event, unique_id_map), candidates, None, held_obj_name, completed_task=list(situation_board))
                time_frame += 1
                continue  # Skip the rest of the loop if the action was canceled

            target = objectId.split('|')[0]
            event = env.step(action=action, objectId=objectId)
            obj_name = unique_id_map[objectId]
            elapsed_time2 = time.time() - start_time
            if event.metadata['lastActionSuccess']:
                log_and_print(f"> t={time_frame:03d}({elapsed_time:.2f}s-{elapsed_time2:.2f}s)|SUCCESS| action = OpenObject & object = {obj_name}")
                logs[time_frame] = log_json(event, elapsed_time, elapsed_time2, action, "SUCCESS", get_seen_objects(event, unique_id_map), candidates, obj_name, held_obj_name, completed_task=list(situation_board))
            else:
                raise ValueError(f"Debugging required for {action}!")
            time_frame += 1


        ## Interaction = CloseObject ############################################################################################  
        elif keystroke == ord(actionList["CloseObject"]):
            action="CloseObject"
            held_object = env.last_event.metadata.get("inventoryObjects", [])
            held_obj_name = unique_id_map[held_object[0]["objectId"]] if (held_object := env.last_event.metadata.get("inventoryObjects", [])) else None
            event = env.last_event
            elapsed_time = time.time() - start_time
            objectId, candidates = get_interact_object(env, action, unique_id_map)
            
            if objectId == "NOT_FOUND":
                log_and_print(f"> t={time_frame:03d}({elapsed_time:.2f}s)|<span style='color:red;'>FAIL</span>| action = {action}  <span style='color: red;'>&lt;!!!WARNING: No valid interactable objects found within reachable distance in view!!!!&gt;</span>")
                logs[time_frame] = log_json(event, elapsed_time, elapsed_time, action, "FAIL", get_seen_objects(event, unique_id_map), None, None, held_obj_name, completed_task=list(situation_board))
                time_frame += 1
                continue  # Skip the rest of the loop if no object was found
            
            if objectId == "CANCEL":
                elapsed_time2 = time.time() - start_time
                log_and_print(f"> t={time_frame:03d}({elapsed_time:.2f}s-{elapsed_time2:.2f}s)||CANCEL| action = {action}")
                logs[time_frame] = log_json(event, elapsed_time, elapsed_time2, action, "CANCEL", get_seen_objects(event, unique_id_map), candidates, None, held_obj_name, completed_task=list(situation_board))
                time_frame += 1
                continue  # Skip the rest of the loop if the action was canceled

            target = objectId.split('|')[0]
            event = env.step(action=action, objectId=objectId)
            obj_name = unique_id_map[objectId]
            elapsed_time2 = time.time() - start_time
            if event.metadata['lastActionSuccess']:
                log_and_print(f"> t={time_frame:03d}({elapsed_time:.2f}s-{elapsed_time2:.2f}s)||SUCCESS| action = {action} & object = {obj_name}")
                logs[time_frame] = log_json(event, elapsed_time, elapsed_time2, action, "SUCCESS", get_seen_objects(event, unique_id_map), candidates, obj_name, held_obj_name, completed_task=list(situation_board))
            else:
                raise ValueError(f"Debugging required for {action}!")
            time_frame += 1


        ## Interaction = ToggleObjectOn ############################################################################################  
        elif keystroke == ord(actionList["ToggleObjectOn"]):
            action="ToggleObjectOn"
            held_object = env.last_event.metadata.get("inventoryObjects", [])
            held_obj_name = unique_id_map[held_object[0]["objectId"]] if (held_object := env.last_event.metadata.get("inventoryObjects", [])) else None
            event = env.last_event
            elapsed_time = time.time() - start_time
            objectId, candidates = get_interact_object(env, action, unique_id_map)

            ## If no itmes were found
            if objectId == "NOT_FOUND":
                log_and_print(f"> t={time_frame:03d}({elapsed_time:.2f}s)|<span style='color:red;'>FAIL</span>| action = {action}  <span style='color: red;'>&lt;!!!WARNING: No valid interactable objects found within reachable distance in view!!!!&gt;</span>")
                logs[time_frame] = log_json(event, elapsed_time, elapsed_time, action, "FAIL", get_seen_objects(event, unique_id_map), None, None, held_obj_name, completed_task=list(situation_board))
                time_frame += 1
                continue  # Skip the rest of the loop if no object was found
            
            ## Cancel the action
            if objectId == "CANCEL":
                elapsed_time2 = time.time() - start_time
                log_and_print(f"> t={time_frame:03d}({elapsed_time:.2f}s-{elapsed_time2:.2f}s)|CANCEL| action = {action}")
                logs[time_frame] = log_json(event, elapsed_time, elapsed_time2, action, "CANCEL", get_seen_objects(event, unique_id_map), candidates, None, held_obj_name, completed_task=list(situation_board))
                time_frame += 1
                continue  # Skip the rest of the loop if the action was canceled
            
            ## Implement the action
            target = objectId.split('|')[0]
            event = env.step(action=action, objectId=objectId)
            obj_name = unique_id_map[objectId]
            elapsed_time2 = time.time() - start_time
            if event.metadata['lastActionSuccess']:
                log_and_print(f"> t={time_frame:03d}({elapsed_time:.2f}s-{elapsed_time2:.2f}s)|SUCCESS| action = {action}  & object = {obj_name}")
                logs[time_frame] = log_json(event, elapsed_time, elapsed_time2, action, "SUCCESS", get_seen_objects(event, unique_id_map), candidates, obj_name, held_obj_name, completed_task=list(situation_board))
            else:
                raise ValueError(f"Debugging required for {action}!")
            time_frame += 1


        ## Interaction = ToggleObjectOff ############################################################################################  
        elif keystroke == ord(actionList["ToggleObjectOff"]):
            action="ToggleObjectOff"
            held_object = env.last_event.metadata.get("inventoryObjects", [])
            held_obj_name = unique_id_map[held_object[0]["objectId"]] if (held_object := env.last_event.metadata.get("inventoryObjects", [])) else None
            event = env.last_event
            elapsed_time = time.time() - start_time
            objectId, candidates = get_interact_object(env, action, unique_id_map)

            if objectId == "NOT_FOUND":
                log_and_print(f"> t={time_frame:03d}({elapsed_time:.2f}s)|<span style='color:red;'>FAIL</span>| action = {action}  <span style='color: red;'>&lt;!!!WARNING: No valid interactable objects found within reachable distance in view!!!!&gt;</span>")
                logs[time_frame] = log_json(event, elapsed_time, elapsed_time, action, "FAIL", get_seen_objects(event, unique_id_map), None, None, held_obj_name, completed_task=list(situation_board))
                time_frame += 1
                continue  # Skip the rest of the loop if no object was found
            
            if objectId == "CANCEL":
                elapsed_time2 = time.time() - start_time
                log_and_print(f"> t={time_frame:03d}({elapsed_time:.2f}s-{elapsed_time2:.2f}s)|CANCEL| action = {action}")
                logs[time_frame] = log_json(event, elapsed_time, elapsed_time2, action, "CANCEL", get_seen_objects(event, unique_id_map), candidates, None, held_obj_name, completed_task=list(situation_board))
                time_frame += 1
                continue  # Skip the rest of the loop if the action was canceled
                
            target = objectId.split('|')[0]
            event = env.step(action=action, objectId=objectId)
            obj_name = unique_id_map[objectId]
            elapsed_time2 = time.time() - start_time
            if event.metadata['lastActionSuccess']:
                log_and_print(f"> t={time_frame:03d}({elapsed_time:.2f}s-{elapsed_time2:.2f}s)|SUCCESS| action = {action}  & object = {obj_name}")
                logs[time_frame] = log_json(event, elapsed_time, elapsed_time2, action, "SUCCESS", get_seen_objects(event, unique_id_map), candidates, obj_name, held_obj_name, completed_task=list(situation_board))
            else:
                raise ValueError(f"Debugging required for {action}!")
            time_frame += 1


        ## Interaction = SliceObject ############################################################################################  
        elif keystroke == ord(actionList["SliceObject"]):
            action="SliceObject"
            held_object = env.last_event.metadata.get("inventoryObjects", [])
            held_obj_name = unique_id_map[held_object[0]["objectId"]] if (held_object := env.last_event.metadata.get("inventoryObjects", [])) else None
            event = env.last_event
            elapsed_time = time.time() - start_time
            objectId, candidates = get_interact_object(env, action, unique_id_map)

            if objectId == "NOT_FOUND":
                log_and_print(f"> t={time_frame:03d}({elapsed_time:.2f}s)|<span style='color:red;'>FAIL</span>| action = {action}  <span style='color: red;'>&lt;!!!WARNING: No valid interactable objects found within reachable distance in view!!!!&gt;</span>")
                logs[time_frame] = log_json(event, elapsed_time, elapsed_time, action, "FAIL", get_seen_objects(event, unique_id_map), candidates, None, held_obj_name, completed_task=list(situation_board))
                time_frame += 1
                continue  # Skip the rest of the loop if no object was found
            
            if objectId == "CANCEL":
                elapsed_time2 = time.time() - start_time
                log_and_print(f"> t={time_frame:03d}({elapsed_time:.2f}s-{elapsed_time2:.2f}s)|CANCEL| action = {action}")
                logs[time_frame] = log_json(event, elapsed_time, elapsed_time2, action, "CANCEL", get_seen_objects(event, unique_id_map), candidates, None, held_obj_name, completed_task=list(situation_board))
                time_frame += 1
                continue  # Skip the rest of the loop if the action was canceled

            ## Check if the agent is holding a knife
            if objectId == "NO_KNIFE":
                elapsed_time = time.time() - start_time
                log_and_print(f"> t={time_frame:03d}({elapsed_time:.2f}s)|<span style='color:red;'>FAIL</span>| action = {action}  <span style='color: red;'>&lt;!!!WARNING: You must hold a Knife to perform SliceObject!!!!&gt;</span>")
                logs[time_frame] = log_json(event, elapsed_time, elapsed_time, action, "FAIL", get_seen_objects(event, unique_id_map), candidates, None, held_obj_name, completed_task=list(situation_board))
                time_frame += 1
                continue  # Skip the rest of the loop if no object was found

            target = objectId.split('|')[0]
            event = env.step(action=action, objectId=objectId)
            elapsed_time2 = time.time() - start_time
            obj_name = unique_id_map[objectId]
            if event.metadata['lastActionSuccess']:
                del unique_id_map[objectId]

                pattern = re.escape(objectId)
                pattern_slice = pattern + r'\|(.*)'

                # visible_objects = [object for object in event.metadata['objects'] if object['visible']]
                all_objects = [object for object in event.metadata['objects']]
                # for obj in visible_objects:
                for obj in all_objects:
                    match_result = re.match(pattern_slice, obj['objectId'])
                    if match_result:
                        unique_id_map[obj['objectId']] = match_result.group(1)
    
                    # if re.match(pattern, obj['objectId']):
                    #     unique_id_map[obj['objectId']] = re.match(pattern_slice, obj['objectId']).group(1)
                    #     log_and_print(f"TEST = {re.match(pattern_slice, obj['objectId']).group(1)} ")


                log_and_print(f"> t={time_frame:03d}({elapsed_time:.2f}s-{elapsed_time2:.2f}s)|SUCCESS| action = {action}  & object = {obj_name}")
                logs[time_frame] = log_json(event, elapsed_time, elapsed_time2, action, "SUCCESS", get_seen_objects(event, unique_id_map), candidates, obj_name, held_obj_name, completed_task=list(situation_board))
        

            else:
                raise ValueError(f"Debugging required for {action}!")
            time_frame += 1

        ## INVALID KEY WARNING ############################################################ 
        else:
            # log_and_print("!!! WARNING: INVALID KEY", keystroke)
            continue

        first_view_frame = env.last_event.frame
        cv2.imshow("first_view", cv2.cvtColor(first_view_frame, cv2.COLOR_RGB2BGR))
        first_view_frames.append(first_view_frame)

        ## Calculate probability
        params = {
            'decay_rate': 0.3,
            'noise': 0.5,
            'threshold': 0,
            'offset_time': 1e-3, 
            'offset_neg': 1e-6,
        }

        logs = {int(key): value for key, value in logs.items()} # Make 'key' integer


    return logs, unique_id_map




def show_video(frames: Sequence[np.ndarray], fps: int = 10):
        """Show a video composed of a sequence of frames.

        Example:
        frames = [
            controller.step("RotateRight", degrees=5).frame
            for _ in range(72)
        ]
        show_video(frames, fps=5)
        """
        frames = ImageSequenceClip(frames, fps=fps)
        return frames


def export_video(path, frames):
    """Merges all the saved frames into a .mp4 video and saves it to `path`"""
    video = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*'mp4v'), 5, (frames[0].shape[1], frames[0].shape[0]))
    for frame in frames:
        # assumes that the frames are RGB images. CV2 uses BGR.
        video.write(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    cv2.destroyAllWindows()
    video.release()


def compute_rotate_camera_pose(center, pose, degree_per_frame=6):
    """degree_per_frame: set the degree of rotation for each frame"""

    def rotate_pos(x1, y1, x2, y2, degree):
        angle = math.radians(degree)
        n_x1 = (x1 - x2) * math.cos(angle) - (y1 - y2) * math.sin(angle) + x2
        n_y1 = (x1 - x2) * math.sin(angle) + (y1 - y2) * math.cos(angle) + y2
        return n_x1, n_y1

    # print(math.sqrt((pose["position"]["x"]-center["x"])**2 + (pose["position"]["z"]-center["z"])**2))
    x, z = rotate_pos(pose["position"]["x"], pose["position"]["z"], center["x"], center["z"], degree_per_frame)
    pose["position"]["x"], pose["position"]["z"] = x, z

    direction_x = center["x"] - x
    direction_z = center["z"] - z
    pose["rotation"]["y"] = math.degrees(math.atan2(direction_x, direction_z))

    # print(math.sqrt((pose["position"]["x"]-center["x"])**2 + (pose["position"]["z"]-center["z"])**2))

    return pose


def initialize_side_camera_pose(scene_bound, pose, third_fov=60, slope_degree=45, down_angle=70, scale_factor=8):
    """
    down_angle: the x-axis rotation angle of the camera, represents the top view of the front view from top to bottom, which needs to be less than 90 degrees
    ensure the line vector between scene's center & camera 's angel equal down_angle
    scale_factor scale the camera's view, make it larger ensure camera can see the whole scene
    """
    fov_rad = np.radians(third_fov)
    pitch_rad = np.radians(down_angle)
    distance = (scene_bound["center"]["y"] / 2) / np.tan(fov_rad / 2)
    pose["position"]["y"] = scene_bound["center"]["y"] + distance * scale_factor * np.sin(pitch_rad)
    pose["position"]["z"] = scene_bound["center"]["z"] - distance * scale_factor * np.cos(pitch_rad)
    pose["rotation"]["x"] = down_angle
    pose["orthographic"] = False
    del pose["orthographicSize"]

    pose = compute_rotate_camera_pose(scene_bound["center"], pose, slope_degree)

    return pose



def keyboard_play_thread(queue, env, first_view_frames, is_rotate, rotate_per_frame):
    """
    Run the keyboard play logic in a separate thread.
    """
    keyboard_play(env, first_view_frames, is_rotate, rotate_per_frame, queue)




def main(scene_name="FloorPlan205_physics", gridSize=0.25, rotateStepDegrees=30, BEV=False, slope_degree=45
        , down_angle=65, use_procthor=False, procthor_scene_file="", procthor_scene_num=100, is_rotate=True
        , rotate_per_frame=6, generate_video=False, generate_gif=False, save_result=True):

    ## procthor room
    if use_procthor:
        with gzip.open(procthor_scene_file, "r") as f:
            houses = [line for line in tqdm(f, total=10000, desc=f"Loading train")]
        ## procthor train set's room 
        house = json.loads(houses[procthor_scene_num])
    else:
        ## select room, 1-30，201-230，301-330，401-430 are ithor's room
        house = scene_name
    

    ## Initialize the environment
    controller = Controller(
        agentMode="default",
        visibilityDistance=2.0,
        renderInstanceSegmentation=True,
        scene=house,
        ## step sizes
        gridSize=gridSize,
        snapToGrid=False,
        rotateStepDegrees=rotateStepDegrees,
        ## camera properties
        width=1600,
        height=1600,
        fieldOfView=90,
    )


    ## collect frame
    first_view_frames = []
    logs, unique_id_map = keyboard_play(controller, first_view_frames, is_rotate, rotate_per_frame)

    if logs is not False:

        logs[9999] = unique_id_map


        ## Save the result - recording and log
        if save_result:
            ## Get the current script's directory
            script_dir = os.path.dirname(os.path.abspath(__file__))
            default_output_dir = os.path.join(script_dir, "game_result")

            ## Prompt user for video save path
            folder_name = input(f"Enter the folder name to save the video (default: 'game_result'): ").strip() or "game_result"
            output_dir = os.path.join(default_output_dir, folder_name)

            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
                log_and_print("Video directory created: {output_dir}")

            ## Save video
            video_path = os.path.join(output_dir, f"recording_{scene_name}.mp4")
            export_video(video_path, first_view_frames)
            log_and_print(f"Video saved at: {video_path}")

            ## Save logs
            save_json(logs, output_dir, filename="action_logs.json")
            log_and_print(f"Logs saved at: {os.path.join(output_dir, 'action_logs.json')}")
        

    log_and_print("Exiting program...")

if __name__ == "__main__":
    main(scene_name="FloorPlan13", ## room
         gridSize=0.25, rotateStepDegrees=90, ## agent step len and rotate degree
         BEV=False, ## Bird's-eye view or top view(slope)
         slope_degree=60, ## top view(slope)'s initial rotate degree
         down_angle=65, ## top view(slope)'s pitch angle, should be 0-90, 90 equal to Bird's-eye view
        use_procthor=False, ## use procthor room, True: select room from procthor train set, need dataset dir
         procthor_scene_file="", ## procthor train set dir
         procthor_scene_num=100, ## select scene from procthor train set 
         is_rotate=True, ## top_view rotate?
         rotate_per_frame=6, ## top_view rotate degree
         generate_video=True, ## use frames generate video
         generate_gif=True,  ## use frames generate gif
         save_result=True,
         ) 


