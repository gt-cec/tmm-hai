import copy

class SMMPredicates:
    def __init__(self, can_see = None):
        self.domain_knowledge = {
            "agents": {},  # each known agent has: at (x, y), capable [actions], perceivable [(location, proposition)]
            "objects": {},  # each object has: property [(attribute, state)]
            # "locations": {},  # locations where this agent can move: (x,y) boolean
            # "activities": {}  # 
        }
        self.agent_capabilities = {}   
        self.agent_and_task_states = {}
        self.norms_and_obligations = {}
        self.activities = {}
        self.functional_role_of_agents_in_teams = {}
        self.agent_name = "A0"
        self.can_see = can_see
        return
    
    def update(self, state:dict, debug=False):
        self.update_domain_knowledge(state=state, debug=debug)
        return self.domain_knowledge
    
    # set up the known appliances
    def init_belief_state(self, layout:dict):
        # create objects for the appliances and ingredients
        for row_idx in range(len(layout)):
            for col_idx in range(len(layout[0])):
                if layout[row_idx][col_idx] == "P":  # pot
                    self.update_object(None, {"position": (col_idx, row_idx), "propertyOf": {"name": "pot"}}, new_object=True)
                if layout[row_idx][col_idx] == "S":  # station
                    self.update_object(None, {"position": (col_idx, row_idx), "propertyOf": {"name": "station"}}, new_object=True)
        return

    # gets an ingredient list from an object
    def get_ingredient_list(self, object_id=None, obj=None):
        if object_id is not None:
            obj = self.domain_knowledge["objects"][object_id]
        if obj is None:
            raise ValueError("When the object_id parameter is not given (pulling from domain_knowledge), the obj parameter must be (pulling from a custom object, like known_objects)!")
        if "ingredients" not in obj["propertyOf"]:
            return []
        return [x["propertyOf"]["name"] for x in obj["propertyOf"]["ingredients"]]
    
    # determines whether an object is on a pot spot
    def on_pot(self, object_id):
        return len([x for x in self.domain_knowledge["objects"] if self.domain_knowledge["objects"][x]["propertyOf"]["name"] == "pot" and self.domain_knowledge["objects"][x]["position"] == self.domain_knowledge["objects"][object_id]["position"]]) > 0

    # determines whether an object is on a soup spot
    def on_soup(self, object_id):
        return len([x for x in self.domain_knowledge["objects"] if self.domain_knowledge["objects"][x]["propertyOf"]["name"] == "soup" and self.domain_knowledge["objects"][x]["position"] == self.domain_knowledge["objects"][object_id]["position"]]) > 0

    # determines the agent's goal from the state
    def predict_goal(self, state, agent_id=0):
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
        o = state["agents"][agent_id]["holding"]
        # if the held object is a string, use the corresponding known object
        if isinstance(o, str):
            o = self.domain_knowledge["objects"][o]
        held_object = "null" if o is None else "dish" if o["propertyOf"]["name"] == "soup" and "+" not in o["propertyOf"]["name"] else "soup" if "soup" in o["propertyOf"]["name"] else "ingredient"
        predicates.append("A holding " + held_object)

        # next look at the pot
        for o in state["objects"]:
            # get soups that are cooking
            if state["objects"][o]["propertyOf"]["name"] == "soup" and "is_ready" in state["objects"][o]["propertyOf"]:
                # if the soup is not ready and cook time is -1, ingredients are in pot
                if state["objects"][o]["propertyOf"]["isReady"] == False and state["objects"][o]["propertyOf"]["cookTime"] == -1:
                    predicates.append("Pot cooking no")
                    if len(state["objects"][o]["propertyOf"]["ingredients"]) > 0:
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
                self.domain_knowledge["agents"][subject] = {"position":"(-1,-1)", "facing":"(0,0)", "holding":None, "capableOf":[], "perceivable":{}}
            # at: update location (x,y)
            if function == "position":
                self.domain_knowledge["agents"][subject]["position"] = attribute
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
                self.domain_knowledge["objects"][subject] = {"position":"(-1,-1)", "contains":[], "canUseWith":{}, "visible":True, "propertyOf":{}}
            # at: update location (x,y)
            if function == "position":
                self.domain_knowledge["objects"][subject]["position"] = attribute
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
                self.domain_knowledge["objects"][subject]["canUseWith"][attribute[0]] = attribute[1]
                
            pass


    def update_domain_knowledge(self, state, debug=False):
        # includes agents, objects, locations, activities,
        # and other domain-specific representations needed to model the task and environment

        agent_locations = {}  # reference for linking objects to players holding them
        # update agents, using the index in the state's player list as the agent ID
        for agent_id in state["agents"]:
            self.updatePredicate("position", agent_id, state["agents"][agent_id]["position"])
            self.updatePredicate("facing", agent_id, state["agents"][agent_id]["facing"])
            agent_locations[str(state["agents"][agent_id]["position"])] = agent_id
            # add held objects
            if state["agents"][agent_id]["holding"] is not None:
                obj = state["agents"][agent_id]["holding"]
                # if the held object is a string (object ID), update that predicate
                if isinstance(obj, str):
                    # if the object is seen, directly update it
                    if obj in state["objects"]:
                        state["agents"][agent_id]["holding"] = state["objects"][obj]
                        self.updatePredicate("holding", agent_id, state["objects"][obj])
                    # otherwise, update the position of the corresponding known object
                    else:
                        self.updatePredicate("position", obj, state["agents"][agent_id]["position"])
                # if the held object is a dictionary, create a new object
                elif isinstance(obj, dict):
                    obj_id = "O" + str(len(state["objects"]) + 1)
                    state["objects"][obj_id] = obj
                    self.updatePredicate("holding", agent_id, obj)
                else:
                    raise ValueError("Object held by an agent was not a string nor a dictionary.")
                
            else:
                self.updatePredicate("holding", agent_id, None)

        # update objects, using matching
        matched_ids = self.match_objects(self.domain_knowledge["objects"], state["objects"], debug=debug)
        for object_id in matched_ids:
            # if ID is a string, update known object
            if isinstance(matched_ids[object_id], str):
                # print("  Updating seen object", object_id, "to known", matched_ids[object_id], "known", self.domain_knowledge["objects"][matched_ids[object_id]], "and seen", state["objects"][object_id])
                self.update_object(matched_ids[object_id], state["objects"][object_id])
                
            # if ID is None, add new object
            elif matched_ids[object_id] is None:
                if debug:
                    print("  Adding new object", object_id, state["objects"][object_id]["propertyOf"]["name"])
                self.update_object(None, state["objects"][object_id], new_object=True)
            else:
                raise ValueError("PREDICATES: Object ID is not None (new object) or string (existing object)!", matched_ids)

            # if object is visible and on the same tile as an agent, associate the holder
            if matched_ids[object_id] is not None and self.domain_knowledge["objects"][matched_ids[object_id]]["visible"] and str(state["objects"][object_id]["position"]) in agent_locations:
                self.updatePredicate("holding", agent_locations[str(state["objects"][object_id]["position"])], matched_ids[object_id])

        # update usability between objects, inefficient n^2 algorithm but our environment size is pretty small
        for i, object_from in enumerate(self.domain_knowledge["objects"]):
            for j, object_to in enumerate(self.domain_knowledge["objects"]):
                # can never use an object with itself
                if i == j:
                    self.updatePredicate("canUseWith", object_from, [object_to, 0])
                # ingredients can be used on unfilled pots
                elif self.domain_knowledge["objects"][object_from]["propertyOf"]["name"] in ["onion", "tomato"] and \
                     self.domain_knowledge["objects"][object_to]["propertyOf"]["name"] == "soup" and \
                     len(self.get_ingredient_list(object_to)) < 3:
                        self.updatePredicate("canUseWith", object_from, [object_to, 1])
                # soups can be used on stations
                elif self.domain_knowledge["objects"][object_from]["propertyOf"]["name"] == "soup" and \
                     len(self.get_ingredient_list(object_from)) == 3 and \
                     self.domain_knowledge["objects"][object_from]["propertyOf"]["isReady"] and \
                     self.domain_knowledge["objects"][object_to]["propertyOf"]["name"] == "station":
                    self.updatePredicate("canUseWith", object_from, [object_to, 1])
                # ingredients can be used on empty pots
                elif self.domain_knowledge["objects"][object_from]["propertyOf"]["name"] in ["onion", "tomato"] and \
                     self.domain_knowledge["objects"][object_to]["propertyOf"]["name"] == "pot" and \
                     not self.on_soup(object_to):
                        self.updatePredicate("canUseWith", object_from, [object_to, 1])
                # dishes can be used on filled pots
                elif self.domain_knowledge["objects"][object_from]["propertyOf"]["name"] == "dish" and \
                     len(self.get_ingredient_list(object_from)) == 0 and \
                     self.domain_knowledge["objects"][object_to]["propertyOf"]["name"] == "soup" and \
                     self.domain_knowledge["objects"][object_to]["propertyOf"]["isReady"] and \
                     self.on_pot(object_to):
                    self.updatePredicate("canUseWith", object_from, [object_to, 1])
                
                # by default, cannot use
                else:
                    self.updatePredicate("canUseWith", object_from, [object_to, 0])

        # update location: this is the nav mesh of each agent, irrelevant for us at this point
        # update perceivable: all agents can perceive all objects in all conditions, should double for loop to add these
        # update knowsOf: knowing attributes of other agents and objects, should double for loop
        # update obligations: we aren't ordering agents, so ignore

        # update goals
        for agent_id in state["agents"]:
            self.updatePredicate("goal", agent_id, self.predict_goal(state, agent_id))

        return self.domain_knowledge
    

    # match objects of a class to their known
    # inputs:
    #   known_objects: list of known objects from the last time step
    #   objects: observed state objects
    #   debug: whether to print debug statements
    # returns a list of known object IDs associated with each object, or the new IDs for each object
    def match_objects(self, known_objects, objects, debug=False):
        return self.closest_matching(known_objects, objects, debug=debug)

    # object matching by the closest match algorithm
    def closest_matching(self, known_objects, objects, debug=False):
        # ignore invisible (discarded) objects
        known_objects = {k : known_objects[k] for k in known_objects if known_objects[k]["visible"]}
        
        ids = {k : None for k in objects}  # object index to known object name so we can match objects -> known object name
        completed_matches = {x : None for x in known_objects}  # known object index to object index so we can match known object name[known object index] -> object index
        
        if debug:
            print("[Start] Seen Objects:", [objects[o]["propertyOf"]["name"] + (":" + "+".join([x["propertyOf"]["name"] for x in objects[o]["propertyOf"]["ingredients"]]) if "ingredients" in objects[o]["propertyOf"] else "") + " at " + str(objects[o]["position"]) for o in objects])
            print("[Start] Known Objects:", [known_objects[k]["propertyOf"]["title"] + " at " + str(known_objects[k]["position"]) for k in known_objects])
        if len(str([known_objects[k]["propertyOf"]["title"] + " at " + str(known_objects[k]["position"]) for k in known_objects]).split("soup")) > 2:
        #     # print("[DEBUG] Known Objects:", [k + " " + known_objects[k]["propertyOf"]["title"] + " at " + str(known_objects[k]["position"]) for k in known_objects])
            pass

        soups_delta_ingredients = {}  # soups that have stayed in the same location but now have ingredients to be assigned

        # the naive case: objects have exact name/location matches, does not work for moved or transformed objects
        for o in objects:
            # ignore matched objects
            if ids[o] is not None:
                continue

            # check if the object matches a known object's name and position
            for k in known_objects:
                # ignore objects of the wrong name
                if known_objects[k]["propertyOf"]["name"] != objects[o]["propertyOf"]["name"]:
                    continue
                # save if this known object has the same position
                if known_objects[k]["position"] == objects[o]["position"]:
                    # if a soup, check if ingredients match
                    if known_objects[k]["propertyOf"]["name"] == "soup":
                        # if matching a seen object soup and we already have it in the soup ingredients delta record, ignore because we have already matched it
                        if objects[o]["propertyOf"]["name"] == "soup" and k in soups_delta_ingredients:
                            continue
                        known_soup_ingredients = self.get_ingredient_list(obj=known_objects[k])
                        object_soup_ingredients = self.get_ingredient_list(obj=objects[o])
                        # ignore if known object has ingredients and this one does not
                        if known_soup_ingredients == []:
                            if debug:
                                print("    Skipping soup", k, "because it has no ingredients:", known_objects[k])
                            continue
                        if debug:
                            print("    Looking at soup with ingredients", known_soup_ingredients)
                        if object_soup_ingredients != known_soup_ingredients:
                            # if the known soup has ingredients that are not in the object soup, they must be different
                            incompatible_soups = False
                            delta_ingredients = [x for x in object_soup_ingredients]
                            for ing in known_soup_ingredients:
                                if ing not in delta_ingredients:
                                    incompatible_soups = True
                                    if debug:
                                        print("    Soups are incompatible, known soup ingredients:", known_soup_ingredients, "; object soup ingredients:", object_soup_ingredients)
                                    break
                                else:
                                    delta_ingredients.remove(ing)  # remove the ingredient from the object soup ingredients so we are left with a delta ingredients (object soup - known soup)
                            if incompatible_soups:
                                continue
                            
                            # add the delta ingredients to the soups that added ingredients
                            soups_delta_ingredients[k] = delta_ingredients
                        elif "ingredients" in objects[o]["propertyOf"] and debug:
                            print("    Naive case: soups match, known", known_objects[k], "and seen object", o)
                    ids[o] = k
                    completed_matches[k] = o
                    if debug:
                        # print("   matched known object", known_objects[k]["propertyOf"]["name"], "position", known_objects[k]["position"], "with seen object", objects[o]["propertyOf"]["name"], "position", objects[o]["position"])
                        pass
                    break

        unmatched_seen_objects = [seen_obj_id for seen_obj_id in ids if ids[seen_obj_id] is None]  # seen objects that have not been matched
        unmatched_known_objects = [known_obj_id for known_obj_id in known_objects if completed_matches[known_obj_id] is None and known_objects[known_obj_id]["propertyOf"]["name"] not in ["pot", "station"]]  # known objects that have not been matched
        
        if debug:
            print("[After naive] Unmatched Known Objects:", [known_objects[k]["propertyOf"]["title"] + " was at " + str(known_objects[k]["position"]) for k in unmatched_known_objects])
            print("[After naive] Unmatched Seen Objects:", [objects[o]["propertyOf"]["name"] + (":" + "+".join([x["propertyOf"]["name"] for x in objects[o]["propertyOf"]["ingredients"]]) if "ingredients" in objects[o]["propertyOf"] else "") + " " + str(objects[o]["position"]) for o in unmatched_seen_objects])

        # the next case, match items that are held by agents
        for o in unmatched_seen_objects:
            if "holder" in objects[o]["propertyOf"] and objects[o]["propertyOf"]["holder"] is not None:
                if debug:
                    print("    Found unmatched seen held object", o, objects[o]["propertyOf"]["name"], "at", objects[o]["position"], "will try to match to known previously held object")

                # if linking soup to a held dish, link the dish to the soup and make the dish invisible
                if objects[o]["propertyOf"]["name"].startswith("soup"):
                    for k in unmatched_known_objects:
                        if known_objects[k]["propertyOf"]["name"] != "dish":  # ignore non-dishes
                            continue
                        if debug:
                            print("        dish!", known_objects[k], objects[o])
                        completed_matches[k] = o  # the dish is part of the soup
                        self.updatePredicate("visible", k, False)  # hide the dish  
                        # this must have previously used a soup, so find the closest known soup with ingredients that don't conflict
                        closest_k = None
                        closest_k_dist = float("inf")
                        for _k in unmatched_known_objects:
                            if known_objects[_k]["propertyOf"]["name"] == "soup" and known_objects[_k]["propertyOf"]["holder"] is None:  # if the known object is a soup that was not held
                                no_incorrect_ingredients = True
                                seen_ingredients = [x["propertyOf"]["name"] for x in objects[o]["propertyOf"]["ingredients"]]
                                for ing_name in self.get_ingredient_list(obj=known_objects[_k]):  # check if any known ingredients are conflicting
                                    if ing_name in seen_ingredients:
                                        seen_ingredients.remove(ing_name)
                                    else:
                                        no_incorrect_ingredients = False
                                        break
                                if no_incorrect_ingredients:  # check if distance is shorter
                                    dist = self.distance(known_objects[_k], objects[o])
                                    if dist < closest_k_dist:
                                        closest_k = _k
                                        closest_k_dist = dist
                        if closest_k is None:
                            pass
                            # raise ValueError("Could not find a known soup that this dish+soup could have come from!")
                        else:  # if a match was found, link them together
                            ids[o] = closest_k
                            completed_matches[closest_k] = o

                else:  # if not a soup, find the closest object with the same holder, note that ingredients taken out of range will retain their owner, hence the "closest" object
                    closest_k = None
                    closest_k_dist = float("infinity")
                    for k in unmatched_known_objects:
                        if known_objects[k]["propertyOf"]["name"] != objects[o]["propertyOf"]["name"]:  # only link if they have the same name
                            continue
                        dist = self.distance(known_objects[k], objects[o])
                        if dist < closest_k_dist:  # consider the known object a potential match if the holder is the same, or the object should be in visible range
                            if "holder" in known_objects[k]["propertyOf"] and known_objects[k]["propertyOf"]["holder"] is not None and objects[o]["propertyOf"]["holder"] != known_objects[k]["propertyOf"]["holder"]:  # ignore if known object has a holder and the holder is not the same
                                continue
                            agent = self.domain_knowledge["agents"][self.agent_name]
                            if ("holder" not in known_objects[k]["propertyOf"] or known_objects[k]["propertyOf"]["holder"] is None) and \
                                not self.can_see(agent["facing"], agent["position"][0] - known_objects[k]["position"][0], agent["position"][1] - known_objects[k]["position"][1]): # ignore if the object has no holder and the object is also not visible
                                continue
                            closest_k = k
                            closest_k_dist = dist
                            continue

                    if debug:
                        print("    Found a match! Linking object", o, "to known object", known_objects[k]["propertyOf"]["title"])                                                      
                    ids[o] = closest_k
                    completed_matches[closest_k] = o

        unmatched_seen_objects = [seen_obj_id for seen_obj_id in ids if ids[seen_obj_id] is None]  # seen objects that have not been matched
        unmatched_known_objects = [known_obj_id for known_obj_id in known_objects if completed_matches[known_obj_id] is None and known_objects[known_obj_id]["propertyOf"]["name"] not in ["pot", "station"]]  # known objects that have not been matched

        if debug:
            print("[After held+moved items] Unmatched Known Objects:", [known_objects[k]["propertyOf"]["title"] + " was at " + str(known_objects[k]["position"]) for k in unmatched_known_objects])
            print("[After held+moved items] Unmatched Seen Objects:", [objects[o]["propertyOf"]["name"] + (":" + "+".join([x["propertyOf"]["name"] for x in objects[o]["propertyOf"]["ingredients"]]) if "ingredients" in objects[o]["propertyOf"] else "") for o in unmatched_seen_objects])

        # the next cases will repeat until all moved objects have a match
        while len([x for x in ids if ids[x] is None]) > 0:
            hadChange = False  # indicates that this loop did not converge yet
            matches = {}  # map from known object ID to list of candidate objects and their distances, used as an intermediary to the completed_matches

            # the closest match case: objects have exact name and closest location, does not work for transformed objects (ingredients -> soup)
            for o in unmatched_seen_objects:
                if debug:
                    print("   Checking unmatched seen:", o, "matched?", ids[o])
                # ignore matched objects
                if ids[o] is not None:
                    continue

                # find the closest unmatched known object
                closest_k = None
                closest_k_dist = float("infinity")
                for k in unmatched_known_objects:
                    # ignore known objects that have already been matched to
                    if known_objects[k]["propertyOf"]["id"] in completed_matches and completed_matches[known_objects[k]["propertyOf"]["id"]] is not None:
                        if debug:
                            print("   Known object", k, "is actually already matched to", completed_matches[known_objects[k]["propertyOf"]["id"]])
                        continue
                    # ignore objects of the wrong class
                    if known_objects[k]["propertyOf"]["name"] != objects[o]["propertyOf"]["name"]:
                        if debug:
                            print("    Wrong name, known is", known_objects[k]["propertyOf"]["name"], "while this is", objects[o]["propertyOf"]["name"])
                        continue
                    # if soup, ignore if ingredients are different
                    if known_objects[k]["propertyOf"]["name"] == "soup":
                        # ignore if known object has ingredients and this one does not
                        if ":" in known_objects[k]["propertyOf"]["title"] and "ingredients" not in objects[o]["propertyOf"]:
                            continue
                        # ignore if this object has ingredients and the known one does not
                        if ":" not in known_objects[k]["propertyOf"]["title"] and "ingredients" in objects[o]["propertyOf"]:
                            continue
                        # ignore if ingredients do not match
                        if ":" in known_objects[k]["propertyOf"]["title"] and "ingredients" in objects[o]["propertyOf"] and known_objects[k]["propertyOf"]["title"].split(":")[1].split("+") != [x["propertyOf"]["name"] for x in objects[o]["propertyOf"]["ingredients"]]:
                            continue
                        if debug:
                            print("SOUP", known_objects[k]["propertyOf"]["title"], "object is", objects[o]["propertyOf"]["name"])
                    # check if this known object is closer
                    dist = (known_objects[k]["position"][0] - objects[o]["position"][0]) * (known_objects[k]["position"][0] - objects[o]["position"][0]) + (known_objects[k]["position"][1] - objects[o]["position"][1]) * (known_objects[k]["position"][1] - objects[o]["position"][1])
                    if dist < closest_k_dist:
                        closest_k = known_objects[k]["propertyOf"]["id"]  # known object name
                        closest_k_dist = dist
                        if debug and known_objects[k]["propertyOf"]["name"] == "tomato":
                            print("    matched tomato known", k, "object", o)

                # if no close matches, continue
                if closest_k is None:
                    continue

                # add to matches
                if closest_k not in matches:
                    matches[closest_k] = []
                matches[closest_k].append([closest_k_dist, o])  # matches[known object index] = [[dist, object index], ...]
            
            # set 1-1 matches, resolve conflicts by choosing closest object
            for m in matches:
                if len(matches[m]) == 1:
                    ids[matches[m][0][1]] = m  # ids[object index] = known object name
                    completed_matches[m] = matches[m][0][1]  # completed_matches[known object index] = object index
                    hadChange = True
                    if debug:
                        print("1-1 MATCH obj name", objects[matches[m][0][1]]["propertyOf"]["name"], "at", objects[matches[m][0][1]]["position"], "to known", m, "of name", known_objects[m]["propertyOf"]["name"], "position", known_objects[m]["position"])
                if len(matches[m]) > 1:
                    min_idx = min(matches[m], key = lambda x : x[0])[1]
                    ids[min_idx] = m 
                    completed_matches[m] = matches[m][0][1]
                    hadChange = True
                    if debug:
                        print("N-1 Match obj name", objects[matches[m][0][1]]["name"], "at", objects[matches[m][0][1]]["position"], "to known", m, "of name", known_objects[m]["propertyOf"]["name"], "position", known_objects[m]["position"])
        
            # if no changes to environment, exit and register new objects
            if not hadChange:
                break

        # objects that have not been matched have likely transformed, check for those transformations
        unmatched_seen_objects = [seen_obj_id for seen_obj_id in ids if ids[seen_obj_id] is None]  # seen objects that have not been matched
        unmatched_known_objects = [known_obj_id for known_obj_id in known_objects if completed_matches[known_obj_id] is None and known_objects[known_obj_id]["propertyOf"]["name"] not in ["pot", "station"]]  # known objects that have not been matched

        if debug:
            print("[After picked up/placed down items] Unmatched Known", [(x, known_objects[x]["propertyOf"]["title"]) for x in unmatched_known_objects])
            print("[After picked up/placed down items] Unmatched Seen", unmatched_seen_objects)

        # check for ingredients that have become soups

        # resolve ingredients to the soups that were in the delta
        for soup in soups_delta_ingredients:  # soup is the known object ID of the soup that has not moved and has changed ingredients
            for ingredient in soups_delta_ingredients[soup]:  # for each added ingredient
                # find the closest known ingredient from the unmatched knowns
                closest_ks = None
                closest_k = None  # will filter the closest ks (list) to choose the best k
                closest_k_dist = float("infinity")
                for k in unmatched_known_objects:
                    if known_objects[k]["propertyOf"]["name"] == ingredient:
                        dist = self.distance(known_objects[k], known_objects[soup])
                        if dist < closest_k_dist:  # reset the set of closest k objects if the distance decreases
                            closest_ks = [k]
                            closest_k_dist = dist
                        elif dist == closest_k_dist:  # add to the set of closest k objects if the distance matches
                            closest_ks.append(k)
                            closest_k_dist = dist
                if closest_ks is None:  # sanity check
                    break
                    # raise ValueError("Could not figure out an unmatched known ingredient to add to this soup! Debug this!")
                # choose the best k, the priority order is simply: 1) the known ingredient has a holder, 2) anything else
                closest_k_holder = None
                for k in closest_ks:
                    if known_objects[k]["propertyOf"]["holder"] is not None:  # prioritize an object with a holder
                        closest_k_holder = known_objects[k]["propertyOf"]["holder"]
                        closest_k = k
                    elif closest_k_holder is None:
                        closest_k = k
                completed_matches[closest_k] = completed_matches[soup]  # match the closest unmatched ingredient with the soup, careful
                known_objects[closest_k]["position"] = known_objects[soup]["position"]  # move the ingredient's position to that of the soup's
                self.updatePredicate("visible", closest_k, False)  # set the ingredient to invisible
                self.updatePredicate("holder", closest_k, None)  # set the holder to None

        # objects that have not been matched have likely transformed, check for those transformations
        unmatched_seen_objects = [seen_obj_id for seen_obj_id in ids if ids[seen_obj_id] is None]  # seen objects that have not been matched
        unmatched_known_objects = [known_obj_id for known_obj_id in known_objects if completed_matches[known_obj_id] is None and known_objects[known_obj_id]["propertyOf"]["name"] not in ["pot", "station"]]  # known objects that have not been matched

        if debug:
            print("[After resolving ingredient deltas] Unmatched Known", [(x, known_objects[x]["propertyOf"]["title"]) for x in unmatched_known_objects])
            print("[After resolving ingredient deltas] Unmatched Seen", unmatched_seen_objects)

        used_known_objects = []  # keep track of which known objects we use so we don't double use ingredients        
        for o in unmatched_seen_objects:  # check for a soup in the seen objects
            if objects[o]["propertyOf"]["name"] != "soup":  # ignore objects that are not soups
                continue
            ingredients = self.get_ingredient_list(obj=objects[o])
            if len(ingredients) == 0:  # ignore soups that don't have ingredients somehow
                raise ValueError("Somehow, a soup does not have any ingredients! Seen object " + o)
            for ingredient in ingredients:
                # find the closest ingredient that fits
                closest_k = None
                closest_k_dist = float("infinity")
                for k in unmatched_known_objects:  # for each unmatched known object
                    # NOTE: we can likely improve this by keeping track of the ingredients in soups, and the soups that have been served, so the system maintains a net zero
                    if known_objects[k]["propertyOf"]["name"] != ingredient:  # ignore objects that are not ingredients to this soup
                        continue
                    if k not in used_known_objects:  # if the object name is not already acounted for with this soup
                        dist = self.distance(known_objects[k], objects[o])
                        if dist < closest_k_dist:  # pick the closest ingredient to the soup
                            closest_k = k
                            closest_k_dist = dist

                if closest_k is None:  # it should not be possible for there not to be a valid ingredient
                    # raise ValueError("No possible ingredients were found to be in this soup! Flag this line and run a debugger.")  # This can happen when chaining mental models due to the reduced observability
                    pass
                else:
                    if debug:
                        print("    I believe object", closest_k, known_objects[closest_k]["propertyOf"]["name"], "has become a soup", o, objects[o])
                    self.updatePredicate("visible", closest_k, False)  # set the ingredient to invisible
                    self.updatePredicate("holder", closest_k, None)  # set the holder to None
                    # "remove" the ingredient by setting its known object link to the soup
                    completed_matches[closest_k] = o
                    used_known_objects.append(closest_k)
                    # if there is not a soup there already, make the object there over the known ingredient
                    no_soup = True
                    for _k in unmatched_known_objects:
                        if known_objects[_k]["propertyOf"]["name"] == "soup" and known_objects[_k]["position"] == objects[o]["position"]:
                            no_soup = False
                            if debug:
                                print("        Soup at", objects[o]["position"], "already exists! From known", known_objects[_k])
                            # "remove" the soup by setting its known object link to the soup
                            completed_matches[_k] = o
                            ids[o] = _k
                    if no_soup:
                        if debug:
                            print("        Adding a new object to ids slot", o, "is the known", known_objects[closest_k])
                        # ids[o] = k

                    # match the objects by moving the ingredient to the soup object
                    known_objects[closest_k]["position"] = objects[o]["position"]

        unmatched_seen_objects = [seen_obj_id for seen_obj_id in ids if ids[seen_obj_id] is None]
        unmatched_known_objects = [known_obj_id for known_obj_id in known_objects if completed_matches[known_obj_id] is None and known_objects[known_obj_id]["propertyOf"]["name"] not in ["pot", "station"]]  # known objects that have not been matched

        if debug:
            print("[After ingredient transform] Umatched Known Objects", [(x, known_objects[x]["propertyOf"]["title"]) for x in unmatched_known_objects])
            print("[After ingredient transform] Unmatched Seen", unmatched_seen_objects)

        # check for dishes that have been turned into soups
        for k in unmatched_known_objects:
            # if dish is held
            if known_objects[k]["propertyOf"]["name"] == "dish" and known_objects[k]["propertyOf"]["holder"] is not None:
                # if there is a full soup that is supposed to be on that spot
                for o in objects:
                    if debug and objects[o]["propertyOf"]["name"] == "soup" and self.get_ingredient_list(obj=objects[o]) == 3 and objects[o]["position"] == known_objects[k]["position"]:
                        print("LIKELY DISH TO SOUP!!!")

        unmatched_seen_objects = [seen_obj_id for seen_obj_id in ids if ids[seen_obj_id] is None]
        unmatched_known_objects = [known_obj_id for known_obj_id in known_objects if completed_matches[known_obj_id] is None and known_objects[known_obj_id]["propertyOf"]["name"] not in ["pot", "station"]]  # known objects that have not been matched

        if debug:
            print("[After dish transform] Umatched Known Objects", [(x, known_objects[x]["propertyOf"]["title"]) for x in unmatched_known_objects])
            print("[After dish transform] Unmatched Seen", unmatched_seen_objects)

        # check for soups that have been turned in to the station, hide them
        for k in unmatched_known_objects:  # for each unmatched known object
            # if the unmatched known object is still unmatched, and a soup, it's probably been turned in
            if known_objects[k]["propertyOf"]["name"] == "soup" and known_objects[k]["propertyOf"]["isReady"] == True:
                # assign the object to any station
                for k2 in known_objects:
                    if known_objects[k2]["propertyOf"]["name"] == "station":
                        self.updatePredicate("position", k, known_objects[k2]["position"])
                        self.updatePredicate("visible", k, False)
                        if debug:
                            print("moving soup to station", k, k2)
                        break

        known_objects = {k : known_objects[k] for k in known_objects if known_objects[k]["visible"]}  # ignore invisible (discarded) objects
        unmatched_known_objects = [known_obj_id for known_obj_id in known_objects if completed_matches[known_obj_id] is None and known_objects[known_obj_id]["propertyOf"]["name"] not in ["pot", "station"]]  # known objects that have not been matched

        # register unassigned objects as new
        for l in [x for x in ids if ids[x] is None]:
            ids[l] = None

        return ids


    # squared distance formula between objects
    def distance(self, obj1, obj2):
        return (obj1["position"][0] - obj2["position"][0]) * (obj1["position"][0] - obj2["position"][0]) + (obj1["position"][1] - obj2["position"][1]) * (obj1["position"][1] - obj2["position"][1])


    # adds an object's predicates or updates them
    #  object_id: the ID of the object to update
    #  obj_dict: dictionary of values to copy over
    #  new_object: whether the object is new and should be initialized
    def update_object(self, object_id, obj_dict, new_object=False):
        # if the object ID is none, pick one
        if object_id is None:
            object_id = "O" + str(len(self.domain_knowledge["objects"]) + 1)
        # the title will not yet be created for observed states, so also initialize other parameters
        if new_object or ("title" not in obj_dict["propertyOf"] and "holder" in obj_dict["propertyOf"] and obj_dict["propertyOf"]["holder"] is None):
            object_title = object_id + "-" + obj_dict["propertyOf"]["name"] + (":" + "+".join([x["propertyOf"]["name"] for x in obj_dict["propertyOf"]["ingredients"]]) if "ingredients" in obj_dict["propertyOf"] else "")
            self.updatePredicate("position", object_id, obj_dict["position"])
            self.updatePredicate("propertyOf", object_id, ("id", object_id))
            self.updatePredicate("propertyOf", object_id, ("name", "NO NAME"))
            self.updatePredicate("propertyOf", object_id, ("holder", None))
            self.updatePredicate("propertyOf", object_id, ("cookTime", None))
            self.updatePredicate("propertyOf", object_id, ("isCooking", None))
            self.updatePredicate("propertyOf", object_id, ("isReady", None))
            self.updatePredicate("propertyOf", object_id, ("isIdle", None))
        else:
            object_title = obj_dict["propertyOf"]["title"] if "title" in obj_dict["propertyOf"] else object_id + "-" + obj_dict["propertyOf"]["name"]
            # if the title is a soup, ensure it has the ingredients
            if "soup" in object_title and "ingredients" in obj_dict["propertyOf"] and ":" not in object_title:
                object_title += ":" + "+".join([x["propertyOf"]["name"] for x in obj_dict["propertyOf"]["ingredients"]])
        # can always update the title
        self.updatePredicate("propertyOf", object_id, ("title", object_title))

        # position"title"
        if "position" in obj_dict:
            self.updatePredicate("position", object_id, obj_dict["position"])
        # id
        if "id" in obj_dict:
            self.updatePredicate("propertyOf", object_id, ("id", object_id))
        # name
        if "propertyOf" in obj_dict and "name" in obj_dict["propertyOf"]:
            self.updatePredicate("propertyOf", object_id, ("name", obj_dict["propertyOf"]["name"]))
        # holder
        if "propertyOf" in obj_dict and "holder" in obj_dict["propertyOf"]:
            self.updatePredicate("propertyOf", object_id, ("holder", obj_dict["propertyOf"]["holder"]))
        # ingredients
        if "propertyOf" in obj_dict and "ingredients" in obj_dict["propertyOf"]:
            self.updatePredicate("propertyOf", object_id, ("ingredients", obj_dict["propertyOf"]["ingredients"]))
        # cook time
        if "propertyOf" in obj_dict and "cookTime" in obj_dict["propertyOf"]:
            self.updatePredicate("propertyOf", object_id, ("cookTime", obj_dict["propertyOf"]["cookTime"]))
        # is cooking
        if "propertyOf" in obj_dict and "isCooking" in obj_dict["propertyOf"]:
            self.updatePredicate("propertyOf", object_id, ("isCooking", obj_dict["propertyOf"]["isCooking"]))
        # is ready
        if "propertyOf" in obj_dict and "isReady" in obj_dict["propertyOf"]:
            self.updatePredicate("propertyOf", object_id, ("isReady", obj_dict["propertyOf"]["isReady"]))
        # is idle
        if "propertyOf" in obj_dict and "isIdle" in obj_dict["propertyOf"]:
            self.updatePredicate("propertyOf", object_id, ("isIdle", obj_dict["propertyOf"]["isIdle"]))
        
        return object_id
