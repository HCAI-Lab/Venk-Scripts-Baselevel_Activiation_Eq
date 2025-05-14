import re
import json

MAIN_TASK_OBJECTS = ['Apple_1', 'ButterKnife_1', 'Fork_1', 'Bowl_1', 'Spoon_1', 'Ladle_1', 'DishSponge_1', 'Faucet_1']

def get_object_current_time(data, object_name):
    # Check if the object_name is valid

    # Flag to ensure we only track after "END_REARRANGEMENT" action
    end_rearrangement_reached = False
    object_current_time = None

    # Iterate over the time frame logs (assuming `action_logs` is already loaded as your JSON)
    for time_frame, frame_data in data.items():
        action = frame_data.get("action", None)
        
        # If the action is "END_REARRANGEMENT", we mark the start of tracking
        if action == "END_ARRANGEMENT":
            end_rearrangement_reached = True
        
        # Check if 'current_task' exists in the frame data
        current_task = frame_data.get("current_task", None)
        
        # If 'current_task' is missing or null, skip this time frame
        if current_task is None:
            continue
        
        elapsed_time_as = frame_data["elapsed_time_as"]

        # Only track after "END_REARRANGEMENT" action and if the current task contains the main task object (without '_1')
        if end_rearrangement_reached:
            task_without_1 = re.sub(r'_1$', '', object_name)  # Remove '_1' using regex

            if task_without_1.lower() in current_task.lower():  # Compare case-insensitive
                object_current_time = elapsed_time_as
                break  # Stop when we find the first occurrence of the object

    return object_current_time

# Usage example:
# log_file_path = "ashish_logs.json"
# object_name = "Apple_1"
# current_time = get_object_current_time(log_file_path, object_name)
# print(f"Current time for {object_name}: {current_time}")
