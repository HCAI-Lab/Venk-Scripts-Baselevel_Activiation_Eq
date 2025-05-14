"""


"""
import numpy as np
import re


LOCATIONS = {
    "Sink":{ "action": "TeleportFull", "position":{"x": -3.0, 'y':0.9, "z": 3.5}, "rotation": {"x": 0, 'y':270, "z": 0}, "horizon": 30 ,'standing': True}
    , "Stove": {"action": "TeleportFull", "position":{"x": -2.75, 'y':0.9, "z": 3.00}, "rotation": {"x": 0, 'y':180, "z": 0}, "horizon": 30 ,'standing': True}
    , "Fridge": {"action": "TeleportFull", "position":{"x": -1.5, 'y':0.9, "z": 3.75}, "rotation": {"x": 0, 'y':90, "z": 0}, "horizon": 30 ,'standing': True}
    , "Door": {"action": "TeleportFull", "position":{"x": -0.75, 'y':0.9, "z": 1.0}, "rotation": {"x": 0, 'y':270, "z": 0}, "horizon": 30 ,'standing': True}
    , "CoffeeMachine": {"action": "TeleportFull", "position":{"x": -1.5, 'y':0.9, "z": 5.75}, "rotation": {"x": 0, 'y':90, "z": 0}, "horizon": 30 ,'standing': True}
    , "CounterTop": {"action": "TeleportFull", "position":{"x": -3.5, 'y':0.9, "z": 4.25}, "rotation": {"x": 0, 'y':0, "z": 0}, "horizon": 30 ,'standing': True}
}



MAIN_TASK = [
    {
        "description": "Cook a sliced bread.",  
        "subconditions": [
            (
                lambda status: any(re.match(r"BreadSliced_\d+", obj) for obj in status),
                "Slice a bread"
            ),
            (
                lambda status: any(status[obj]["isCooked"] == True for obj in status if re.match(r"BreadSliced_\d+", obj)),
                "Cook a sliced bread using the toaster"
            ),
            (
                lambda status: all([
                    any(status[obj]["isToggled"] == False for obj in status if re.match(r"Toaster_\d+", obj)),
                    any(status[obj]["isCooked"] == True for obj in status if re.match(r"BreadSliced_\d+", obj))
                ]),
                "Turn off the toaster after cooking the bread"
            )
        ]
    },
    {
        "description": "Cool down a sliced tomato.", 
        "subconditions": [
            (
                lambda status: any(re.match(r"TomatoSliced_\d+", obj) for obj in status),
                "Slice a tomato"
            ),
            (
                lambda status: any(status[obj]["temperature"] == "Cold" for obj in status if re.match(r"TomatoSliced_\d+", obj)),
                "Ensure the sliced tomato is cold"
            ),
            (
                lambda status: all([
                    all(status[obj]["isOpen"] == False for obj in status if re.match(r"Fridge_\d+", obj)),
                    any(status[obj].get("parentReceptacles") and "Fridge|-00.32|00.00|+03.60" in status[obj]["parentReceptacles"] for obj in status if re.match(r"TomatoSliced_\d+", obj))
                ]),
                "Store the sliced tomato inside the fridge and close the fridge door"
            )
        ]
    },
    {
        "description": "Place a sliced cooked potato on a plate.",  
        "subconditions": [
            (
                lambda status: any(re.match(r"PotatoSliced_\d+", obj) for obj in status),
                "Slice a potato"
            ),
            (
                lambda status: any(status[obj]["isCooked"] == True for obj in status if re.match(r"PotatoSliced_\d+", obj)),
                "Cook the sliced potato using the microwave"
            ),
            # (
            #     lambda status: any(status[obj].get("parentReceptacles") and "Plate|-04.23|+00.91|+04.72" in status[obj]["parentReceptacles"] for obj in status if re.match(r"PotatoSliced_\d+", obj)),
            #     "Place the cooked sliced potato on the plate"
            # ),
            (
                lambda status: all([
                    any(re.match(r"PotatoSliced_\d+", obj) for obj in status),
                    any(status[obj]["isCooked"] == True for obj in status if re.match(r"PotatoSliced_\d+", obj)),
                    any(status[obj].get("parentReceptacles") and "Plate|-04.23|+00.91|+04.72" in status[obj]["parentReceptacles"] for obj in status if re.match(r"PotatoSliced_\d+", obj)),
                    any(status[obj]["isOpen"] == False for obj in status if re.match(r"Microwave_\d+", obj)),
                ]),
                "Close the microwave before placing the potato on the plate"
            )
        ]
    },
    # {
    #     "description": "Cook a sliced potato using a pan.", 
    #     "subconditions": [
    #         (
    #             lambda status: any(re.match(r"PotatoSliced_\d+", obj) for obj in status),
    #             "Slice a potato"
    #         ),
    #         (
    #             lambda status: all([any(status[obj]["isCooked"] == True for obj in status if re.match(r"PotatoSliced_\d+", obj))
    #             , any(status[obj].get("parentReceptacles") and "Pan|-02.45|+00.93|+02.02" in status[obj]["parentReceptacles"] for obj in status if re.match(r"PotatoSliced_\d+", obj))
    #             ]), "Cook the sliced potato using the pan and leave it on the pan."
    #             ),
    #         # (
    #         #     lambda status: any(status[obj]["isCooked"] == True for obj in status if re.match(r"PotatoSliced_\d+", obj)),
    #         #     "Cook the sliced potato using the pan"
    #         # ),
    #         # # (
    #         # #     lambda status: any(status[obj]["temperature"] == "Hot" for obj in status if re.match(r"PotatoSliced_\d+", obj)),
    #         # #     "Ensure the sliced potato is hot"
    #         # # ),
    #         # (
    #         #     lambda status: any(status[obj].get("parentReceptacles") and "Pan|-02.45|+00.93|+02.02" in status[obj]["parentReceptacles"] for obj in status if re.match(r"PotatoSliced_\d+", obj)),
    #         #     "Leave the cooked potato in the pan"
    #         # ),
    #     ]
    # },
    {
        "description": "Place a mug in the left cabinet of the microwave.", 
        "subconditions": [
            (
                lambda status: all(
                    [all(status[obj]["isOpen"] == False for obj in status if re.match(r"Cabinet_\d+", obj)),
                    any(status[obj].get("parentReceptacles") and "Cabinet|-01.58|+01.93|+01.78" in status[obj]["parentReceptacles"] for obj in status if re.match(r"Mug_\d+", obj)),
                ]),
                "Place a mug in the left cabinet of the microwave."
            )
        ]
    }
]




class GameStatus:
    def __init__(self, game_status, main_tasks):
        """
        Initialize the game status evaluator.
        
        :param game_status: Dictionary representing the current state of the game.
        :param arrangement_tasks: List of task dictionaries for arrangement tasks.
        :param main_tasks: List of task dictionaries for main tasks.
        """
        self.game_status_data = game_status
        self.main_task = main_tasks


    def evaluate_task_completion(self):
        report = {}
        all_completed = True

        for task in self.main_task:
            task_name = task["description"]
            completed_conditions = []
            total_conditions = len(task["subconditions"])

            # Collect all sub-task descriptions
            all_subtasks = [condition_text for _, condition_text in task["subconditions"]]

            for condition_func, condition_text in task["subconditions"]:
                if condition_func(self.game_status_data):
                    completed_conditions.append(condition_text)

            completed = len(completed_conditions) == total_conditions
            report[task_name] = {
                "completed": completed,
                "completed_conditions": len(completed_conditions),
                "total_conditions": total_conditions,
                "completion_percentage": round((len(completed_conditions) / total_conditions) * 100, 2),
                "completed_texts": completed_conditions,  # Store completed sub-task descriptions
                "all_subtasks": all_subtasks  # Store all available sub-task descriptions
            }

            if not completed:
                all_completed = False

        return all_completed, report






def interpret(data):
    for n in list(data.keys()):
        action = data[n]['action']
        action_start = data[n]['elapsed_time_as']
        action_end = data[n]['elapsed_time_ae']
        success_fail_cancel = data[n]['result']
        interactable_objects_in_action = process_candidates(data[n]['candidate_objects']) 
        num_interactable_objects_in_action = (len(interactable_objects_in_action) if interactable_objects_in_action else 0)
        selected_object_in_action = data[n]['selected_object']
        object_in_hand = data[n]['held_object']
        objects_in_view = data[n]['object_seen']

        completed_tasks = process_completed_tasks(data[n]['completed_tasks'])

        agent_position = data[n]['game_status']['agent']['position']
        agent_rotation = data[n]['game_status']['agent']['rotation']['y']
        print(f"{n}: '{action}' & AS:{action_start} & AE:{action_end} & {num_interactable_objects_in_action} & Held:{object_in_hand}")



def interpret_task(data, arrangement_tasks, completion_time_prev=None):
    # Create a dictionary to track when each arrangement task is completed
    task_completion_times = {task_id: None for task_id in arrangement_tasks.keys()}
    for n in list(data.keys()):
        completed_tasks = process_completed_tasks(data[n]['completed_tasks'])
        for task_id, task_description in arrangement_tasks.items():
            if task_completion_times[task_id] is None and task_description in completed_tasks:
                task_completion_times[task_id] = n  # Record the time step when the task is completed

    my_dict = {}
    if not completion_time_prev:
        completion_time_prev = None
    for task_id, completion_time in task_completion_times.items():
        task_id = f"Task_{task_id}"
        my_dict[task_id] = {}
        for n in list(data.keys()):
            if completion_time_prev is None:
                if int(n) <= int(completion_time):
                    my_dict[task_id][int(n)] = {
                        'action': data[n]['action'],  
                        'action_start': data[n]['elapsed_time_as'],
                        'action_end': data[n]['elapsed_time_ae'],
                        'success_fail_cancel': data[n]['result'],
                        'interactable_objects_in_action' : process_candidates(data[n]['candidate_objects']) ,
                        'num_interactable_objects_in_action' : (len(interactable_objects_in_action) if interactable_objects_in_action else 0),
                        'selected_object_in_action' : data[n]['selected_object'],
                        'object_in_hand' : data[n]['held_object'],
                        'objects_in_view' : data[n]['object_seen']
                    }
            elif int(completion_time_prev) < int(n) <= int(completion_time):
                my_dict[task_id][int(n)] = {
                    'action': data[n]['action'],  
                    'action_start': data[n]['elapsed_time_as'],
                    'action_end': data[n]['elapsed_time_ae'],
                    'success_fail_cancel': data[n]['result'],
                    'interactable_objects_in_action' : process_candidates(data[n]['candidate_objects']) ,
                    'num_interactable_objects_in_action' : (len(interactable_objects_in_action) if interactable_objects_in_action else 0),
                    'selected_object_in_action' : data[n]['selected_object'],
                    'object_in_hand' : data[n]['held_object'],
                    'objects_in_view' : data[n]['object_seen']
                }
        completion_time_prev = completion_time

    return my_dict






