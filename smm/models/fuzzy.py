import copy
import ast

class SMMFuzzy:
    def __init__(self):
        self.S = ["human move up",
                  "human move right",
                  "human move down", 
                  "human move left",
                  "human pick tomato",
                  "human pick onion",
                  "human place",
                  "human activate pot",

                  "robot move up",
                  "robot move right",
                  "robot move down",
                  "robot move left",
                  "robot pick tomato",
                  "robot pick onion",
                  "robot place",
                  "robot activate pot"
                  ]  # finite set of input events (human actions, environmental events, etc.) that can cause a change in system state that are observable by a person
        
        self.Q = {}  # finite set of states the person thinks the system is in
        self.Q_template = {
            "agent": {
                "position": [-1,-1],
                "holding": "",
                "going to": [-1,-1],
                "goal": ""
            },
            "pot": {
                "position": [-1,-1],
                "contains": [],
                "cooking": False,
                "cooked": False
            }
        }

        self.I = []  # set of all possible vectors of fuzzy membership values of input events from S, each entry in an element i is the degree to which the person thinks the associated event has occured
        self.M = []  # set of all possible vectors of fuzzy membership values of each state from Q, each entry in an element m is the degree to which the person thinks the system is in the associated state of Q
        return

    def update(self, state):
        self.update_fuzzy_mental_model(state)
        return self.Q

    def get_next_possible_states(self):
        # not sure if this is necessary, my thought was to consider all possible states from the current state, HOWEVER this can lead to impossible jumps
        return

    # initialize Q
    def init_belief_state(self, layout):
        self.Q = {}
        for row_id in range(len(layout)):
            for col_id in range(len(layout[row_id])):
                letter = layout[row_id][col_id]
                # if letter is an agent
                if letter.isdigit():
                    # copy the template
                    self.Q["A" + letter] = self.copy_template("agent")
                    # set the location params, we have no other information to initialize
                    self.Q["A" + letter]["position"] = [row_id, col_id]
                    self.Q["A" + letter]["going to"] = [row_id, col_id]
                # if letter is a pot
                if letter == "P":
                    # copy the template
                    self.Q["P" + letter] = self.copy_template("pot")
                    # set the location params, we have no other information to initialize
                    self.Q["P" + letter]["position"] = [row_id, col_id]
        print("initial Q", self.Q)
        return self.Q

    def copy_template(self, _class):
        return {k : self.Q_template[_class][k] if not isinstance(self.Q_template[_class][k], list) else [x for x in self.Q_template[_class][k]] for k in self.Q_template[_class]}

    # function mapping S -> I, describing how inputs are fuzzified by mapping crisp input events from S to a vector of input fuzzy set memberships from I
    def alpha(self, input_event):
        # in our case an observed input is always going to happen
        self.I = [0 if x == input_event else 1 for x in self.X]
        return self.I

    # function mapping Q, S -> M, describes the fuzzification of state transitions (degree to which the person thinks that a given state and input will transition to another given state), so degree to which the person thinks the machine will be in each state of Q in the next state following input event s when the machine is in state q
    def phi(self, input_event):
        self.M_new = copy.deepcopy(self.M)  # M is the belief state, Q is the actual state
        # we think the user will be less likely to notice events further away from their character
        # if "robot" in input_event:
            # chance_event_was_seen = self.Q["agents"][self.robot_id]["position"] - 
        self.Q
        self.S
    
    # function mapping M, S -> M the next state, uses alpha and phi to describe how a given vector of fuzzy state memberships will change in response to an input event
    def delta(self):
        self.M
        self.S
        result = 0 # m_prime where for all m_prime_x in m_prime, m_prime_x = 1 - product sum of (m_y * s_z * phi(y,z)_x) for all m_y in m, s_z in alpha(s)

    def update_fuzzy_mental_model(self, input):
        return

smm = SMMFuzzy()
print("Q", smm.Q)