import copy

class SMMPredicates:
    domain_knowledge = {
        "agents": {},  # each known agent has: at (x, y), capable [actions], perceivable [(location, proposition)]
        "objects": {},  # each object has: property [(attribute, state)]
        # "locations": {},  # locations where this agent can move: (x,y) boolean
        # "activities": {}  # 
    }
    agent_capabilities = {}   
    agent_and_task_states = {}
    norms_and_obligations = {}
    activities = {}
    functional_role_of_agents_in_teams = {}
    
    agent_name = 0

    def __init__(self):
        return
    
    def update(self, state):
        self.update_domain_knowledge(state)
        return self.domain_knowledge
    
    # can ignore this in the logical predicates
    def init_belief_state(self, layout):
        return

    # determines the agent's goal from the state
    def predict_goal(self, state, agent=0):
        recipe = {
            "pick up ingredient": ["A holding null", "Pot contains null"],
            "place ingredient into pot": ["A holding ingredient", "Pot cooking no"],
            "activate pot": ["Pot contains ingredients", "Pot cooking no"],
            "picking up dish": ["A holding null", "Pot cooking progress"],
            "wait for cooking": ["Pot cooking"],
            "place soup on dish": ["A holding dish", "Pot cooking complete"],
            "place soup on counter": ["A holding soup"],
        }

        # determine logical predicates from state
        predicates = []

        # first look at agent
        o = state["state"]["players"][agent]["held_object"]
        held_object = "null" if o is None else "dish" if o["name"] == "soup" and "+" not in o["name"] else "soup" if "soup" in o["name"] else "ingredient"
        predicates.append("A holding " + held_object)

        # next look at the pot
        for i, o in enumerate(state["state"]["objects"]):
            # get soups that are cooking
            if o["name"] == "soup" and "is_ready" in o:
                # if the soup is not ready and cook time is -1, ingredients are in pot
                if o["is_ready"] == False and o["cook_time"] == -1:
                    predicates.append("Pot cooking no")
                    if len(o["_ingredients"]) > 0:
                        predicates.append("Pot contains ingredients")
                    else:
                        predicates.append("Pot contains null")

        # now, find the most likely step
        step_scores = {}
        for step in recipe:
            step_scores[step] = 0
            for predicate in recipe[step]:
                if predicate in predicates:
                    step_scores[step] += 1
            
        max_step = max(step_scores, key = step_scores.get)
        return max_step
            
    # update the predicate if it already exists, otherwise insert it
    def updatePredicate(self, function, subject, attribute):
        # agents
        if subject[0] == "A":
            # add agent if agent has not been seen before
            if subject not in self.domain_knowledge["agents"]:
                self.domain_knowledge["agents"][subject] = {"at":"(-1,-1)", "facing":"(0,0)", "holding":None, "capableOf":[], "perceivable":{}}
            # at: update location (x,y)
            if function == "at":
                self.domain_knowledge["agents"][subject]["at"] = attribute
            # facing: update orientation (x,y)
            if function == "facing":
                self.domain_knowledge["agents"][subject]["facing"] = attribute
            # holding: update held objectID
            if function == "holding":
                self.domain_knowledge["agents"][subject]["holding"] = attribute
            # capable: update set of capable actions
            if function == "capableOf":
                self.domain_knowledge["agents"][subject]["capableOf"] = list(set(self.domain_knowledge["agents"][subject]["capableOf"] + [attribute]))
            # perceivable: update dictionary of situation:property
            if function == "perceivable":
                self.domain_knowledge["agents"][subject]["perceivable"][attribute[1]] = list(set(self.domain_knowledge["agents"][subject]["perceivable"][attribute[1]] + [attribute[0]]))
            # goal: update the agent's perceived goal
            if function == "goal":
                self.domain_knowledge["agents"][subject]["goal"] = attribute

        # objects
        if subject[0] == "O":
            # add object if object has not been seen yet
            if subject not in self.domain_knowledge["objects"]:
                self.domain_knowledge["objects"][subject] = {"at":"(-1,-1)", "propertyOf":{}}
            # at: update location (x,y)
            if function == "at":
                self.domain_knowledge["objects"][subject]["at"] = attribute
            # propertyOf: update dictionary of property:status
            if function == "propertyOf":
                self.domain_knowledge["objects"][subject]["propertyOf"][attribute[0]] = attribute[1]
            pass


    def update_domain_knowledge(self, state):
        # includes agents, objects, locations, activities,
        # and other domain-specific representations needed to model the task and environment

        agent_locations = {}  # reference for linking objects to players holding them

        # update agents, using the index in the state's player list as the agent ID
        for i, p in enumerate(state["state"]["players"]):
            agent_id = "A" + str(i)
            self.updatePredicate("at", agent_id, p["position"])
            self.updatePredicate("facing", agent_id, p["orientation"])
            agent_locations[p["position"]] = agent_id
            # add held objects
            if p["held_object"] is not None:
                o = p["held_object"]
                o["holder"] = agent_id
                # correct the object name from "dish" to "soup"
                o["name"] = "soup" if o["name"] == "dish" else o["name"]
                state["state"]["objects"].append(o)
            else:
                self.updatePredicate("holding", agent_id, None)

        # update objects, using matching
        matched_ids = self.match_objects(self.domain_knowledge["objects"], state["state"]["objects"])

        for i, object_id in enumerate(matched_ids):
            # if object is on the same tile as an agent, associate the holder
            if state["state"]["objects"][i]["position"] in agent_locations:
                self.updatePredicate("holding", agent_locations[state["state"]["objects"][i]["position"]], object_id)

            # if ID is a string, update known object
            if isinstance(object_id, str):
                self.add_object(object_id, state["state"]["objects"][i])
            # if ID is a dictionary, add new object
            if isinstance(object_id, dict):
                new_id = len(self.domain_knowledge["objects"]) + 1
                self.add_object("O" + str(new_id), state["state"]["objects"][i])

        # update location: this is the nav mesh of each agent, irrelevant for us at this point
        # update perceivable: all agents can perceive all objects in all conditions, should double for loop to add these
        # update knowsOf: knowing attributes of other agents and objects, should double for loop
        # update obligations: we aren't ordering agents, so ignore

        # update goals
        for i in range(len(state["state"]["players"])):
            agent_id = "A" + str(i)
            self.updatePredicate("goal", agent_id, self.predict_goal(state, i))

        return self.domain_knowledge
    

    # match objects of a class to their known
    # inputs:
    #   known_objects: list of known objects from the last time step
    #   objects: list of observed objects
    # returns a list of known object IDs associated with each object, or the new IDs for each object
    def match_objects(self, known_objects, objects):
        return self.closest_matching(known_objects, objects)
    

    # object matching by the closest match algorithm
    def closest_matching(self, known_objects, objects):
        ids = [None for _ in objects]
        completed_matches = []

        # will repeat until all objects have a match
        while len([x for x in ids if x is None]) > 0:
            hadChange = False  # indicates that this loop did not converge yet
            matches = {}  # map from known object ID to list of candidate objects and their distances
            # check each object for closest known object
            for i, o in enumerate(objects):
                # ignore matched objects
                if ids[i] is not None:
                    continue

                # correct the object name from "dish" to "soup"
                o["name"] = "soup" if o["name"] == "dish" else o["name"]

                # find the closest known object
                closest_k = None
                closest_k_dist = float("infinity")
                for k in known_objects:
                    # ignore known objects that have already been matched to
                    if known_objects[k]["propertyOf"]["id"] in completed_matches:
                        continue
                    # ignore objects of the wrong class
                    if known_objects[k]["propertyOf"]["name"] != o["name"]:
                        continue
                    # check if this known object is closer
                    dist = (known_objects[k]["at"][0] - o["position"][0]) * (known_objects[k]["at"][0] - o["position"][0]) + (known_objects[k]["at"][1] - o["position"][1]) * (known_objects[k]["at"][1] - o["position"][1])
                    if dist < closest_k_dist:
                        closest_k = known_objects[k]["propertyOf"]["id"]
                        closest_k_dist = dist

                # if no close matches, continue
                if closest_k is None:
                    continue

                # add to matches
                if closest_k not in matches:
                    matches[closest_k] = []
                matches[closest_k].append([closest_k_dist, i])
            
            # set 1-1 matches, resolve conflicts by choosing closest
            for m in matches:
                if len(matches[m]) == 1:
                    ids[matches[m][0][1]] = m
                    completed_matches.append(m)
                    hadChange = True
                if len(matches[m]) > 1:
                    min_idx = min(matches[m], key = lambda x : x[0])[1]
                    ids[min_idx] = m 
                    completed_matches.append(m)
                    hadChange = True
        
            # if no changes to environment, exit and register new objects
            if not hadChange:
                break

        # register unassigned objects as new
        for l in [(i, objects[i]) for i, x in enumerate(ids) if x is None]:
            ids[l[0]] = l[1]

        return ids


    # adds an object's predicates
    def add_object(self, object_id, o):
        object_title = object_id + "-" + o["name"] + (":" + "+".join([x["name"] for x in o["_ingredients"]]) if "_ingredients" in o else "")
        self.updatePredicate("at", object_id, o["position"])
        self.updatePredicate("propertyOf", object_id, ("id", object_id))
        self.updatePredicate("propertyOf", object_id, ("title", object_title))
        self.updatePredicate("propertyOf", object_id, ("name", o["name"]))
        self.updatePredicate("propertyOf", object_id, ("holder", o["holder"] if "holder" in o else None))
        self.updatePredicate("propertyOf", object_id, ("cookTime", o["cook_time"] if "cook_time" in o else -1))
        self.updatePredicate("propertyOf", object_id, ("isCooking", o["is_cooking"] if "is_cooking" in o else False))
        self.updatePredicate("propertyOf", object_id, ("isReady", o["is_ready"] if "is_ready" in o else False))
        self.updatePredicate("propertyOf", object_id, ("isIdle", o["is_idle"] if "is_idle" in o else False))
        return object_id
