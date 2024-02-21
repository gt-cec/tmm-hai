import grader  # for running through a user and grading them with the various SMMs
import pickle  # for saving pickled data
import os  # for pulling all files in a directory

def main():
    question_responses = {}  # responses invariant to the user nor round
    round_responses = {}  # responses for each round, invariant of the user
    user_responses = {}  # responses for each user, invariant of the round
    structured_responses = {}  # responses for each user, for each round

    log_path = "./env/server/logs/"  # path of user data logs 

    processed_user_data_path = "./processed_data/"  # path of processed data logs
    processed_users = [x.replace(".pkl", "") for x in os.listdir(processed_user_data_path)]  # all processed data file names, removing the .pkl extension

    # for each user
    for user in os.listdir(log_path):
        user = user.replace(".txt", "")  # remove the trailing .txt from the file name
        if user not in user_responses:  # ensure user is in the user responses
            user_responses[user] = {}
        if user not in structured_responses:  # ensure user is in the structured responses
            structured_responses[user] = {}

        # for each round
        for round in [1, 2, 3, 4]: 
            if round not in round_responses:  # ensure round is in round responses
                round_responses[round] = {}
            if round not in structured_responses[user]:  # ensure round is in the structured responses for the user
                structured_responses[user][round] = {}

            # run through the round and gather the Q/A for the user and mental models
            if user + "_" + str(round) in processed_users:  # if the user has already been processed, use that instead
                with open(processed_user_data_path + user + "_" + str(round) + ".pkl", "rb") as f:
                    user_data = pickle.load(f)
                    responses = user_data[0]
                    score = user_data[1]
                    num_questions = user_data[2]
            else:  # otherwise, process the user logs
                # this will create new SMMs, so data does not carry over between users and rounds
                responses, score, num_questions = grader.grade_user(user=user, round=round, debug=False)
                with open(processed_user_data_path + user + "_" + str(round) + ".pkl", "wb") as f:  # save the user's data
                    pickle.dump([responses, score, num_questions], f)
            
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
    with open(processed_user_data_path + "smm_results_by_question.pkl", "wb") as f:
        pickle.dump(question_responses, f)
    with open(processed_user_data_path + "smm_results_by_round.pkl", "wb") as f:
        pickle.dump(round_responses, f)
    with open(processed_user_data_path + "smm_results_by_user.pkl", "wb") as f:
        pickle.dump(user_responses, f)
    with open(processed_user_data_path + "smm_results_by_user_and_round.pkl", "wb") as f:
        pickle.dump(structured_responses, f)
    
    print("Processing complete! See the output .pkl files.")

main()