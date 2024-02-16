import grader  # for running through a user and grading them with the various SMMs
import pickle  # for saving pickled data
import os  # for pulling all files in a directory

def main():
    question_responses = {}  # responses invariant to the user nor round
    round_responses = {}  # responses for each round, invariant of the user
    user_responses = {}  # responses for each user, invariant of the round
    structured_responses = {}  # responses for each user, for each round

    log_path = "./env/server/logs/"

    # for each user
    for user in os.listdir(log_path):
        user = user.replace(".txt", "")
        if user not in user_responses:  # ensure user is in the user responses
            user_responses[user] = {}
        if user not in structured_responses:  # ensure user is in the structured responses
            structured_responses[user] = {}

        # for each round
        for round in [2, 3, 4, 5]: 
            if round not in round_responses:  # ensure round is in round responses
                round_responses[round] = {}
            if round not in structured_responses[user]:  # ensure round is in the structured responses for the user
                structured_responses[user][round] = {}
            responses, score, num_questions = grader.grade_user(user=user, round=round)
            
            # for each question in the responses
            for question in responses:
                if question not in question_responses:  # ensure question is in question responses
                    question_responses[question] = []
                if question not in round_responses:  # ensure question is in round responses for the round
                    round_responses[round][question] = []
                if question not in user_responses:  # ensure question is in user responses for the user
                    user_responses[user][question] = []
                if question not in structured_responses[user][round]:  # ensure question is in structured responses for the user and round
                    structured_responses[user][round][question] = []
                
                # for each response to the question
                for response in responses[question]:
                    question_responses[question].append(response)
                    round_responses[round][question].append(response)
                    user_responses[user][question].append(response)
                    structured_responses[user][round][question].append(response)

    # save the responses
    with open("./processed_data/smm_results_by_question.pkl", "wb") as f:
        pickle.dump(question_responses, f)
    with open("./processed_data/smm_results_by_round.pkl", "wb") as f:
        pickle.dump(round_responses, f)
    with open("./processed_data/smm_results_by_user.pkl", "wb") as f:
        pickle.dump(user_responses, f)
    with open("./processed_data/smm_results_by_user_and_round.pkl", "wb") as f:
        pickle.dump(structured_responses, f)
    
    print("Processing complete! See the output .pkl files.")

main()