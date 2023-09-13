import pickle
import sys
import pyperclip  # for placing the prompt onto the clipboard
import grader
import plots.bar
import statistics


# load the pickled data
def load_data(path="./processed_data/", visibility=None):
    if visibility is None or visibility[0] not in ["V", "O", "D"] or visibility[1] not in ["1", "2", "3", "4", "5", "6", "7", "8", "9"]:  # check the visibility
        raise ValueError("Invalid visibility argument! Must be of type O, D, V, and radii 1-9, for example, O4")
    with open(path + visibility + "_smm_responses_by_round.pkl", "rb") as f:
        responses_by_round = pickle.load(f)
    with open(path + visibility + "_smm_responses_by_user.pkl", "rb") as f:
        responses_by_user = pickle.load(f)
    with open(path + visibility + "_smm_responses_by_user_and_round.pkl", "rb") as f:
        responses_by_user_and_round = pickle.load(f)
    with open(path + visibility + "_smm_responses_by_question.pkl", "rb") as f:
        responses_by_question = pickle.load(f)
    with open(path + visibility + "_smm_scores_by_user_and_round.pkl", "rb") as f:
        scores_by_user_and_round = pickle.load(f)
    print("Loaded results data.")
    return responses_by_round, responses_by_user, responses_by_user_and_round, responses_by_question, scores_by_user_and_round


# formulate the prompt header
def get_prompt_header():
    prompt = "You are playing a simple 2D kitchen game. The objective of the game is for two agents, A0 and A1, to cook soups using ingredients from the counters. You are A1. The game board has 11 columns and 5 rows, where the location (0,0) is at the top left and the location (10,4) is at the bottom right. Here are the steps to cook a soup:"
    prompt += "\n"
    prompt += "\n1. Bring three ingredients to an unfilled pot. The ingredients can be tomatoes, or onions, or both."
    prompt += "\n2. The pot will start cooking when it is filled."
    prompt += "\n3. Once cooking is complete, bring a dish to the pot to plate the soup."
    prompt += "\n4. Bring the plated soup to a serving station."
    prompt += "\n5. The plated soup will then be delivered automatically."
    prompt += "\n\nA pot is considered cooking if it has a soup at its location, and the soup is cooking. Cooking is complete if the soup at the pot's location is ready. A pot without a soup at its location is empty."
    return prompt


# formulate the prompt from the state
def get_prompt_state(state):
    prompt = "The current objects in the kitchen are:"
    agent_locations = [tuple(state["agents"][agent_id]["position"]) for agent_id in state["agents"]]
    for object_id in state["objects"]:
        if state["objects"][object_id]["position"] in agent_locations:  # ignore objects on agent locations
            continue
        prompt += "\n    " + state["objects"][object_id]["propertyOf"]["name"] + " at " + str(tuple(state["objects"][object_id]["position"]))
        if state["objects"][object_id]["propertyOf"]["name"] == "soup":
            prompt += " containing: " + ", ".join(state["objects"][object_id]["propertyOf"]["title"].split(":")[1].split("+")) + ". Cooking: " + str(state["objects"][object_id]["propertyOf"]["isCooking"]) + ", Ready: " + str(state["objects"][object_id]["propertyOf"]["isReady"])
    prompt += "\n"
    prompt += "\nThe chefs in the kitchen are:"
    for agent_id in state["agents"]:
        prompt += "\n    " + agent_id + " at " + str(tuple(state["agents"][agent_id]["position"]))
        prompt += " facing " + ("up" if state["agents"][agent_id]["facing"] == (0, 1) else "right" if state["agents"][agent_id]["facing"] == (1, 0) else "down" if state["agents"][agent_id]["facing"] == (0, -1) else "left" if state["agents"][agent_id]["facing"] == (-1, 0) else "INVALID FACING!")
        prompt += " and holding " + ("nothing" if state["agents"][agent_id]["holding"] is None else state["objects"][state["agents"][agent_id]["holding"]]["propertyOf"]["name"])
    return prompt


# formulate the prompt from the question
def get_prompt_question(question:str, answers:list):
    prompt = "Please answer the question as A1, using only one of responses below."
    prompt += "\n\nThe question is: " + question
    prompt += "\n\nYou can answer with only one of:"
    for answer in answers:
        prompt += "\n    - " + answer

    prompt += "\n\nWhat is your answer?"
    return prompt


# get the answers that correspond to a question
def get_question_answers(question):
    if question.startswith("where is the nearest available"):
        return ["Left half", "Right half", "Center-ish", "None available", "No idea"]
    if question.startswith("is there at least one available"):
        return ["Definite YES", "Likely YES", "No idea", "Likely NO", "Definite NO"]
    if question.startswith("where is your"):
        return ["Top Left", "Top Right", "Center or In-Between", "Bottom Left", "Bottom Right"]
    if question.startswith("where are you"):
        return ["Top Left", "Top Right", "Center or In-Between", "Bottom Left", "Bottom Right"]
    if question.startswith("how full is the"):
        return ["Empty", "1-2 ingredients", "3 ingredients (full/cooking)", "No idea"]
    if "pot's status" in question:
        return ["Finished cooking", "Cooking", "1-2 ingredients", "Empty", "No idea"]
    if question.startswith("what are you doing now"):
        return ["Getting ingredient for pot", "Getting dish for soup", "Bringing soup to station", "Idling, all soups complete"]
    if question.startswith("what is your teammate doing now"):
        return ["Getting ingredient for pot", "Getting dish for soup", "Bringing soup to station", "Idling, all soups complete", "No idea"]
    if question.startswith("how many more soups can be made"):
        return ["No soups", "1-2 soups", "3-4 soups", "5+ soups", "No idea"]
    if question.startswith("do you think your team will complete all the dishes in time"):
        return ["YES or already complete", "Probably YES", "Not sure", "Probably NO", "Definite NO"]
    raise ValueError("Unaccounted for question:" + str(question))


# write the grade to a file
def record_grade(visibility, iter, question, user_answer, llm_answer, score, round):
    with open("./llm_outputs_" + visibility + ".txt", "a+") as f:
        f.write("\n" + str(iter) + "|" + question + "|" + user_answer + "|" + llm_answer + "|" + score + "|" + str(round))

# process the LLM results
def process_llm_results():
    LP_O4_mean, LP_O4_variance = get_lp_mean_variance("O4")
    LP_O9_mean, LP_O9_variance = get_lp_mean_variance("O9")

    if LP_O4_mean is None or LP_O4_variance is None or LP_O9_mean is None or LP_O9_variance is None:
        raise ValueError("Missing linear predicates responses")
    
    LLM_results_O4 = []
    LLM_results_O9 = []

    with open("./llm_outputs_O4.txt", "r") as f:
        lines = f.readlines()
        for line in lines:
            if line != "\n":
                LLM_results_O4.append(int(float(line.replace("\n", "").split("|")[4])))
    
    with open("./llm_outputs_O9.txt", "r") as f:
        lines = f.readlines()
        for line in lines:
            if line != "\n":
                LLM_results_O9.append(int(float(line.replace("\n", "").split("|")[4])))
    
    O4_mean = sum(LLM_results_O4) / len(LLM_results_O4)
    O4_variance = statistics.variance(LLM_results_O4)

    O9_mean = sum(LLM_results_O9) / len(LLM_results_O9)
    O9_variance = statistics.variance(LLM_results_O9)

    return O4_mean, O4_variance, O9_mean, O9_variance, LP_O4_mean, LP_O4_variance, LP_O9_mean, LP_O9_variance


def get_lp_mean_variance(visibility:str):
    # load the data
    responses_by_round, responses_by_user, responses_by_user_and_round, responses_by_question, scores_by_user_and_round = load_data(visibility=visibility)
    
    # get all responses and the game state at that point
    iter = 1
    max_iter = 40
    results = []
    for user in responses_by_user_and_round:
        for round in responses_by_user_and_round[user]:
            for question in responses_by_user_and_round[user][round]:
                for response in responses_by_user_and_round[user][round][question]:
                    if iter > max_iter:
                        return sum(results) / len(results), statistics.variance(results)
                    
                    lp_response = response[7]  # estimated human response
                    print("( Iter", iter, ") ( User Response:", response[0],") ( LP Response:", lp_response, ")")
                    score = grader.score_response(question, lp_response, response[0])
                    print("[Score]", score)
                    results.append(score)
                    
                    iter += 1

    return sum(results) / len(results), statistics.variance(results)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        visibility = sys.argv[1]
    else:
        LP_O4_mean, LP_O4_variance = get_lp_mean_variance("O4")
        LP_O9_mean, LP_O9_variance = get_lp_mean_variance("O9")
        process_llm_results(LP_O4_mean=LP_O4_mean, LP_O4_variance=LP_O4_variance, LP_O9_mean=LP_O9_mean, LP_O9_variance=LP_O9_variance)
        sys.exit()
    idx = 1
    if len(sys.argv) > 2:
        idx = int(sys.argv[2])

    # load the data
    responses_by_round, responses_by_user, responses_by_user_and_round, responses_by_question, scores_by_user_and_round = load_data(visibility=visibility)
    
    # get all responses and the game state at that point
    iter = 1
    for user in responses_by_user_and_round:
        for round in responses_by_user_and_round[user]:
            for question in responses_by_user_and_round[user][round]:
                for response in responses_by_user_and_round[user][round][question]:
                    if iter < idx:  # ignore ones we have already done
                        iter += 1
                        continue

                    answers = get_question_answers(question)
                    prompt = get_prompt_header()
                    prompt += "\n\n"
                    prompt += get_prompt_state(response[-1])
                    prompt += "\n\n"
                    prompt += get_prompt_question(question, answers)
                    print(prompt)
                    pyperclip.copy(prompt)
                    print("( Iter", iter, ") ( User Response:", response[0],")")
                    llm_response = input()
                    score = str(grader.score_response(question, llm_response, response[0]))
                    print("[Score]", score)
                    record_grade(visibility=visibility, iter=iter, question=question, user_answer=response[0], llm_answer=llm_response, score=score, round=round)
                    iter += 1
