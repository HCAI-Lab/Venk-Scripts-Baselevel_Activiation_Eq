"""
	Put knife and spoon to the drawer (drawer_3; Drawer|-00.07|+00.75|-00.01) right underneath.
	Put fork, butterknife, spatula, and ladle to the closest drawer (drawer_2; Drawer|-00.45|+00.75|-00.01).
	Put potato, tomato, bread to the fridge.
	Put pot in the cabinet (cabinet_20; Cabinet|-01.15|+02.02|-00.77) above the stove.
	Put paper towel in the cabinet (cabinet_9; Cabinet|-00.82|+00.47|-01.69) below the sink.
	Put kettle in the cabinet (cabinet_12; Cabinet|-01.10|+02.02|-02.00) above the sink.
	Put plate in the cabinet (cabinet_11; Cabinet|-01.15|+02.02|-01.98) above the stove
	Put pepper shaker and salt shaker in the cabinet (cabinet_13; Cabinet|+00.20|+02.02|-02.00 or cabinet_14; Cabinet|+01.18|+02.02|-02.00) above the coffee machine.
	Put pan on the stove.
	Put the bowl on the countertop in the cabinet (cabinet_7; Cabinet|-00.84|+00.47|-00.05 or cabinet_8; Cabinet|-00.84|+00.47|-01.67) below the stove.

"""
import numpy as np
import re

"""
- "FloorPlan11"
- Main arragement:
    1. Put the 'Mug' in the cabinet above the microwave.
    2. Put the 'Knife' and 'Spatula' in the drawer right below the microwave.
    3. Put the 'Bowl' in the cabinet below the microwave.
    4. Put the 'Plate' in the right cabinet below the stove.
    5. Put the 'Fork', 'Spoon', and 'ButterKnife' in the drawer right below the coffee machine.
    6. Put lettuce, tomato, and apple in the fridge.
- Distraction:
    1. Put the 'PaperTowerRoll' in the left cabinet below the sink
    2. Put the 'Kettle' in the right cabinet below the coffee machine.
    3. Put the 'Lettuce' in the sink.

"""
LOCATIONS = {
    "CoffeeMachine": {"action": "TeleportFull", "position":{"x": 0.5, 'y':0.9, "z": -0.5}, "rotation": {"x": 0, 'y':0, "z": 0}, "horizon": 30 ,'standing': True}
    , "Stove": {"action": "TeleportFull", "position":{"x": 1.25, 'y':0.9, "z": -0.5}, "rotation": {"x": 0, 'y':0, "z": 0}, "horizon": 30 ,'standing': True}
    , "Sink":{ "action": "TeleportFull", "position":{"x": 1.0, 'y':0.9, "z": -0.75}, "rotation": {"x": 0, 'y':180, "z": 0}, "horizon": 30 ,'standing': True}
    , "Microwave": {"action": "TeleportFull", "position":{"x": -0.75, 'y':0.9, "z": -0.75}, "rotation": {"x": 0, 'y':180, "z": 0}, "horizon": 30 ,'standing': True}
    , "DinningTable": {"action": "TeleportFull", "position":{"x": -2.0, 'y':0.9, "z": -0.25}, "rotation": {"x": 0, 'y':0, "z": 0}, "horizon": 30 ,'standing': True}
    , "Fridge": {"action": "TeleportFull", "position":{"x": -2.0, 'y':0.9, "z": -0.5}, "rotation": {"x": 0, 'y':180, "z": 0}, "horizon": 30 ,'standing': True}
    , "Door": {"action": "TeleportFull", "position":{"x": -2.5, 'y':0.9, "z": -0.5}, "rotation": {"x": 0, 'y':90, "z": 0}, "horizon": 30 ,'standing': True}
}


EXPLORATION_TASK = [
    {
        "description": "Explore the position 'CoffeeMachine' ",
        "subconditions": [
            (
                lambda status, agent: all(
                    [abs(agent['pos_x'] - (-0.5)) <= 0.01
                    , any(abs(agent['pos_z'] - value) <= 0.01 for value in [-0.5])
                    , abs(agent['rotation'] - 0) <= 0.01
                    ]), "Explore the position 'CoffeeMachine' "
                )
            ],
    },
    {
        "description": "Explore the position 'Stove' ",
        "subconditions": [
            (
                lambda status, agent: all(
                    [abs(agent['pos_x'] - (-1.25)) <= 0.01
                    , any(abs(agent['pos_z'] - value) <= 0.01 for value in [-0.5])
                    , abs(agent['rotation'] - 0) <= 0.01
                    ]),  "Explore the position 'Stove' "
                )
            ],
    },
    {
        "description": "Explore the position 'Sink' ",
        "subconditions": [
            (
                lambda status, agent: all(
                    [abs(agent['pos_x'] - (-1.0)) <= 0.01
                    , any(abs(agent['pos_z'] - value) <= 0.01 for value in [-0.75])
                    , abs(agent['rotation'] - 180) <= 0.01
                    ]),  "Explore the position 'Stove' "
                )
            ],
    }
]


ARRANGEMENT_OBJECTS = {"Task_1" : {"receptacle":"Cabinet|-00.19|+01.69|-01.65", "objects":['Mug_1']}
                    , "Task_2" : {"receptacle":"Drawer|-01.10|+00.79|-01.50", "objects":["Knife_1", "Spatula_1"]}
                    , "Task_3" : {"receptacle":"Cabinet|-00.82|+00.40|-01.35", "objects":["Bowl_1"]} 
                    , "Task_4" : {"receptacle":"Cabinet|+00.73|+00.40|+00.15", "objects":["Kettle_1"]} 
                    , "Task_5" : {"receptacle":"Cabinet|-00.18|+00.40|+00.15", "objects":["Plate_1"]} 
                    , "Task_6" : {"receptacle":"Drawer|+00.02|+00.79|+00.30", "objects":['Fork_1', 'Spoon_1','ButterKnife_1']} 
                    , "Task_7" : {"receptacle":"Fridge|-02.14|+00.00|-01.69", "objects":['Tomato_1','Apple_1']} 
                    , "Task_8" : {"receptacle":"Cabinet|+01.08|+00.40|-01.35", "objects":["PaperTowelRoll_1"]} 
                    , "Task_9" : {"receptacle":"Microwave|-01.04|+00.90|-01.72" , "objects":["Bread_1"]}
}


ARRANGEMENT_TASK = [

    {
        "description": "Put 'Mug' in the cabinet above the microwave.", 
        "subconditions": [
            (
                lambda status, agent: all(
                    [all(status[obj]["isOpen"] == False for obj in status if re.match(r"Cabinet_\d+", obj)),
                    any(status[obj].get("parentReceptacles") and "Cabinet|-00.19|+01.69|-01.65" in status[obj]["parentReceptacles"] for obj in status if re.match(r"Mug_\d+", obj)),
                ]),
                "Place the mug inside the cabinet above the toaster and close the cabinet"
            )
        ] 
    },
    {
        "description": "Put 'Knife' and 'Spatula' in the drawer right below the microwave.", 
        "subconditions": [
            (
                lambda status, agent: all(
                    [all(status[obj]["isOpen"] == False for obj in status if re.match(r"Drawer_\d+", obj)),
                    all(status[obj].get("parentReceptacles") and "Drawer|-01.10|+00.79|-01.50" in status[obj]["parentReceptacles"] for obj in ["Knife_1", "Spatula_1"]),
                ]),
                "Put the 'Knife' and 'Spatula' in the drawer right below the microwave."
            )
        ] 
    },
    {
        "description": "Put 'Bowl' in the right-most cabinet below the microwave.", 
        "subconditions": [
            (
                lambda status, agent: all(
                    [all(status[obj]["isOpen"] == False for obj in ["Cabinet_9"]),
                    all(status[obj].get("parentReceptacles") and "Cabinet|-00.82|+00.40|-01.35" in status[obj]["parentReceptacles"] for obj in ["Bowl_1"]),
                ]),
                "Put 'Bowl' in the right-most cabinet below the microwave."
            )
        ] 
    },

    {
        "description": "Put 'Kettle' in the right cabinet below the coffee machine.", 
        "subconditions": [
            (
                lambda status, agent: all(
                    [all(status[obj]["isOpen"] == False for obj in ["Cabinet_10"]),
                    all(status[obj].get("parentReceptacles") and "Cabinet|+00.73|+00.40|+00.15" in status[obj]["parentReceptacles"] for obj in ["Kettle_1"]),
                ]),
                "Put the 'Kettle' in the right cabinet below the coffee machine."
            )
        ] 
    },

    {
        "description": "Put 'Plate' in the left cabinet below the coffee machine.", 
        "subconditions": [
            (
                lambda status, agent: all(
                    [all(status[obj]["isOpen"] == False for obj in ["Cabinet_7"]),
                    all(status[obj].get("parentReceptacles") and "Cabinet|-00.18|+00.40|+00.15" in status[obj]["parentReceptacles"] for obj in ["Plate_1"]),
                ]),
                "Put 'Plate' in the right cabinet below the stove."
            )
        ] 
    },

    {
        "description": "Put the 'Fork', 'Spoon', and 'ButterKnife' in the left drawer below the coffee machine.", 
        "subconditions": [
            (
                lambda status, agent: all(
                    [all(status[obj]["isOpen"] == False for obj in ["Drawer_6"]),
                    all(status[obj].get("parentReceptacles") and "Drawer|+00.02|+00.79|+00.30" in status[obj]["parentReceptacles"] for obj in ["Fork_1", "Spoon_1", "ButterKnife_1"]),
                ]),
                "Put the 'Fork', 'Spoon', and 'ButterKnife' in the left drawer below the coffee machine."
            )
        ] 
    },

    {
        "description": "Put tomato and apple in the fridge.", 
        "subconditions": [
            (
                lambda status, agent: all(
                    [all(status[obj]["isOpen"] == False for obj in ["Fridge_1"]),
                    all(status[obj].get("parentReceptacles") and "Fridge|-02.14|+00.00|-01.69" in status[obj]["parentReceptacles"] for obj in ["Tomato_1", "Apple_1"]),
                ]),
                "Put tomato and apple in the fridge."
            )
        ] 
    },

    # {
    #     "description": "Put the 'Lettuce' in the sink.", 
    #     "subconditions": [
    #         (
    #             lambda status, agent: all(
    #                 [
    #                 any(status[obj].get("parentReceptacles") and "Sink|+00.71|+00.82|-01.77|SinkBasin" in status[obj]["parentReceptacles"] for obj in ["Lettuce_1"]),
    #             ]),
    #             "Put the 'Lettuce' in the sink."
    #         )
    #     ] 
    # },

    {
        "description": "Put the 'PaperTowelRoll' in the left cabinet below the sink.", 
        "subconditions": [
            (
                lambda status, agent: all(
                    [all(status[obj]["isOpen"] == False for obj in ["Cabinet_3"]),
                    all(status[obj].get("parentReceptacles") and "Cabinet|+01.08|+00.40|-01.35" in status[obj]["parentReceptacles"] for obj in ["PaperTowelRoll_1"]),
                ]),
                "Put the 'PaperTowelRoll' in the left cabinet below the sink."
            )
        ] 
    },


    {
        "description": "Put the 'Bread' in the microwave.", 
        "subconditions": [
            (
                lambda status, agent: all(
                    [all(status[obj]["isOpen"] == False for obj in ["Microwave_1"]),
                    all(status[obj].get("parentReceptacles") and "Microwave|-01.04|+00.90|-01.72" in status[obj]["parentReceptacles"] for obj in ["Bread_1"]),
                ]),
                "Put the 'PaperTowelRoll' in the left cabinet below the sink."
            )
        ] 
    },

    # {
    #     "description": "Move back to the position where you were at the beginning of the game.",
    #     "subconditions": [
    #         (
    #             lambda status, agent: 
    #                 abs(agent['pos_x'] - (-2.5)) <= 0.01 and 
    #                 any(abs(agent['pos_z'] - value) <= 0.01 for value in [-0.5]) and
    #                 abs(agent['rotation'] - 90) <= 0.01,
    #             "Move back to the position where you were at the beginning of the game."
    #         )
    #     ]
    # },

]


"""
1. Prepare a sliced of toasted bread on a plate and bring it to the dinning table.
    - Knife_1,  Plate_1, Bread_1, Microwave_1, Drawer_4, Cabinet_7, DiningTable_1

2. Prepare a sliced tomato in a bowl and bring it to the dinning table. 
    - Knife_1, Bowl_1, Tomato_1, Fridge_1, Cabinet_9, DiningTable_1

3. Prepare a coffee in a mug and bring it to the dinning table.
    - Mug_1, Cabinet_6, DiningTable_1

4. Bring a fork to the dinning table
    - Fork_1, Drawer_6
"""


MAIN_TASK = [
    {
        "description": "Prepare a slice of toasted bread on a plate and bring it to the dinning table.",
        "subconditions": [
            (
                lambda status, agent: all(
                    [all(not status[obj].get("isOpen", True) for obj in status if re.match(r"Drawer_\d+", obj)),
                    all(not status[obj].get("isOpen", True) for obj in status if re.match(r"Cabinet_\d+", obj)),
                    any(status[obj].get("parentReceptacles") and "Plate|-00.11|+00.90|-01.60" in status[obj]["parentReceptacles"] for obj in status if re.match(r"BreadSliced_\d+", obj)),
                    any(status[obj].get("parentReceptacles") and "DiningTable|-02.26|00.00|+00.43" in status[obj]["parentReceptacles"] for obj in ["Plate_1"]),
                    any(status[obj].get("isCooked", False) for obj in status if re.match(r"BreadSliced_\d+", obj)),
                    any(not status[obj].get("isToggled", True) for obj in status if re.match(r"Toaster_\d+", obj)),
                ]),
                "Prepare a sliced of toasted bread on a plate on the dinning table."
            )
        ] 
    }, 

    {
        "description": "Prepare a sliced tomato in a bowl and bring it to the dinning table.",
        "subconditions": [
            (
                lambda status, agent: all(
                    [
                    all(not status[obj].get("isOpen", True) for obj in status if re.match(r"Drawer_\d+", obj)),
                    all(not status[obj].get("isOpen", True)for obj in status if re.match(r"Cabinet_\d+", obj)),
                    all(not status[obj].get("isOpen", True)for obj in status if re.match(r"Fridge_\d+", obj)),
                    any(status[obj].get("parentReceptacles") and "DiningTable|-02.26|00.00|+00.43" in status[obj]["parentReceptacles"] for obj in ["Bowl_1"]),
                    any("Bowl|-02.48|+00.95|+00.23" in (status[obj].get("parentReceptacles") or [])for obj in status if re.match(r"TomatoSliced_\d+", obj))

                ]),
                "Prepare a sliced tomato in a bowl and bring it to the dinning table."
            )
        ] 
    }, 


    {
        "description": "Prepare a coffee in a mug and bring it to the dinning table.",
        "subconditions": [
            (
                lambda status, agent: all(
                    [
                    all(status[obj].get("isFilledWithLiquid", False) for obj in status if re.match(r"Mug_\d+", obj)),
                    any(not status[obj].get("isToggled", True) for obj in status if re.match(r"CoffeeMachine_\d+", obj)),
                    any(status[obj].get("parentReceptacles") and "DiningTable|-02.26|00.00|+00.43" in status[obj]["parentReceptacles"] for obj in ["Mug_1"]),
                    all(not status[obj].get("isOpen", True) for obj in status if re.match(r"Drawer_\d+", obj)),
                    all(not status[obj].get("isOpen", True)for obj in status if re.match(r"Cabinet_\d+", obj)),
                    all(not status[obj].get("isOpen", True)for obj in status if re.match(r"Fridge_\d+", obj)),

                ]),
                "Prepare a coffee in a mug and bring it to the dinning table."
            )
        ] 
    }, 

     {
        "description": "Bring a fork to the dinning table",
        "subconditions": [
            (
                lambda status, agent: all(
                    [
                    any(status[obj].get("parentReceptacles") and "DiningTable|-02.26|00.00|+00.43" in status[obj]["parentReceptacles"] for obj in ["Fork_1"]),
                    all(not status[obj].get("isOpen", True) for obj in status if re.match(r"Drawer_\d+", obj)),
                    all(not status[obj].get("isOpen", True)for obj in status if re.match(r"Cabinet_\d+", obj)),
                    all(not status[obj].get("isOpen", True)for obj in status if re.match(r"Fridge_\d+", obj)),

                ]),
                "Bring a fork to the dinning table"
            )
        ] 
    }, 
    # {
    #     "description": "Move back to the position where you were at the beginning of the game.",
    #     "subconditions": [
    #         (
    #             lambda status, agent: 
    #                 abs(agent['pos_x'] - (-2.5)) <= 0.01 and 
    #                 any(abs(agent['pos_z'] - value) <= 0.01 for value in [-0.5]) and
    #                 abs(agent['rotation'] - 90) <= 0.01,
    #             "Move back to where you were at the beginning of the game."
    #         )
    #     ]
    # },
]




class GameStatus:
    def __init__(self, game_status, agent_info, arrangement_tasks, main_tasks):
        """
        Initialize the game status evaluator.
        
        :param game_status: Dictionary representing the current state of the game.
        :param arrangement_tasks: List of task dictionaries for arrangement tasks.
        :param main_tasks: List of task dictionaries for main tasks.
        """
        self.game_status_data = game_status
        self.agent = agent_info
        self.arrangement_task = arrangement_tasks
        self.main_task = main_tasks

    def evaluate_task_completion_exploration(self):
        report = {}
        all_completed = True

        for task in self.exploration_task:
            task_name = task["description"]
            completed_conditions = []
            total_conditions = len(task["subconditions"])

            # Collect all sub-task descriptions
            all_subtasks = [condition_text for _, condition_text in task["subconditions"]]

            for condition_func, condition_text in task["subconditions"]:
                if condition_func(self.game_status_data, self.agent):
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

    def evaluate_task_completion_arrangement(self):
        report = {}
        all_completed = True

        for task in self.arrangement_task:
            task_name = task["description"]
            completed_conditions = []
            total_conditions = len(task["subconditions"])

            # Collect all sub-task descriptions
            all_subtasks = [condition_text for _, condition_text in task["subconditions"]]

            for condition_func, condition_text in task["subconditions"]:
                if condition_func(self.game_status_data, self.agent):
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


    def evaluate_task_completion_main(self):
        report = {}
        all_completed = True

        for task in self.main_task:
            task_name = task["description"]
            completed_conditions = []
            total_conditions = len(task["subconditions"])

            # Collect all sub-task descriptions
            all_subtasks = [condition_text for _, condition_text in task["subconditions"]]

            for condition_func, condition_text in task["subconditions"]:
                if condition_func(self.game_status_data, self.agent):
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





def objectId_to_objectName(objectId_objectName_dict, objectId):
    return objectId_objectName_dict[objectId]


def objectName_to_objectId(objectId_objectName_dict, objectName):
    return [k for k, v in objectId_objectName_dict.items() if objectName == v][0]


def process_candidates(candidate_objects):
    """
    Extract object IDs from candidate interactable objects.
    """
    if candidate_objects in [None, 'None']:
        return None
    else:
        candidate_objects_in_action = []
        for candidate in candidate_objects:
            candidate_objects_in_action.append(candidate[0]['objectId'])
        return candidate_objects_in_action


def process_completed_tasks(completed_tasks):
    """
    To exclude 'Move back to the position where you were at the beginning of the game.'
    """
    ## Remove the specific element from completed_tasks if it exists
    if completed_tasks is None:
        return []
        
    # Remove the specific task if it exists
    task_to_remove = 'Move back to the position where you were at the beginning of the game.'
    return [task for task in completed_tasks if task != task_to_remove]



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



def interpret_by_task(data, arrangement_tasks, main_tasks):
    ## Split data into arrangement task data and main task data --------------------------------
    N_arrangement = None
    for n, details in list(data.items())[:-1]:  # Exclude the last item
        if details.get('action') and 'END_ARRANGEMENT' in details['action']:
            N_arrangement = n
            break  # Stop once the marker is found

    keys = list(data.keys())
    index = keys.index(N_arrangement)
    arrangement_task_data = {k: data[k] for k in keys[:index+1]}
    main_task_data = {k: data[k] for k in keys[index + 1:-1]}  # Exclude last key
    objectId_objectName_dict = data[keys[-1]]


    ## Exploration and Arrangement Task -------------------------------------------------------
    data = arrangement_task_data
    arrangement_task_completion_times = {task_id: None for task_id in arrangement_tasks.keys()}
    been_there = set()
    count = 0
    exploration_end = None
    for n in list(data.keys()):
        if data[n]['action'] == "MoveTo" and data[n]['result'] == 'SUCCESS':
            count+=1
            position = data[n]['game_status']['agent']['position']
            agent_position = (position['x'], position['y'], position['z'])
            been_there.add(agent_position)
            
        if count == 6 and len(been_there) == 6:
            exploration_end = int(n) + 1

        completed_tasks = process_completed_tasks(data[n]['completed_tasks'])
        for task_id, task_description in arrangement_tasks.items():
            if arrangement_task_completion_times[task_id] is None and task_description in completed_tasks:
                arrangement_task_completion_times[task_id] = n  # Record the time step when the task is completed

    exploration_dict = {}
    arrangement_dict = {}
    for task_id, completion_time in arrangement_task_completion_times.items():
        task_id = f"Task_{task_id}"
        arrangement_dict[task_id] = {}
        for n in list(data.keys()):
            if int(n) <= int(exploration_end) :
                interactable_objects_in_action = process_candidates(data[n]['candidate_objects'])  
                exploration_dict[int(n)] = {
                    'action': data[n]['action'],  
                    'action_start': data[n]['elapsed_time_as'],
                    'action_end': data[n]['elapsed_time_ae'],
                    'success_fail_cancel': data[n]['result'],
                    'interactable_objects_in_action' : interactable_objects_in_action ,
                    'num_interactable_objects_in_action' : (len(interactable_objects_in_action) if interactable_objects_in_action else 0),
                    'selected_object_in_action' : data[n]['selected_object'],
                    'object_in_hand' : data[n]['held_object'],
                    'objects_in_view' : data[n]['object_seen']
                }
            elif int(exploration_end) < int(n) <= int(completion_time):
                interactable_objects_in_action = process_candidates(data[n]['candidate_objects']) 
                arrangement_dict[task_id][int(n)] = {
                    'action': data[n]['action'],  
                    'action_start': data[n]['elapsed_time_as'],
                    'action_end': data[n]['elapsed_time_ae'],
                    'success_fail_cancel': data[n]['result'],
                    'interactable_objects_in_action' : interactable_objects_in_action ,
                    'num_interactable_objects_in_action' : (len(interactable_objects_in_action) if interactable_objects_in_action else 0),
                    'selected_object_in_action' : data[n]['selected_object'],
                    'object_in_hand' : data[n]['held_object'],
                    'objects_in_view' : data[n]['object_seen']
                }
        completion_time_prev = completion_time

    
    ## Main Task --------------------------------------------------------------------------
    data = main_task_data
    main_task_completion_times = {task_id: None for task_id in main_tasks.keys()}
    for n in list(data.keys()):
        completed_tasks = process_completed_tasks(data[n]['completed_tasks'])
        for task_id, task_description in main_tasks.items():
            if main_task_completion_times[task_id] is None and task_description in completed_tasks:
                main_task_completion_times[task_id] = n  # Record the time step when the task is completed

    main_dict = {}
    for task_id, completion_time in main_task_completion_times.items():
        task_id = f"Task_{task_id}"
        main_dict[task_id] = {}
        for n in list(data.keys()):
            if int(n) <= int(completion_time) :
                interactable_objects_in_action = process_candidates(data[n]['candidate_objects'])  
                main_dict[task_id][int(n)] = {
                    'action': data[n]['action'],  
                    'action_start': data[n]['elapsed_time_as'],
                    'action_end': data[n]['elapsed_time_ae'],
                    'success_fail_cancel': data[n]['result'],
                    'interactable_objects_in_action' : interactable_objects_in_action,
                    'num_interactable_objects_in_action' : (len(interactable_objects_in_action) if interactable_objects_in_action else 0),
                    'selected_object_in_action' : data[n]['selected_object'],
                    'object_in_hand' : data[n]['held_object'],
                    'objects_in_view' : data[n]['object_seen']
                }

    return exploration_dict, arrangement_dict, main_dict, objectId_objectName_dict




