import copy, ast

# model imports
import smm.models.predicates
import smm.models.fuzzy

class SMM:
    # the mental model class
    #   model: name of the model to use
    #   visibility: visibility of the agent (O, D, V type and radius/range, e.g., O4 will be a circle of radius 4 units)
    #   agent: name of the agent to follow, for our domains A0 is the robot and A1 is the human
    def __init__(self, model:str, visibility:str, agent:str):
        if model == "predicates":
            self.model = smm.models.predicates.SMMPredicates(can_see=self.can_see)
        elif model == "fuzzy":
            self.model = smm.models.fuzzy.SMMFuzzy(can_see=self.can_see)
        else:
            raise ValueError("Failed to initialize SMM, model must be 'predicates' or 'fuzzy'")
        if visibility[0] not in ["O", "D", "V"]:
            raise ValueError("Incorrect visibility type, visibility must be of the format (type)(range), e.g., V5, O2, D99")
        self.visibility_type = visibility[0]
        if not visibility[1:].isdigit():
            raise ValueError("Incorrect visibility range, visibility must be of the format (type)(range), e.g., V5, O2, D99")
        self.visibility_range = int(visibility[1:])
        self.belief_state = {}  # the belief state output by the SMM
        self.agent_name = agent
        self.initialized = False

    # loads an initial belief state from a layout dictionary
    def init_belief_state(self, layout:dict):
        grid = layout["grid"].replace("                ", "").split("\n")
        if "start_state" in layout:
            if "objects" in layout["start_state"]:
                for obj in layout["start_state"]["objects"]:
                    row = obj["position"][1]
                    col = obj["position"][0]
                    if obj["name"] == "tomato":
                        grid[row] = grid[row][:col] + "t" + grid[row][col+1:]
                    if obj["name"] == "onion":
                        grid[row] = grid[row][:col] + "o" + grid[row][col+1:]
        self.model.init_belief_state(grid)
        self.initialized = True

    # initializes a belief state from a layout file name
    def init_belief_state_from_file(self, layout:str):
        if not layout.endswith(".layout"):
            layout += ".layout"
        with open("env/server/layouts/" + layout, "r") as f:
            layout = ast.literal_eval(f.read())
            self.init_belief_state(layout)

    # gets the visible portion of a belief state
    def get_visible_belief_state(self):
        for k in self.belief_state["objects"]:
            if not self.belief_state["objects"][k]["visible"]:
                pass
                # print("IGNORING", k, self.belief_state["objects"][k])
        visible_belief_state = {
            # return all agents, because agents are always visible
            "agents": copy.deepcopy(self.belief_state["agents"]),
            # return objects that have a True "visible" property
            "objects": {
                k : copy.deepcopy(self.belief_state["objects"][k]) for k in self.belief_state["objects"] if self.belief_state["objects"][k]["visible"]
            }
        }
        return visible_belief_state
    
    # updates the model by filtering state visibility and shunting over to the model
    #   from_log: dictionary from a log file, representing raw observations from the game
    #   from_smm: dictionary from another SMM, representing a belief state\
    def update(self, state:dict, debug:bool=False)->None:
        state = copy.deepcopy(state)  # deep copy the dict
        state = self.filter_visibility(state=state)  # remove features outside the user's visibility from the state
        self.belief_state = self.model.update(state=state, debug=debug)  # update the model

    # filter out objects and agents that are not immediately visible
    def filter_visibility(self, state:dict):
        agent_position = state["agents"][self.agent_name]["position"] #if state_type == "log" else state["agents"]["A" + str(self.agent_name)]["position"]
        agent_orientation = state["agents"][self.agent_name]["facing"] #if state_type == "log" else state["agents"]["A" + str(self.agent_name)]["facing"]

        # filter out objects
        object_ids = [x for x in state["objects"]]
        for o in object_ids: #if state_type == "log" else state["objects"]):
            dX = state["objects"][o]["position"][0] - agent_position[0] #if state_type == "log" else state["objects"][o]["position"][0] - agent_position[0]
            dY = state["objects"][o]["position"][1] - agent_position[1] #if state_type == "log" else state["objects"][o]["position"][1] - agent_position[1]
            if not self.can_see(agent_orientation, dX, dY):
                del state["objects"][o]
        
        # filter out other agents
        # agent_ids = [x for x in state["agents"]]
        # for a in agent_ids: #if state_type == "log" else state["agents"]):
        #     dX = state["agents"][a]["position"][0] - agent_position[0] #if state_type == "log" else state["agents"][a]["position"][0] - agent_position[0]
        #     dY = state["agents"][a]["position"][1] - agent_position[1] #if state_type == "log" else state["agents"][a]["position"][1] - agent_position[1]
        #     if not self.can_see(agent_orientation, dX, dY):
        #         del state["agents"][a]
        
        return state

    # whether the agent can see the object given the object's dx and dy relative to the agent, this is copied from game.py
    def can_see(self, agent_orientation, dX, dY):       
        # V visibility: agents sees everything in front of them with 90deg field of view (45deg angles)
        if self.visibility_type == "V":
            # agent facing right, ignore items to left of agent and beyond 45deg (dY > dX)
            if agent_orientation == (1, 0) and (dX < 0 or abs(dY) > abs(dX) or dY * dY + dX * dX > self.visibility_range * self.visibility_range):
                return False
            # agent facing left, ignore items to right of agent and beyond 45deg (dY > dX)
            if agent_orientation == (-1, 0) and (dX > 0 or abs(dY) > abs(dX) or dY * dY + dX * dX > self.visibility_range * self.visibility_range):
                return False
            # agent facing up, ignore items to down of agent and beyond 45deg (dX > dY)
            if agent_orientation == (0, 1) and (dY < 0 or abs(dX) > abs(dY) or dY * dY + dX * dX > self.visibility_range * self.visibility_range):
                return False
            # agent facing down, ignore items to up of agent and beyond 45deg (dX > dY)
            if agent_orientation == (0, -1) and (dY > 0 or abs(dX) > abs(dY) or dY * dY + dX * dX > self.visibility_range * self.visibility_range):
                return False

        # D visibility: agents see everything in front of them to a radius
        elif self.visibility_type == "D":
            # agent facing right, ignore items to left of agent and where dist > max
            if agent_orientation == (1, 0) and (dX < 0 or dY * dY + dX * dX > self.visibility_range * self.visibility_range):
                return False
            # agent facing left, ignore items to right of agent and where dist > max
            if agent_orientation == (-1, 0) and (dX > 0 or dY * dY + dX * dX > self.visibility_range * self.visibility_range):
                return False
            # agent facing up, ignore items to down of agent and where dist > max
            if agent_orientation == (0, 1) and (dY < 0 or dY * dY + dX * dX > self.visibility_range * self.visibility_range):
                return False
            # agent facing down, ignore items to up of agent and where dist > max
            if agent_orientation == (0, -1) and (dY > 0 or dY * dY + dX * dX > self.visibility_range * self.visibility_range):
                return False
        
        # O visibility: agents see everything around them to a radius
        elif self.visibility_type == "O":
            # ignore items where dist > max
            if dY * dY + dX * dX > self.visibility_range * self.visibility_range:
                return False
            
        return True
    
    # converts an observed world state from the log files to the data structure used by the belief state modules
    def convert_log_to_state(self, log):
        state = {
            "agents": {},
            "objects": {}
        }

        # get the object information
        for i in range(len(log["state"]["objects"])):
            object_id = "O" + str(i+1)
            state["objects"][object_id] = {
                "position": log["state"]["objects"][i]["position"],
                "propertyOf": {
                    "name": log["state"]["objects"][i]["name"],
                },
                "visible": True,  # by default, model assumes objects are visible
                "canUseWith": []  # by default, the model does not know what objects can be used with
            }

            # if the object has ingredients, set those
            if "_ingredients" in log["state"]["objects"][i]:
                state["objects"][object_id]["propertyOf"]["ingredients"] = []
                for ingredient in log["state"]["objects"][i]["_ingredients"]:
                    state["objects"][object_id]["propertyOf"]["ingredients"].append({
                        "position": ingredient["position"],
                        "propertyOf": {
                            "name": ingredient["name"]
                        }
                    })
                if log["state"]["objects"][i]["is_ready"] is None:
                    pass
                state["objects"][object_id]["propertyOf"]["isReady"] = log["state"]["objects"][i]["is_ready"]
                state["objects"][object_id]["propertyOf"]["isCooking"] = log["state"]["objects"][i]["is_cooking"]
                if "is_idle" in log["state"]["objects"][i]:
                    state["objects"][object_id]["propertyOf"]["isIdle"] = log["state"]["objects"][i]["is_idle"]

        # get the agent information 
        for i in range(len(log["state"]["players"])):
            agent_id = "A" + str(i)
            state["agents"][agent_id] = {
                "position": log["state"]["players"][i]["position"],
                "facing": log["state"]["players"][i]["orientation"],
            }
            # if the agent is holding an object, include it
            if log["state"]["players"][i]["held_object"] is not None:
                state["agents"][agent_id]["holding"] = {
                    "position": log["state"]["players"][i]["position"],
                    "propertyOf": {
                        "name": log["state"]["players"][i]["held_object"]["name"],
                        "holder": agent_id
                    }
                }
                # if the object has ingredients, set those
                if "_ingredients" in log["state"]["players"][i]["held_object"]:
                    state["agents"][agent_id]["holding"]["propertyOf"]["ingredients"] = []
                    for ingredient in log["state"]["players"][i]["held_object"]["_ingredients"]:
                        state["agents"][agent_id]["holding"]["propertyOf"]["ingredients"].append({
                            "position": ingredient["position"],
                            "propertyOf": {
                                "name": ingredient["name"]
                            }
                        })
            else:
                state["agents"][agent_id]["holding"] = None

        return state