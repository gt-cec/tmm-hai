import copy

# model imports
import smm.models.predicates
import smm.models.fuzzy

class SMM:
    def __init__(self, model:str):
        if model == "predicates":
            self.model = smm.models.predicates.SMMPredicates()
        if model == "fuzzy":
            self.model = smm.models.fuzzy.SMMFuzzy()

        self.belief_state = {}  # the belief state output by the SMM
        self.agent_name = 0

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
    
    # updates the model by filtering state visibility and shunting over to the model
    def update(self, state):
        state = copy.deepcopy(state)
        state = self.filter_visibility(state)
        self.belief_state = self.model.update(state)

    # filter out objects and agents that are not immediately visible
    def filter_visibility(self, state):
        agent_position = state["state"]["players"][self.agent_name]["position"]

        # filter out objects
        for i, o in enumerate(state["state"]["objects"]):
            dX = o["position"][0] - agent_position[0]
            dY = o["position"][1] - agent_position[1]
            if state["state"]["visibility"][o["position"][1]][o["position"][0]]:
                del state["state"]["objects"][i]
        
        # filter out other agents
        for i, a in enumerate(state["state"]["players"]):
            dX = a["position"][0] - agent_position[0]
            dY = a["position"][1] - agent_position[1]
            if state["state"]["visibility"][o["position"][1]][o["position"][0]]:
                del state["state"]["players"][i]
        
        return state
