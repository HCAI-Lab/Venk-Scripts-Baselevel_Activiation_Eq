import json


# Mapping of locations based on agent position
FLOORPLAN2 = {
    "Fridge": {"x": -0.75, "z": 0.0},
    "Sink": {"x": -0.75, "z": -0.5},
    "CounterTop_1": {"x": 0.0, "z": -0.75},
    "Microwave&CoffeeMachine": {"x": 0.85, "z": -0.35},
    "Stove": {"x": 0.75, "z": 0.75},
    "CounterTop_2": {"x": 1.0, "z": 1.25},
    "Door": {"x": -0.75, "z": 3.0},
}

# Exclusion list for objects that should not be counted
EXCLUDE = {
    "Fridge": ["Cabinet_2"],
    "Sink": ["Drawer_1", "Window_2"],
    "CounterTop_1": ["Fridge_1", "Bowl_1", "CellPhone_1", "Drawer_4", "Drawer_8", "Drawer_9", "Drawer_10", "CounterTop_1"],
    "Microwave&CoffeeMachine": ["Drawer_3", "Cabinet_5", "Cabinet_6"],
    "Stove": ["Window_3", "Microwave_1"],
    "CounterTop_2": ["CounterTop_1"],
    "Door": ["CellPhone_1", "Potato_1", "Chair_1", "GarbageCan_1", "CounterTop_2"],
}

def get_location_from_position(agent_position):
    """Finds the location name based on the agent's x, z coordinates."""
    for location, pos in FLOORPLAN2.items():
        if round(agent_position.get("x", 0), 2) == round(pos["x"], 2) and round(agent_position.get("z", 0), 2) == round(pos["z"], 2):
            return location
    return None  # If no matching location is found

def process_exploration_log(log_data):
    exploration_summary = {"Exploration": {}}
    
    previous_elapsed_time_ae = 0
    previous_completed_tasks = set()
    active_subtasks = {}  # Tracks the currently active subtask and accumulates metrics
    last_active_task = None  # Keeps track of which task was active when an action happened

    for time_frame, data in log_data.items():
        completed_tasks = set(data.get("completed_tasks", []) or [])
        new_tasks = completed_tasks - previous_completed_tasks
        current_task = data.get("current_task")
        agent_position = data.get("agent", {}).get("position", {})
        action = data.get("action", "")

        # Determine the current location from the agent's position
        location = get_location_from_position(agent_position)

        # If a new subtask appears, initialize its tracking data if not already present
        if current_task and current_task not in active_subtasks:
            active_subtasks[current_task] = {
                "Num_of_GameStatusCheck_pressed": 0,
                "Num_of_CheckObjectState_pressed": 0,
                "num_of_object_seen": set(),  # Track unique objects seen as a set
                "start_time": data.get("elapsed_time_ae", previous_elapsed_time_ae)
            }

        # Update last_active_task **only if** current_task is valid
        if current_task:
            last_active_task = current_task

        # Only process objects if last_active_task is valid
        if last_active_task and last_active_task in active_subtasks:
            # Track the unique objects seen
            seen_objects = set(data.get("object_seen", []))  # Convert list to set for uniqueness
            active_subtasks[last_active_task]["num_of_object_seen"].update(seen_objects)

            # **Fix: Track GameStatusCheck and ObjectStateCheck presses**
            if "GameStatusCheck" in action:
                active_subtasks[last_active_task]["Num_of_GameStatusCheck_pressed"] += 1
            if "CheckObjectState" in action:
                active_subtasks[last_active_task]["Num_of_CheckObjectState_pressed"] += 1

            # Compute interactable objects (all objects seen - excluded ones)
            num_of_object_seen = len(active_subtasks[last_active_task]["num_of_object_seen"])
            num_of_interactable_objects = num_of_object_seen  # By default, all seen objects are interactable

            if location in EXCLUDE:
                excluded_objects = set(EXCLUDE[location]) & active_subtasks[last_active_task]["num_of_object_seen"]
                num_of_interactable_objects -= len(excluded_objects)  # Subtract excluded objects

            # Ensure it does not go negative
            num_of_interactable_objects = max(num_of_interactable_objects, 0)

        # When a subtask moves to completed_tasks, finalize and store its data
        for task in new_tasks:
            if task in active_subtasks:
                task_key = f"Subtask_{len(exploration_summary['Exploration']) + 1}"
                completion_time = data.get("elapsed_time_ae", previous_elapsed_time_ae) - active_subtasks[task]["start_time"]

                exploration_summary["Exploration"][task_key] = {
                    "Description": f"{task}",
                    "Num_of_GameStatusCheck_pressed": active_subtasks[task]["Num_of_GameStatusCheck_pressed"],
                    "Num_of_CheckObjectState_pressed": active_subtasks[task]["Num_of_CheckObjectState_pressed"],
                    "num_of_object_seen": num_of_object_seen,  # Unique objects count
                    "num_of_interactable_objects": num_of_interactable_objects,  # Corrected logic
                    "completion_time": completion_time
                }
                
                del active_subtasks[task]  # Remove from active subtasks after storing

        previous_completed_tasks = completed_tasks

        # Stop processing when END_EXPLORATION is encountered, but record its state
        if data.get("action") == "END_EXPLORATION" and data.get("result") == "SUCCESS":
            if last_active_task in active_subtasks:
                task_key = f"Subtask_{len(exploration_summary['Exploration']) + 1}"
                completion_time = data.get("elapsed_time_ae", previous_elapsed_time_ae) - active_subtasks[last_active_task]["start_time"]

                exploration_summary["Exploration"][task_key] = {
                    "Description": f"{last_active_task} (Final Task)",
                    "Num_of_GameStatusCheck_pressed": active_subtasks[last_active_task]["Num_of_GameStatusCheck_pressed"],
                    "Num_of_CheckObjectState_pressed": active_subtasks[last_active_task]["Num_of_CheckObjectState_pressed"],
                    "num_of_object_seen": num_of_object_seen,
                    "num_of_interactable_objects": num_of_interactable_objects,
                    "completion_time": completion_time
                }

            break  # Stop processing after recording the final task

    return exploration_summary

# Load input JSON file
with open(r"chulhyun\action_logs.json", "r") as file:
    log_data = json.load(file)

# Process the log
exploration_summary = process_exploration_log(log_data)

# Save output JSON file
with open(r"chulhyun\exploration_summary.json", "w") as output_file:
    json.dump(exploration_summary, output_file, indent=4)

print("Exploration summary saved to exploration_summary.json")
