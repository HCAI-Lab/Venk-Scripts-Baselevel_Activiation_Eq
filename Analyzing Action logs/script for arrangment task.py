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

def process_arrangement_log(log_data):
    arrangement_summary = {"Arrangement": {}}
    
    previous_elapsed_time_ae = 0
    previous_completed_tasks = set()
    active_subtasks = {}  # Tracks active subtasks
    last_active_task = None  # Last active arrangement task
    arrangement_started = False  # Flag to track when arrangement begins

    for time_frame, data in log_data.items():
        # Detect the start of the arrangement task (after END_EXPLORATION)
        if not arrangement_started:
            if data.get("action") == "END_EXPLORATION" and data.get("result") == "SUCCESS":
                arrangement_started = True
            continue  # Skip frames until arrangement starts

        # Detect the end of the arrangement task
        if data.get("action") == "END_ARRANGEMENT" and data.get("result") == "SUCCESS":
            break  # Stop processing after END_ARRANGEMENT

        completed_tasks = set(data.get("completed_tasks", []) or [])
        new_tasks = completed_tasks - previous_completed_tasks
        current_task = data.get("current_task")
        agent_position = data.get("agent", {}).get("position", {})

        # Determine the current location from the agent's position
        location = get_location_from_position(agent_position)

        # If a new subtask appears, initialize its tracking data
        if current_task and current_task not in active_subtasks:
            active_subtasks[current_task] = {
                "Description": current_task,
                "total_Num_of_GameStatusCheck_pressed": 0,
                "total_Num_of_CheckObjectState_pressed": 0,
                "total_num_of_object_seen": set(),
                "total_num_of_interactable_objects": set(),
                "completion_time": 0,
                "score": None,  # Will be updated only on completion
                "locations": {loc: {
                    "num_of_visit": 0,
                    "Num_of_GameStatusCheck_pressed": 0,
                    "Num_of_CheckObjectState_pressed": 0,
                    "num_of_object_seen": set(),
                    "num_of_interactable_objects": set()
                } for loc in FLOORPLAN2.keys()},
                "_start_time": data.get("elapsed_time_ae", previous_elapsed_time_ae)  # Internal only
            }

        # Update last_active_task **only if** current_task is valid
        if current_task:
            last_active_task = current_task

        # Only process objects if last_active_task is valid
        if last_active_task and last_active_task in active_subtasks:
            task_data = active_subtasks[last_active_task]

            # Track the unique objects seen
            seen_objects = set(data.get("object_seen", []))
            task_data["total_num_of_object_seen"].update(seen_objects)

            # Compute interactable objects (all objects seen - excluded ones)
            if location in EXCLUDE:
                excluded_objects = set(EXCLUDE[location]) & task_data["total_num_of_object_seen"]
                task_data["total_num_of_interactable_objects"] = task_data["total_num_of_object_seen"] - excluded_objects
            else:
                task_data["total_num_of_interactable_objects"] = task_data["total_num_of_object_seen"]

            # Track game status and object state checks
            action = data.get("action", "")
            if "GameStatusCheck" in action:
                task_data["total_Num_of_GameStatusCheck_pressed"] += 1
            if "CheckObjectState" in action:
                task_data["total_Num_of_CheckObjectState_pressed"] += 1

            # Update location-specific tracking
            if location:
                loc_data = task_data["locations"][location]
                loc_data["num_of_visit"] += 1
                loc_data["Num_of_GameStatusCheck_pressed"] += (1 if "GameStatusCheck" in action else 0)
                loc_data["Num_of_CheckObjectState_pressed"] += (1 if "CheckObjectState" in action else 0)
                loc_data["num_of_object_seen"].update(seen_objects)
                loc_data["num_of_interactable_objects"] = len(loc_data["num_of_object_seen"])

        # When a subtask moves to completed_tasks, finalize and store its data
        for task in new_tasks:
            if task in active_subtasks:
                task_data = active_subtasks[task]
                task_key = f"Subtask_{len(arrangement_summary['Arrangement']) + 1}"

                # ✅ Compute completion time before removing _start_time
                task_data["completion_time"] = data.get("elapsed_time_ae", previous_elapsed_time_ae) - task_data["_start_time"]

                # ✅ Store the score ONLY on task completion
                task_data["score"] = {
                    "rearrangement_score": data.get("scores", {}).get("rearrangement_score", 0),
                    "main_score": data.get("scores", {}).get("main_score", 0)
                }

                # ✅ Remove `_start_time` before saving to final JSON
                del task_data["_start_time"]

                # Convert sets to counts
                task_data["total_num_of_object_seen"] = len(task_data["total_num_of_object_seen"])
                task_data["total_num_of_interactable_objects"] = len(task_data["total_num_of_interactable_objects"])

                for loc in task_data["locations"]:
                    loc_data = task_data["locations"][loc]
                    loc_data["num_of_object_seen"] = len(loc_data["num_of_object_seen"])

                    # ✅ Convert only if it's a set
                    if isinstance(loc_data["num_of_interactable_objects"], set):
                        loc_data["num_of_interactable_objects"] = len(loc_data["num_of_interactable_objects"])

                arrangement_summary["Arrangement"][task_key] = task_data
                del active_subtasks[task]  # Remove from active subtasks

        previous_completed_tasks = completed_tasks

    return arrangement_summary

# Load input JSON file
with open(r"swlee\action_logs.json", "r") as file:
    log_data = json.load(file)

# Process the log
arrangement_summary = process_arrangement_log(log_data)

# Save output JSON file
with open(r"swlee\arrangement_summary.json", "w") as output_file:
    json.dump(arrangement_summary, output_file, indent=4)

print("Arrangement summary saved to arrangement_summary.json")
