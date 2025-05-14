import json
import re
import current_time_main_task_objects

# Load JSON file
with open("ashish_logs.json", "r") as file:
    data = json.load(file)

# Define constants
MAIN_TASK_OBJECTS = ['Apple_1', 'ButterKnife_1', 'Fork_1', 'Bowl_1', 'Spoon_1', 'Ladle_1', 'DishSponge_1', 'Faucet_1']
OPENABLE = ['Fridge', 'Cabinet', 'Microwave', 'Drawer', 'Safe', 'Box']
PICKUPABLE = ['AlarmClock', 'Apple', 'AppleSliced', 'ArmChair', 'BaseballBat',
              'BasketBall', 'Book', 'Bowl', 'Box', 'Bread', 'BreadSliced', 'ButterKnife', 'CD', 
              'Candle', 'CellPhone', 'Cloth', 'CreditCard', 'Cup',
              'DishSponge', 'Egg', 'Fork', 'Glassbottle', 'HandTowel', 'Kettle', 'KeyChain',
              'Knife', 'Ladle', 'Laptop', 'Lettuce', 'LettuceSliced', 'Mug',
              'Newspaper','Pan', 'Pen', 'Pencil', 'PepperShaker',
              'Pillow', 'Plate', 'Plunger', 'Pot', 'Potato', 'PotatoSliced', 'RemoteControl',
              'SaltShaker','SoapBar','SoapBottle', 'Spatula', 'Spoon', 'SprayBottle', 'Statue',
              'TennisRacket', 'TissueBox', 'ToiletPaper','Tomato', 'TomatoSliced', 'Vase', 
              'Watch', 'WateringCan', 'WineBottle', 'ToiletPaperRoll', 'PaperTowelRoll']

# Define FLOORPLAN2 and EXCLUDE
FLOORPLAN2 = {
    "Fridge": {"x": -0.75, "z": 0.0},
    "Sink": {"x": -0.75, "z": -0.5},
    "CounterTop_1": {"x": 0.0, "z": -0.75},
    "Microwave&CoffeeMachine": {"x": 0.85, "z": -0.35},
    "Stove": {"x": 0.75, "z": 0.75},
    "CounterTop_2": {"x": 1.0, "z": 1.25},
    "Door": {"x": -0.75, "z": 3.0},
}

EXCLUDE = {
    "Fridge": ["Cabinet_2"],
    "Sink": ["Drawer_1", "Window_2"],
    "CounterTop_1": ["Fridge_1", "Bowl_1", "CellPhone_1", "Drawer_4", "Drawer_8", "Drawer_9", "Drawer_10", "CounterTop_1"],
    "Microwave&CoffeeMachine": ["Drawer_3", "Cabinet_5", "Cabinet_6"],
    "Stove": ["Window_3", "Microwave_1"],
    "CounterTop_2": ["CounterTop_1"],
    "Door": ["CellPhone_1", "Potato_1", "Chair_1", "GarbageCan_1", "CounterTop_2"],
}

# Initialize result storage
observations_output = {}

# Ensure time frames are processed in order
time_keys = sorted(map(int, data.keys()))

# Helper function to get location from agent position
def get_location_from_position(agent_position):
    """Finds the location name based on the agent's x, z coordinates."""
    for location, pos in FLOORPLAN2.items():
        if round(agent_position.get("x", 0), 2) == round(pos["x"], 2) and round(agent_position.get("z", 0), 2) == round(pos["z"], 2):
            return location
    return None  # If no matching location is found

# Iterate over each main task object separately
for main_object in MAIN_TASK_OBJECTS:
    observations_output[main_object] = {"Observations": []}
    
    # Object-specific tracking variables
    unique_interactable = set()
    unique_pickupable = set()
    unique_openable = set()
    
    start_time = None
    end_time = None
    current_task = None
    recording = False  # Indicates if we are tracking an observation

    for time_key in time_keys:
        frame_data = data[str(time_key)]
        
        # Stop processing if we reach "END_ARRANGEMENT"
        if frame_data.get("action") == "END_ARRANGEMENT":
            break

        object_seen = frame_data.get("object_seen", [])
        completed_tasks = frame_data.get("completed_tasks")
        task = frame_data.get("current_task")
        elapsed_time = frame_data.get("elapsed_time_as")
        agent_position = frame_data.get("agent", {}).get("position", {})

        # If the object appears and we are not already recording, start tracking
        if main_object in object_seen and not recording:
            start_time = elapsed_time
            current_task = task
            recording = True  # Begin tracking this observation
            unique_interactable.clear()
            unique_pickupable.clear()
            unique_openable.clear()

        # If tracking is active, keep updating unique object counts
        if recording:
            for obj in object_seen:
                # Full object name with numbers intact
                full_object_name = obj  # Keep full object name (with numbers)

                # Check if the agent's position matches any location in FLOORPLAN2
                location = get_location_from_position(agent_position)
                if location in EXCLUDE:
                    if full_object_name in EXCLUDE[location]:
                        continue  # Skip this object if it should be excluded based on the agent's location

                # Remove any numbers for checking if object is in pickupable, openable, or interactable
                base_name = re.sub(r'_\d+$', '', full_object_name)

                # Check if the base_name is in the PICKUPABLE list
                if base_name in PICKUPABLE:
                    unique_pickupable.add(base_name)

                # Check if the base_name is in the OPENABLE list
                if base_name in OPENABLE:
                    unique_openable.add(base_name)

                # Now, check if the object should be added to the interactable set
                unique_interactable.add(base_name)

        # If recording and completed tasks change (current task is found), finalize the observation
        if recording and completed_tasks and current_task in completed_tasks:
            end_time = elapsed_time
            # Record observation using current_time_main_task_objects.get_object_current_time to get the current time
            observations_output[main_object]["Observations"].append({
                "Observation": f"Observation_{len(observations_output[main_object]['Observations']) + 1}",
                "Current Time": current_time_main_task_objects.get_object_current_time(data, main_object),
                "Current Task": current_task,
                "Start Time": start_time,
                "End Time": end_time,
                "Completion Time": end_time - start_time,
                "Num Unique Interactable Objects": len(unique_interactable),
                "Num Unique Pickupable Objects": len(unique_pickupable),
                "Num Unique Openable Objects": len(unique_openable)
            })
            recording = False  # Reset for the next occurrence

# Save output to JSON file
with open("observations_output.json", "w") as file:
    json.dump(observations_output, file, indent=4)

print("Observation tracking completed successfully.")
