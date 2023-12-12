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
    
    # set up the known appliances
    def init_belief_state(self, layout):
        # create objects for the appliances and ingredients
        for row_idx in range(len(layout)):
            for col_idx in range(len(layout[0])):
                if layout[row_idx][col_idx] == "P":  # pot
                    self.add_object(None, {"name": "pot", "position": [col_idx, row_idx]})
                if layout[row_idx][col_idx] == "S":  # station
                    self.add_object(None, {"name": "station", "position": [col_idx, row_idx]})
        return

    # gets an ingredient list from an object
    def get_ingredient_list(self, object_id):
        if ":" not in self.domain_knowledge["objects"][object_id]["propertyOf"]["title"]:
            return []
        return self.domain_knowledge["objects"][object_id]["propertyOf"]["title"].split(":")[1].split("+")
    
    # determines whether an object is on a pot spot
    def on_pot(self, object_id):
        return len([x for x in self.domain_knowledge["objects"] if self.domain_knowledge["objects"][x]["propertyOf"]["name"] == "pot" and self.domain_knowledge["objects"][x]["at"] == self.domain_knowledge["objects"][object_id]["at"]]) > 0

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
                self.domain_knowledge["objects"][subject] = {"at":"(-1,-1)", "contains":[], "canUseWith":[], "visible":True, "propertyOf":{}}
            # at: update location (x,y)
            if function == "at":
                self.domain_knowledge["objects"][subject]["at"] = attribute
            # visible: update location (x,y)
            if function == "visible":
                self.domain_knowledge["objects"][subject]["visible"] = attribute
            # contains: update contains object
            if function == "contains":
                if attribute not in self.domain_knowledge["objects"][subject]["contains"]:
                    self.domain_knowledge["objects"][subject]["contains"].append(attribute)
            # notcontains: update contains object
            if function == "notcontains":
                if attribute in self.domain_knowledge["objects"][subject]["contains"]:
                    self.domain_knowledge["objects"][subject]["contains"].remove(attribute)
            # propertyOf: update dictionary of property:status
            if function == "propertyOf":
                self.domain_knowledge["objects"][subject]["propertyOf"][attribute[0]] = attribute[1]
            # canUseWith: update dictionary of obj:usability [0-1]
            if function == "canUseWith":
                if attribute not in self.domain_knowledge["objects"][subject]["canUseWith"]:
                    self.domain_knowledge["objects"][subject]["canUseWith"].append(attribute)
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

        # update usability between objects, inefficient n^2 algorithm but our environment size is pretty small
        for i, object_from in enumerate(self.domain_knowledge["objects"]):
            for j, object_to in enumerate(self.domain_knowledge["objects"]):
                # can never use an object with itself
                if i == j:
                    self.updatePredicate("canUseWith", object_from, [object_to, 0])
                # ingredients can be used on unfilled pots
                elif self.domain_knowledge["objects"][object_from]["propertyOf"]["name"] in ["onion", "tomato"] and \
                     self.domain_knowledge["objects"][object_to]["propertyOf"]["name"] == "pot" and \
                     not self.domain_knowledge["objects"][object_to]["propertyOf"]["isCooking"] and \
                     not self.domain_knowledge["objects"][object_to]["propertyOf"]["isReady"] and \
                     not self.domain_knowledge["objects"][object_to]["propertyOf"]["isIdle"]:
                    self.updatePredicate("canUseWith", object_from, [object_to, 1])
                # dished can be used on filled pots
                elif self.domain_knowledge["objects"][object_from]["propertyOf"]["name"] == "soup" and \
                     len(self.get_ingredient_list(object_from)) == 0 and \
                     self.domain_knowledge["objects"][object_to]["propertyOf"]["name"] == "soup" and \
                     not self.domain_knowledge["objects"][object_to]["propertyOf"]["isCooking"] and \
                     self.domain_knowledge["objects"][object_to]["propertyOf"]["isReady"] and \
                     self.on_pot(object_to):
                    #  self.domain_knowledge["objects"][object_to]["propertyOf"]["isIdle"]:
                    print("Dish can be used with pot", object_from, object_to)
                    self.updatePredicate("canUseWith", object_from, [object_to, 1])
                # soups can be used on stations
                elif self.domain_knowledge["objects"][object_from]["propertyOf"]["name"] == "soup" and \
                     len(self.get_ingredient_list(object_from)) == 3 and \
                     self.domain_knowledge["objects"][object_from]["propertyOf"]["isReady"] and \
                     self.domain_knowledge["objects"][object_to]["propertyOf"]["name"] == "station":
                    print("Soup can be used with station", object_from, object_to)
                    self.updatePredicate("canUseWith", object_from, [object_to, 1])
                # by default, cannot use
                else:
                    self.updatePredicate("canUseWith", object_from, [object_to, 0])

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
        completed_matches = []  # objects with completed matches

        # ignore invisible (discarded) objects
        _known_objects = {k : known_objects[k] for k in known_objects if known_objects[k]["visible"]}

        # the naive case: objects have exact name/location matches, does not work for moved or transformed objects
        for i, o in enumerate(objects):
            # ignore matched objects
            if ids[i] is not None:
                continue

            # correct the object name from "dish" to "soup"
            o["name"] = "soup" if o["name"] == "dish" else o["name"]

            # check if the object matches a known object's name and position
            for k in _known_objects:
                # ignore objects of the wrong name
                if _known_objects[k]["propertyOf"]["name"] != o["name"]:
                    continue
                # save if this known object has the same position
                if _known_objects[k]["at"] == o["position"]:
                    # if a soup, check if ingredients match
                    if _known_objects[k]["propertyOf"]["name"] == "soup":
                        # if ingredients dont match, ignore
                        if "_ingredients" in o and ":" in _known_objects[k]["propertyOf"]["title"] and _known_objects[k]["propertyOf"]["title"].split(":")[1].split("+") != [x["name"] for x in o["_ingredients"]]:
                            # print("XXX soups don't match", known_objects[k]["propertyOf"]["title"].split(":")[1].split("+"), "of known", [x["name"] for x in o["_ingredients"]])
                            continue
                    ids[i] = k
                    completed_matches.append(k)
                    break
        
        # the next cases will repeat until all objects have a match
        while len([x for x in ids if x is None]) > 0:
            hadChange = False  # indicates that this loop did not converge yet
            matches = {}  # map from known object ID to list of candidate objects and their distances, used as an intermediary to the completed_matches

            # the closest match case: objects have exact name and closest location, does not work for transformed objects (ingredients -> soup)
            for i, o in enumerate(objects):
                # ignore matched objects
                if ids[i] is not None:
                    continue

                # find the closest known object
                closest_k = None
                closest_k_dist = float("infinity")
                for k in _known_objects:
                    # ignore known objects that have already been matched to
                    if _known_objects[k]["propertyOf"]["id"] in completed_matches:
                        continue
                    # ignore objects of the wrong class
                    if _known_objects[k]["propertyOf"]["name"] != o["name"]:
                        continue
                    # if soup, ignore if ingredients are different
                    if _known_objects[k]["propertyOf"]["name"] == "soup":
                        if ":" in _known_objects[k]["propertyOf"]["title"] and "_ingredients" in o and _known_objects[k]["propertyOf"]["title"].split(":")[1].split("+") != [x["name"] for x in o["_ingredients"]]:
                            # print("YYY soups don't match", o, "of known", known_objects[k])
                            continue
                    # check if this known object is closer
                    dist = (_known_objects[k]["at"][0] - o["position"][0]) * (_known_objects[k]["at"][0] - o["position"][0]) + (_known_objects[k]["at"][1] - o["position"][1]) * (_known_objects[k]["at"][1] - o["position"][1])
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
            
            # set 1-1 matches, resolve conflicts by choosing closest object
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

        # objects that have not been matched have likely transformed, check for those transformations
        unmatched_seen_objects = [(i, objects[i]) for i, x in enumerate(ids) if x is None]  # seen objects that have not been matched
        unmatched_known_objects = [k for k in known_objects if k not in completed_matches and known_objects[k]["propertyOf"]["name"] not in ["pot", "station"] and known_objects[k]["visible"]]  # known objects that have not been matched

        # check for ingredients that have become soups
        for k in unmatched_known_objects:  # for each unmatched known object
            # check for a soup in the seen objects
            for o in unmatched_seen_objects:
                if o[1]["name"] == "soup":
                    # check if the soup contains the ingredient
                    # NOTE: we can improve this by keeping track of the ingredients in soups 
                    if "_ingredients" in o[1] and \
                        len(o[1]["_ingredients"]) > 0 and \
                        known_objects[k]["propertyOf"]["name"] in [x["name"] for x in o[1]["_ingredients"]]:

                        # match the objects by moving the known object to the seen object
                        known_objects[k]["at"] = o[1]["position"]
                        self.updatePredicate("contains", k, o[0])
                        print("I believe object", k, known_objects[k]["propertyOf"]["name"], "has become a soup", o)
                        # remove the object from the known objects
                        self.updatePredicate("visible", k, False)
                        break

        # check for soups that have been turned in to the station
        unmatched_known_objects = [k for k in known_objects if k not in completed_matches and known_objects[k]["propertyOf"]["name"] not in ["pot", "station"] and known_objects[k]["visible"]]  # known objects that have not been matched

        for k in unmatched_known_objects:  # for each unmatched known object
            # if the unmatched known object is still unmatched, and a soup, it's probably been turned in
            if known_objects[k]["propertyOf"]["name"] == "soup" and known_objects[k]["propertyOf"]["isReady"] == True:
                # assign the object to any station
                for k2 in known_objects:
                    if known_objects[k2]["propertyOf"]["name"] == "station":
                        print("moving soup to station", k, k2)
                        self.updatePredicate("at", k, known_objects[k2]["at"])
                        self.updatePredicate("visible", k, False)
                        break
        
        _known_objects = {k : known_objects[k] for k in known_objects if known_objects[k]["visible"]}  # ignore invisible (discarded) objects
        unmatched_known_objects = [k for k in known_objects if k not in completed_matches and known_objects[k]["propertyOf"]["name"] not in ["pot", "station"]]  # known objects that have not been matched

        # register unassigned objects as new
        for l in [(i, objects[i]) for i, x in enumerate(ids) if x is None]:
            print("adding new object", l[0], l[1])
            ids[l[0]] = l[1]

        return ids


    # adds an object's predicates
    def add_object(self, object_id, o):
        # if the object ID is none, pick one
        if object_id is None:
            object_id = "O" + str(len(self.domain_knowledge["objects"]) + 1)
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
