import math
import json

# Load the observations output JSON
with open('observations_output.json', 'r') as file:
    observations_output = json.load(file)

def calculate_s_interactable(i, observation):
    """
    Calculate s(i) for interactable objects: (end_time - start_time) / len(interactable_objects)
    """
    interactable_objects = observation.get("Num Unique Interactable Objects", 0)
    if interactable_objects == 0:
        return 0
    return (observation["End Time"] - observation["Start Time"]) / interactable_objects

def calculate_s_pickupable(i, observation):
    """
    Calculate s(i) for pickupable objects: (end_time - start_time) / len(pickupable_objects)
    """
    pickupable_objects = observation.get("Num Unique Pickupable Objects", 0)
    if pickupable_objects == 0:
        return 0
    return (observation["End Time"] - observation["Start Time"]) / pickupable_objects

def calculate_s_openable(i, observation):
    """
    Calculate s(i) for openable objects: if zero, return 0
    """
    openable_objects = observation.get("Num Unique Openable Objects", 0)
    if openable_objects == 0:
        return 0  # If no openable objects, return 0 as specified
    return (observation["End Time"] - observation["Start Time"]) / openable_objects

def calculate_T_start(i, observation, current_time):
    """
    Calculate T(i)(start) = current_time - start_time
    """
    return current_time - observation["Start Time"]

def calculate_T_end(i, observation, current_time):
    """
    Calculate T(i)(end) = current_time - end_time
    """
    return current_time - observation["End Time"]

def calculate_entropy(i, observation, obj_type):
    """
    Calculate entropy: Log2(n), where n is the number of objects of the specified type
    """
    if obj_type == 'interactable':
        num_objects = observation.get("Num Unique Interactable Objects", 0)
    elif obj_type == 'pickupable':
        num_objects = observation.get("Num Unique Pickupable Objects", 0)
    elif obj_type == 'openable':
        num_objects = observation.get("Num Unique Openable Objects", 0)
    else:
        raise ValueError("Invalid object type for entropy calculation")
    
    if num_objects <= 0:
        return 0
    return math.log2(num_objects)

# Example Usage: Loop through each main task and perform the calculations

for main_object, data in observations_output.items():
    for observation in data["Observations"]:
        observation_number = observation["Observation"]
        current_time = observation["Current Time"]
        
        # Calculate s(i) for each type of object
        s_interactable = calculate_s_interactable(observation_number, observation)
        s_pickupable = calculate_s_pickupable(observation_number, observation)
        s_openable = calculate_s_openable(observation_number, observation)
        
        # Calculate T(i)(start) and T(i)(end)
        T_start = calculate_T_start(observation_number, observation, current_time)
        T_end = calculate_T_end(observation_number, observation, current_time)
        
        # Calculate entropy for each type
        entropy_interactable = calculate_entropy(observation_number, observation, 'interactable')
        entropy_pickupable = calculate_entropy(observation_number, observation, 'pickupable')
        entropy_openable = calculate_entropy(observation_number, observation, 'openable')
        
        # Print or store these calculated values as needed
        print(f"Observation {observation_number}:")
        print(f"s(i) for interactable: {s_interactable}")
        print(f"s(i) for pickupable: {s_pickupable}")
        print(f"s(i) for openable: {s_openable}")
        print(f"T(i)(start): {T_start}")
        print(f"T(i)(end): {T_end}")
        print(f"Entropy for interactable: {entropy_interactable}")
        print(f"Entropy for pickupable: {entropy_pickupable}")
        print(f"Entropy for openable: {entropy_openable}")
        print()
