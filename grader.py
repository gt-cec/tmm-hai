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
def grade_user(user:str, round:int, debug=False):
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
        smm_ground_truth = smm.smm.SMM("predicates")  # logical predicates SMM using full observability, represents ground truth
        score = 0
        num_questions = 0
        line_count = 1
        for line in lines:
            # keep track of progress
            if line_count % 100 == 0 and smm_ground_truth.initialized:
                print("    ", int(100 * line_count / num_lines), "%", "[", user,"]")
            line_count += 1

            log_dict = ast.literal_eval(line)
            # handle state updates
            if "state" in log_dict:
                state = log_dict  # pull the state
                if state["layout"] != layout:  # ignore if incorrect layout
                    continue
                if not smm_ground_truth.initialized:  # initialize the ground truth SMM if it has not been initialized
                    smm_ground_truth.init_belief_state_from_file(layout)
                smm_ground_truth.update(log_dict, debug=debug)

            if not smm_ground_truth.initialized:
                continue

            # handle in-situ questions
            if "type" in log_dict:
                if log_dict["type"] == "in situ":
                    question = clean_question_string(log_dict["question"])  # clean the question
                    user_response = log_dict["response"].lower()  # get the user response                    
                    print("Question:", question)
                    print("User Response:", user_response)
                    # print("State:", state)
                    ground_truth_response = answer_question(smm_ground_truth, question)
                    print("Ground Truth Response:", ground_truth_response)
                    if ground_truth_response is not None:  # None indicates the question is being intentionally ignored in scoring
                        # score the responses
                        _score = score_response(user_response, ground_truth_response)
                        score += _score
                        num_questions += 1
                        if question not in responses:  # ensure the question is in the seen responses
                            responses[question] = []
                        responses[question].append([user_response, ground_truth_response, _score, smm_ground_truth.belief_state])  # add the record for the question
    print("User:", user, "Round", round, "Score:", score, "/", num_questions)
    return responses, score, num_questions

# score a question's response between 0 (incorrect) and 1 (correct)
#   candidate_response: the user or agent's response
#   ground_truth_response: the oracle's response
def score_response(candidate_response:str, ground_truth_response:str)->int:
    # edge case catching
    if candidate_response is None or candidate_response == "" or ground_truth_response is None or ground_truth_response == "":
        raise ValueError("Candidate and ground truth responses must be non-empty strings!")

    candidate_response = candidate_response.lower()
    ground_truth_response = ground_truth_response.lower()

    score = 0

    # position questions: score 1 for correct, 1 for center-leaning (e.g., user:right, truth:center-right), and 0 otherwise; split across horizontal and vertical components of the response
    if candidate_response in LOCATION and ground_truth_response in LOCATION:
        candidate_response = "center center" if candidate_response == "center" or candidate_response == "center-ish" else candidate_response
        candidate_split = candidate_response.split(" ")
        ground_truth_split = ground_truth_response.split(" ")
        # judge horizontal response
        if "center-right" in ground_truth_split[0] and ("center" in candidate_split[0] or "right" in candidate_split[0]):
            score += 0.5
        elif "right" in ground_truth_split[0] and "right" in candidate_split[0]:
            score += 0.5
        elif "center-left" in ground_truth_split[0] and ("center" in candidate_split[0] or "left" in candidate_split[0]):
            score += 0.5
        elif "left" in ground_truth_split[0] and "left" in candidate_split[0]:
            score += 0.5
        # judge vertical response
        if "center-top" in ground_truth_split[1] and ("center" in candidate_split[1] or "top" in candidate_split[1]):
            score += 0.5
        elif "top" in ground_truth_split[1] and "top" in candidate_split[1]:
            score += 0.5
        elif "center-bottom" in ground_truth_split[1] and ("center" in candidate_split[1] or "bottom" in candidate_split[1]):
            score += 0.5
        elif "bottom" in ground_truth_split[1] and "bottom" in candidate_split[1]:
            score += 0.5
        # add 0.5 for half if the score if already 0.5, so "right half" is 1 when on the right side
        if score > 0 and "half" in candidate_response:
            score += 0.5
        # return if scored
        return score
    
    # action questions: score 1 for correct, 0 otherwise
    if candidate_response in RECIPE and ground_truth_response in smm_to_recipe:
        ground_truth_response = smm_to_recipe[ground_truth_response]
        if "idling" in ground_truth_response and "idling" in candidate_response:
            score += 1
        elif ground_truth_response == candidate_response:
            score += 1
        return score
    
    # player status questions: score 1 for correct, 0 otherwise
    if candidate_response in PLAYER_STATUS and ground_truth_response in smm_to_recipe:
        ground_truth_response = smm_to_recipe[ground_truth_response]
        if "idling" in ground_truth_response and "idling" in candidate_response:
            score += 1
        elif ground_truth_response == candidate_response:
            score += 1
        return score
    
    # pot full questions: score 1 for correct, 0 otherwise
    if candidate_response in POT_FULL and ground_truth_response in POT_FULL:
        if ground_truth_response == candidate_response:
            score += 1
        return score
    
    # pot status questions: score 1 for correct, 0 otherwise
    if candidate_response in POT_STATUS and ground_truth_response in POT_STATUS:
        if ground_truth_response == candidate_response:
            score += 1
        return score
    
    # soups remaining questions: score 1 for correct, 0 otherwise
    if "soups" in candidate_response and "soups" in ground_truth_response:
        ground_truth_soups = int(ground_truth_response.split(" ")[0])
        candidate_response = "1-2 soups" if "1" in candidate_response or "2" in candidate_response else "3-4 soups" if "3" in candidate_response or "4" in candidate_response else candidate_response
        ground_truth_response = "1-2 soups" if ground_truth_soups in [1, 2] else "3-4 soups" if ground_truth_soups >= 3 else ground_truth_response
        if ground_truth_response == candidate_response:
            score += 1
        return score

    # completion likelihood questions: score 1 for correct, 0 otherwise
    if candidate_response in COMPLETION_LIKELIHOOD and ground_truth_response in COMPLETION_LIKELIHOOD:
        if ground_truth_response == candidate_response:
            score += 1
        return score
    
    # ingredient available questions: score 1 for correct, 0.5 for correct likely, 0.25 for unsure, 0 otherwise
    if candidate_response in INGREDIENT_AVAILABLE:
        if candidate_response == "definite yes" and ground_truth_response == "true":
            score += 1
        elif candidate_response == "likely yes" and ground_truth_response == "true":
            score += .5
        elif candidate_response == "unsure":
            score += .25
        elif candidate_response == "likely no" and ground_truth_response == "false":
            score += .5
        elif candidate_response == "definite no" and ground_truth_response == "false":
            score += 1
        return score

    raise ValueError("Reached end of response scoring without catching the response type, responses were: (cand)" + str(candidate_response) + ", (truth)" + str(ground_truth_response))

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
    user_position = smm.belief_state["agents"]["A0"]["at"]
    # get the position of the AI teammate
    if object == "teammate":
        position = smm.belief_state["agents"]["A1"]["at"]
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
                dist = (smm.belief_state["objects"][obj]["at"][0] - user_position[0]) ** 2 + (smm.belief_state["objects"][obj]["at"][1] - user_position[1]) ** 2
                if dist < closest_ingredient_dist:
                    closest_ingredient_dist = dist
                    closest_ingredient_position = smm.belief_state["objects"][obj]["at"]
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
    print(">>>", len([obj for obj in smm.belief_state["objects"] if ingredient in smm.belief_state["objects"][obj]["propertyOf"]["name"]]))
    input()
    ingredient_available = len([obj for obj in smm.belief_state["objects"] if ingredient in smm.belief_state["objects"][obj]["propertyOf"]["name"]]) > 0
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
        if target_pot is None or (side == "left" and smm.belief_state["objects"][obj]["at"][0] < smm.belief_state["objects"][target_pot]["at"][0]):
            target_pot = obj
        elif target_pot is None or (side == "right" and smm.belief_state["objects"][obj]["at"][0] > smm.belief_state["objects"][target_pot]["at"][0]):
            target_pot = obj
    # if we are looking for the status of the pot
    if knowledge == "state":
        ing = [x for x in smm.belief_state["objects"] if x != target_pot and smm.belief_state["objects"][x]["visible"] and tuple(smm.belief_state["objects"][x]["at"]) == tuple(smm.belief_state["objects"][target_pot]["at"])]
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
        ing = [x for x in smm.belief_state["objects"] if x != target_pot and smm.belief_state["objects"][x]["visible"] and tuple(smm.belief_state["objects"][x]["at"]) == tuple(smm.belief_state["objects"][target_pot]["at"])]
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