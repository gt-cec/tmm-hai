# grader.py: processes a world state to determine the ground truth, for comparisan with the user response and belief state estimate

import ast  # for converting log line to dictionary
import re  # for removing HTML tags from question strings
import smm.smm  # for constructing the ground truth SMM (logical predicates with full observability)
import make_smm  # for visualizing the SMM

# mapping from layouts to round
rounds = {
    "RSMM3": 1,
    "RSMM4": 2,
    "RSMM5": 3,
    "RSMM6": 4,
    "RSMM7": 5,
}

INGREDIENTS = ["onion", "tomato"]
LOCATION = ["top right", "top center-right", "top center", "top center-left", "top left", "center right", "center center-right", "center center", "center", "center-ish", "center center-left", "center left", "bottom right", "bottom center-right", "bottom center", "bottom center-left", "bottom left", "left half", "right half", "none available", "no idea"]
RECIPE = ["getting ingredient for pot", "getting dish for soup", "bringing soup to station", "idling, all soups complete", "no idea"]
PLAYER_STATUS = ["getting ingredient for pot", "getting dish for soup", "bringing soup to station", "exploring kitchen", "idling, all soups complete", "not sure yet"]
POT_FULL = ["empty", "1-2 ingredients", "3 ingredients (full/cooking)", "no idea"]
POT_STATUS = ["finished cooking", "cooking", "1-2 ingredients", "empty", "no idea"]
SOUPS_REMAINING = ["no soups", "1-2 soups", "3-4 soups", "no idea"]
COMPLETION_LIKELIHOOD = ["yes or already complete", "probably yes", "not sure", "probably no", "definite no"]
INGREDIENT_AVAILABLE = ["definite yes", "likely yes", "unsure", "likely no", "definite no"]

smm_to_recipe = {
    "pick up ingredient": "getting ingredient for pot",
    "place ingredient into pot": "getting ingredient for pot",
    "activate pot": "getting ingredient for pot",
    "picking up dish": "getting dish for soup",
    "wait for cooking": "getting dish for soup",
    "place soup on dish": "getting dish for soup",
    "place soup on counter": "bringing soup to station",
}

# clean question strings
def clean_question_string(text):
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text).lower()

# processes a user's logs to determine their accuracy
def grade_user(user:str, round:int, visibility:str, debug=False):
    # get the layout from the round
    layout = [x for x in rounds if rounds[x] == round]
    layout = None if len(layout) == 0 else layout[0]
    if layout is None:
        raise ValueError("Provided round is not valid! Rounds are: " + ",".join([x for x in rounds]))
    
    responses = {}  # record of the user's question responses: dict{question:[user response, ground truth response, score]}

    # process the user
    user.replace(".txt", "").replace(".log", "")  # remove the extension
    with open("env/server/logs/" + user + ".txt", "r") as f:
        print("Now processing user", user, "round", round)
        lines = f.readlines()  # read every line of the log
        num_lines = len(lines)
        state = None  # the current game state
        true_model = smm.smm.SMM("predicates", visibility="O20", agent="A0")  # robot model with full observability, ground truth
        agent_model = smm.smm.SMM("predicates", visibility=visibility, agent="A0")  # robot model with partial observability
        estimated_human_model = smm.smm.SMM("predicates", visibility="D4", agent="A1")  # estimated human model with partial observability

        # scores
        user_score_wrt_true = 0
        agent_score_wrt_true = 0
        estimated_human_score_wrt_true = 0
        true_score_wrt_user = 0
        agent_score_wrt_user = 0
        estimated_human_score_wrt_user = 0
        
        num_questions = 0
        line_count = 1
        first_view = True
        for line in lines:
            # keep track of progress
            if line_count % 100 == 0 and true_model.initialized:
                print("    ", int(100 * line_count / num_lines), "%", "[", user,"]")
            line_count += 1

            log_dict = ast.literal_eval(line)
            # handle state updates
            if "state" in log_dict:
                state = log_dict  # pull the state
                if state["layout"] != layout:  # ignore if incorrect layout
                    continue

                # initialize the SMMs if they have not been initialized
                if not true_model.initialized:
                    true_model.init_belief_state_from_file(state["layout"] + ".layout")

                # update the mental models
                state = true_model.convert_log_to_state(state)
                true_model.update(state, debug=False)
                true_belief_state = true_model.get_visible_belief_state()

                if first_view:
                    agent_model.model.domain_knowledge = true_belief_state
                    estimated_human_model.model.domain_knowledge = true_belief_state
                    first_view = False

                agent_model.update(true_belief_state, debug=False)
                agent_belief_state = agent_model.get_visible_belief_state()
                estimated_human_model.update(agent_belief_state, debug=False)

            if not true_model.initialized:
                continue

            # handle in-situ questions
            if "type" in log_dict:
                if log_dict["stage"] != "round" + str(round):
                    continue
                if log_dict["type"] == "in situ submission":
                    question = clean_question_string(log_dict["question"])  # clean the question
                    print("Question:", question)
                    # ignore the completion question
                    if "do you think your team" in question:
                        continue
                    user_response = log_dict["response"].lower()  # get the user response                    
                    true_response = answer_question(true_model, question)
                    agent_response = answer_question(agent_model, question)
                    estimated_human_response = answer_question(estimated_human_model, question)
                    print("User Response:", user_response, "True Response:", true_response, "Agent Response:", agent_response, "Estimated Human Response:", estimated_human_response, "User Score:", score_response(question, user_response, true_response))
                    if true_response is not None:  # None indicates the question is being intentionally ignored in scoring
                        # score the responses
                        # user w.r.t. truth
                        _user_score_wrt_true = score_response(question, user_response, true_response)
                        user_score_wrt_true += _user_score_wrt_true
                        # agent w.r.t. truth
                        _agent_score_wrt_true = score_response(question, agent_response, true_response)
                        agent_score_wrt_true += _agent_score_wrt_true
                        # estimated human w.r.t. truth
                        _estimated_human_score_wrt_true = score_response(question, estimated_human_response, true_response)
                        estimated_human_score_wrt_true += _estimated_human_score_wrt_true
                        # truth w.r.t. user
                        _true_score_wrt_user = score_response(question, true_response, user_response)
                        true_score_wrt_user += _true_score_wrt_user
                        # agent w.r.t. user
                        _agent_score_wrt_user = score_response(question, agent_response, user_response)
                        agent_score_wrt_user += _agent_score_wrt_user
                        # estimated human w.r.t. user
                        _estimated_human_score_wrt_user = score_response(question, estimated_human_response, user_response)
                        estimated_human_score_wrt_user += _estimated_human_score_wrt_user
                        num_questions += 1
                        if question not in responses:  # ensure the question is in the seen responses
                            responses[question] = []
                        responses[question].append([user_response, true_response, _user_score_wrt_true, _true_score_wrt_user, agent_response, _agent_score_wrt_true, _agent_score_wrt_user, estimated_human_response, _estimated_human_score_wrt_true, _estimated_human_score_wrt_user, true_model.get_visible_belief_state(), agent_model.get_visible_belief_state(), estimated_human_model.get_visible_belief_state()])  # add the record for the question
    print("User:", user, "Round", round, "True Score:", user_score_wrt_true, "Agent Score:", agent_score_wrt_user, "Estimated Human Score:", estimated_human_score_wrt_user, "/", num_questions)
    return responses, user_score_wrt_true, agent_score_wrt_true, estimated_human_score_wrt_true, true_score_wrt_user, agent_score_wrt_user, estimated_human_score_wrt_user, num_questions

# score a question's response between 0 (incorrect) and 1 (correct)
#   candidate_response: the user or agent's response
#   ground_truth_response: the oracle's response
def score_response(question:str, candidate_response:str, ground_truth_response:str)->int:
    # edge case catching
    if question is None or question == "" or candidate_response is None or candidate_response == "" or ground_truth_response is None or ground_truth_response == "":
        raise ValueError("Question, candidate, and ground truth responses must be non-empty strings!")

    candidate_response = candidate_response.lower()
    ground_truth_response = ground_truth_response.lower()

    candidate_response = "center" if candidate_response == "center or in-between" else candidate_response
    ground_truth_response = "center" if ground_truth_response == "center or in-between" else ground_truth_response

    score = 0

    # location questions
    if "where are you" in question or "where is your teammate" in question or "where is the nearest available" in question:
        # position questions: score 1 for correct, 1 for center-leaning (e.g., user:right, truth:center-right), and 0 otherwise; split across horizontal and vertical components of the response
        if candidate_response not in LOCATION or ground_truth_response not in LOCATION:
            raise ValueError("Impossible question response")
        if "-r" in candidate_response or "-l" in candidate_response or "-ish" in ground_truth_response or "half" in ground_truth_response or ground_truth_response == "center":
            _resp = candidate_response
            candidate_response = ground_truth_response
            ground_truth_response = _resp
        if candidate_response == "no idea" or ground_truth_response == "no idea":
            return 0
        candidate_response = "center center" if candidate_response == "center" or candidate_response == "center-ish" else candidate_response
        ground_truth_response = "center center" if ground_truth_response == "center" or ground_truth_response == "center-ish" else ground_truth_response
        candidate_split = candidate_response.split(" ")
        ground_truth_split = ground_truth_response.split(" ")
        # judge horizontal response
        if "center-right" in ground_truth_response and ("center" in candidate_split[1] or "right" in candidate_response):
            score += 0.5
        elif "right" in ground_truth_response and "right" in candidate_response:
            score += 0.5
        elif ("center-left" in ground_truth_response and ("center" in candidate_split[1] or "left" in candidate_response)) or ("center-left" in candidate_response and ("center" in ground_truth_split[1] or "left" in ground_truth_response)):
            score += 0.5
        elif "left" in ground_truth_response and "left" in candidate_response:
            score += 0.5
        elif ground_truth_split[1] == "center" and candidate_split[1] == "center":
            score += 0.5
        # judge vertical response
        if ("center-top" in ground_truth_response and ("center" in candidate_split[0] or "top" in candidate_response)) or ("center-top" in candidate_response and ("center" in ground_truth_split[0] or "top" in ground_truth_response)):
            score += 0.5
        elif "top" in ground_truth_response and "top" in candidate_response:
            score += 0.5
        elif ("center-bottom" in ground_truth_response and ("center" in candidate_split[0] or "bottom" in candidate_response)) or ("center-bottom" in candidate_response and ("center" in ground_truth_split[0] or "bottom" in ground_truth_response)):
            score += 0.5
        elif "bottom" in ground_truth_response and "bottom" in candidate_response:
            score += 0.5
        elif ground_truth_split[0] == "center" and candidate_split[0] == "center":
            score += 0.5
        # judge the correct center response
        if ground_truth_response == "center center" and candidate_response == "center center":
            return 1
        # add 0.5 for half if the score if already 0.5, so "right half" is 1 when on the right side
        if score > 0 and "half" in candidate_response:
            score += 0.5
        # return if scored
        return score
    # action questions
    elif "what are you doing" in question or "what is your teammate doing" in question:
        if ground_truth_response in RECIPE and candidate_response in smm_to_recipe:
            _resp = candidate_response
            candidate_response = ground_truth_response
            ground_truth_response = _resp
        if ground_truth_response in smm_to_recipe:
            ground_truth_response = smm_to_recipe[ground_truth_response]
        if candidate_response in smm_to_recipe:
            candidate_response = smm_to_recipe[candidate_response]
        if "idling" in ground_truth_response and "idling" in candidate_response:
            return 1
        elif ground_truth_response == candidate_response:
            return 1
        return score
    # What will you/teammate be doing in ~10 seconds from now?
    elif "what will you be doing ~10 seconds from now" in question or "what will your teammate be doing ~10 seconds from now" in question:
        response = None  # get_future_action_semantic(smm, "player")
    # How many more soups can be made/delivered, including soups in-progress?
    elif "how many more soups" in question:
        if ("soups" not in candidate_response and candidate_response != "no idea") or ("soups" not in ground_truth_response and ground_truth_response != "no idea"):
            raise ValueError("Impossible question answer " + candidate_response + " " + ground_truth_response)
        if "-" in ground_truth_response or "+" in ground_truth_response or "no" in ground_truth_response:
            _resp = candidate_response
            candidate_response = ground_truth_response
            ground_truth_response = _resp
        if candidate_response == "no idea" or ground_truth_response == "no idea":  # no idea is automatic 0
            return 0
        if ground_truth_response == "no soups": 
            ground_truth_response = "0 soups"
        ground_truth_soups = int(ground_truth_response.split(" ")[0]) if ground_truth_response.split(" ")[0].isdigit() else int(ground_truth_response[0])
        candidate_response = "0 soups" if "no soups" in candidate_response or "0" in candidate_response else "1-2 soups" if "1" in candidate_response or "2" in candidate_response else "3-4 soups" if "3" in candidate_response or "4" in candidate_response else "5+ soups" if "5" in candidate_response or "6" in candidate_response else candidate_response
        ground_truth_response = "0 soups" if "no soups" in ground_truth_response or ground_truth_response[0] == "0" else "1-2 soups" if ground_truth_soups in [1, 2] else "3-4 soups" if ground_truth_soups in [3, 4] else "5+ soups" if ground_truth_soups >= 5 else ground_truth_response
        if ground_truth_response == candidate_response:
            score += 1
        return score
    # What is the leftmost/rightmost pot's status?
    elif "pot's status" in question:
        if candidate_response not in POT_STATUS or ground_truth_response not in POT_STATUS:
            raise ValueError("Impossible question answer")
        if ground_truth_response == candidate_response:
            score += 1
        return score
    # How full is the leftmost/rightmost pot?
    elif "how full" in question:
        if candidate_response not in POT_FULL or ground_truth_response not in POT_FULL:
            raise ValueError("Impossible question answer")
        if ground_truth_response == candidate_response:
            score += 1
        return score
    # Is there at one available onion/tomato?
    elif "is there at least one available" in question:
        if ground_truth_response in INGREDIENT_AVAILABLE and candidate_response not in INGREDIENT_AVAILABLE:
            _resp = candidate_response
            candidate_response = ground_truth_response
            ground_truth_response = _resp
        
        candidate_response = "true" if candidate_response in ["definite yes", "likely yes"] else candidate_response
        candidate_response = "false" if candidate_response in ["definite no", "likely no"] else candidate_response

        ground_truth_response = "true" if ground_truth_response in ["definite yes", "likely yes"] else ground_truth_response
        ground_truth_response = "false" if ground_truth_response in ["definite no", "likely no"] else ground_truth_response

        if candidate_response == "no idea" or ground_truth_response == "no idea" or candidate_response == "unsure" or ground_truth_response == "unsure":
            return 0
        
        if candidate_response == "true" and ground_truth_response == "true":
            return 1
        elif candidate_response == "true" and ground_truth_response == "true":
            return 1
        elif candidate_response == "unsure" or candidate_response == "no idea":
            return 0
        elif candidate_response == "false" and ground_truth_response == "false":
            return 1
        elif candidate_response == "false" and ground_truth_response == "false":
            return 1
        return score
    # Do you think your team will complete all the dishes in time?
    elif "complete all the dishes" in question:
        response = None  # not worried about level 3 yet
    else:
        raise ValueError("SMM is trying to answer a question that is not handled: " + question)

    # completion likelihood questions: score 1 for correct, 0 otherwise
    if candidate_response in COMPLETION_LIKELIHOOD and ground_truth_response in COMPLETION_LIKELIHOOD:
        if ground_truth_response == candidate_response:
            score += 1
        return score
    
    # binary questions 
    if candidate_response in ["true", "false"] and ground_truth_response == candidate_response:
        score += 1
        return score

    raise ValueError("Reached end of response scoring without catching the response type, responses were: " + question + " cand: " + str(candidate_response) + ", truth: " + str(ground_truth_response))

# get the SMM's response to a question
def answer_question(smm:smm.smm.SMM, question):
    # Where is you/teammate?
    if "where are you" in question:
        response = get_location_semantic(smm, "player")
    elif "where is your teammate" in question:
        response = get_location_semantic(smm, "teammate")
    # Where is the nearest available onion/tomato?
    elif "where is the nearest available" in question:
        response = get_location_semantic(smm, [x for x in INGREDIENTS if x in question][0])
    # What are you doing?
    elif "what are you doing" in question:
        response = get_current_action_semantic(smm, "player")
    # What is your teammate doing?
    elif "what is your teammate doing" in question:
        response = get_current_action_semantic(smm, "teammate")
    # What will you/teammate be doing in ~10 seconds from now?
    elif "what will you be doing ~10 seconds from now" in question:
        response = None  # get_future_action_semantic(smm, "player")
    elif "what will your teammate be doing ~10 seconds from now" in question:
        response = None  # get_future_action_semantic(smm, "teammate")
    # How many more soups can be made/delivered, including soups in-progress?
    elif "how many more soups" in question:
        response = get_remaining_soups(smm)
    # What is the leftmost/rightmost pot's status?
    elif "pot's status" in question:
        response = get_pot_status(smm, [x for x in ["left", "right"] if x in question][0], "state")
    # How full is the leftmost/rightmost pot?
    elif "how full" in question:
        response = get_pot_status(smm, [x for x in ["left", "right"] if x in question][0], "full")
    # Is there at one available onion/tomato?
    elif "is there at least one available" in question:
        response = get_ingredient_available(smm, [x for x in INGREDIENTS if x in question][0])
    # Do you think your team will complete all the dishes in time?
    elif "complete all the dishes" in question:
        response = None  # not worried about level 3 yet
    else:
        raise ValueError("SMM is trying to answer a question that is not handled: " + question)
    return response

# get location semantic, e.g., "tomato" could return "top left".
def get_location_semantic(smm:smm.smm.SMM, object:str)->str:
    position = None
    user_position = smm.belief_state["agents"]["A0"]["position"]
    # get the position of the AI teammate
    if object == "teammate":
        position = smm.belief_state["agents"]["A1"]["position"]
    # get the position of the player
    if object == "player":
        position = user_position
    # get the position of the closest ingredient of the given object type (onion, tomato)
    if object in INGREDIENTS:
        closest_ingredient_position = None
        closest_ingredient_dist = float("infinity")
        for obj in smm.belief_state["objects"]:
            # ignore incorrect ingredients
            if smm.belief_state["objects"][obj]["propertyOf"]["name"] == object:
                dist = (smm.belief_state["objects"][obj]["position"][0] - user_position[0]) ** 2 + (smm.belief_state["objects"][obj]["position"][1] - user_position[1]) ** 2
                if dist < closest_ingredient_dist:
                    closest_ingredient_dist = dist
                    closest_ingredient_position = smm.belief_state["objects"][obj]["position"]
        # error if there are no ingredients of that type
        if closest_ingredient_position is None:
            raise ValueError("Tried to get the location of the closest ingredient " + object + ", however there were no ingredients of that type!")
        position = closest_ingredient_position
    
    # error if no position was found
    if position is None:
        raise ValueError("Tried to get the location of the closest " + object + ", however there were no objects of that type!")

    # generate the semantic response corresponding to the position of the object (e.g., "top right")
    vertical = "top" if position[1] < 2 else "bottom" if position[1] > 2 else "center"
    # left: 0,1,2 ; center-left: 3,4 ; center: 5 ; center-right: 6,7 ; right: 8,9,10
    horizontal = "left" if position[0] < 3 else "center-left" if position[0] < 5 else "right" if position[0] > 7 else "center-right" if position[0] > 5 else "center"
    response = vertical + " " + horizontal  # in the general case, "top" and "right" becomes "top right"
    return response

# get current action semantic, e.g., "what will you be doing in ~10 seconds from now?"
def get_current_action_semantic(smm:smm.smm.SMM, object:str)->str:
    action = None
    # get the position of the AI teammate
    if object == "teammate":
        action = smm.belief_state["agents"]["A1"]["goal"]
    # get the position of the player
    if object == "player":
        action = smm.belief_state["agents"]["A0"]["goal"]
    
    # error if no position was found
    if action is None:
        raise ValueError("Tried to get the location of the object " + object + ", however there were no objects of that type! Should be \"teammate\" or \"player\"")

    return action

# get future action semantic, e.g., "what will you be doing in ~10 seconds from now?"
def get_future_action_semantic(smm:smm.smm.SMM, object:str)->str:
    action = None
    # get the position of the AI teammate
    if object == "teammate":
        action = smm.belief_state["agents"]["A1"]["goal"]
    # get the position of the player
    if object == "player":
        action = smm.belief_state["agents"]["A0"]["goal"]
    
    # error if no position was found
    if action is None:
        raise ValueError("Tried to get the location of the object " + object + ", however there were no objects of that type! Should be \"teammate\" or \"player\"")

    return action

# get the number of soups that can be made
def get_remaining_soups(smm:smm.smm.SMM)->str:
    objects = get_visible_objects(smm)
    # get number of ingredients on counters and held (working)
    ingredients_on_counters = len([obj for obj in objects if smm.belief_state["objects"][obj]["propertyOf"]["name"] in INGREDIENTS])
    # get number of soups on counters (only complete soups have + in the name), the -1 is to ignore the "soup" prefix
    soups_on_counters = sum([len(smm.belief_state["objects"][obj]["propertyOf"]["title"].replace(":", "+").split("+"))-1 for obj in objects if "+" in smm.belief_state["objects"][obj]["propertyOf"]["title"] or ":" in smm.belief_state["objects"][obj]["propertyOf"]["title"]])
    # number of soups are: ingredients on counters/3 + ingredients held/3 + ingredients in uncooked pot/3 + number of filled cooking/cooked pot + number of carried soups + number of soups on counter
    remaining = int(ingredients_on_counters / 3 + soups_on_counters / 3)  # the int() will floor the result
    return str(remaining) + " soups"

# get whether an ingredient is available
def get_ingredient_available(smm:smm.smm.SMM, ingredient:str)->str:
    ingredient_available = len([obj for obj in smm.belief_state["objects"] if ingredient in smm.belief_state["objects"][obj]["propertyOf"]["name"] and smm.belief_state["objects"][obj]["visible"] == True]) > 0
    return str(ingredient_available).lower()

# get the status of a pot
def get_pot_status(smm:smm.smm.SMM, side:str, knowledge:str)->str:
    # check the side parameter
    if side not in ["left", "right"]:
        raise ValueError("The 'side' parameter of get_pot_status must be \"left\" or \"right\"")
    if knowledge not in ["state", "full"]:
        raise ValueError("The 'knowledge' parameter of get_pot_status must be \"status\" or \"full\"")
    # find the target pot (leftmost or rightmost)
    target_pot = None
    for obj in smm.belief_state["objects"]:
        if smm.belief_state["objects"][obj]["propertyOf"]["name"] != "pot":  # ignore everything but pots
            continue
        if target_pot is None or (side == "left" and smm.belief_state["objects"][obj]["position"][0] < smm.belief_state["objects"][target_pot]["position"][0]):
            target_pot = obj
        elif target_pot is None or (side == "right" and smm.belief_state["objects"][obj]["position"][0] > smm.belief_state["objects"][target_pot]["position"][0]):
            target_pot = obj
    # if we are looking for the status of the pot
    if knowledge == "state":
        ing = [x for x in smm.belief_state["objects"] if x != target_pot and smm.belief_state["objects"][x]["visible"] and tuple(smm.belief_state["objects"][x]["position"]) == tuple(smm.belief_state["objects"][target_pot]["position"])]
        num_ingredients = 0 if len(ing) == 0 else len(smm.belief_state["objects"][ing[0]]["propertyOf"]["title"].split("+"))
        if num_ingredients == 0:
            return "empty"
        elif smm.belief_state["objects"][ing[0]]["propertyOf"]["isReady"]:
            return "finished cooking"
        # if the pot is currently cooking
        elif smm.belief_state["objects"][ing[0]]["propertyOf"]["isCooking"]:
            return "cooking"
        elif num_ingredients < 3:
            return "1-2 ingredients"
        else:
            raise ValueError("Unsure how this many ingredients were not handled: num ingredients in pot: " + str(num_ingredients) + " state " + str(smm.belief_state["objects"][ing[0]]))
    # if we are looking for the number of ingredients 
    elif knowledge == "full":
        # get ingredients on this pot
        ing = [x for x in smm.belief_state["objects"] if x != target_pot and smm.belief_state["objects"][x]["visible"] and tuple(smm.belief_state["objects"][x]["position"]) == tuple(smm.belief_state["objects"][target_pot]["position"])]
        num_ingredients = 0 if len(ing) == 0 else len(smm.belief_state["objects"][ing[0]]["propertyOf"]["title"].split("+"))
        if num_ingredients == 0:
            return "Empty"
        elif num_ingredients < 3:
            return "1-2 ingredients"
        else:
            return "3 ingredients (full/cooking)"

    # otherwise, return the number of ingredients in the pot
    return str(len(smm.belief_state["objects"][target_pot]["contains"]))

# utility function to get visible smm objects
def get_visible_objects(smm, only_ingredients=False):
    obj = [x for x in smm.belief_state["objects"] if smm.belief_state["objects"][x]["visible"]]
    if only_ingredients:
        obj = [x for x in obj if smm.belief_state["objects"][x]["propertyOf"]["name"] in INGREDIENTS]
    return obj