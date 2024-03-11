# visualize_results.py: plots useful data visualizations

import numpy
import matplotlib.pyplot
import plots.confusion
import plots.histogram
import plots.line
import plots.violin
import pickle
import grader  # for some lookup tables

# create the color map
colors = [(0, (1, 1, 1)), (.1, (1, 0.517, 0.156)), (.25, (1, .466, .168)), (.4, (1, .364, .137)), (.55, (1, .305, .196)), (.7, (.980, .282, .227)), (.85, (.866, .215, .180)), (.9, (.713, .176, .160)), (1, (.556, .223, .184))]
cmap = matplotlib.colors.LinearSegmentedColormap.from_list('custom_cmap', colors)
plots.confusion.cmap = cmap
plots.histogram.cmap = cmap
plots.line.cmap = cmap
plots.violin.cmap = cmap

# set some matplotlib settings
matplotlib.rcParams["font.sans-serif"] = "Roboto"
matplotlib.rcParams["font.size"] = 15

# load the pickled data
def load_data(path="./processed_data/"):
    with open(path + "smm_responses_by_round.pkl", "rb") as f:
        responses_by_round = pickle.load(f)
    with open(path + "smm_responses_by_user.pkl", "rb") as f:
        responses_by_user = pickle.load(f)
    with open(path + "smm_responses_by_user_and_round.pkl", "rb") as f:
        responses_by_user_and_round = pickle.load(f)
    with open(path + "smm_responses_by_question.pkl", "rb") as f:
        responses_by_question = pickle.load(f)
    with open(path + "smm_scores_by_user_and_round.pkl", "rb") as f:
        scores_by_user_and_round = pickle.load(f)
    print("Loaded results data.")
    return responses_by_round, responses_by_user, responses_by_user_and_round, responses_by_question, scores_by_user_and_round

# when this script is run
if __name__ == "__main__":
    # load the data
    responses_by_round, responses_by_user, responses_by_user_and_round, responses_by_question, scores_by_user_and_round = load_data()

    ### plot the line graph of user performance over each round
    plots.line.plot_line_matrix_scores_by_round(scores_by_user_and_round, category="user wrt full")

    ### plot the violin plot of performances at each round
    # plots.violin.plot_violin_scores_by_round(scores_by_user_and_round, category="user wrt full")

    ### plot the question frequency histogram
    # plots.histogram.plot_histogram_question_frequency(responses_by_question)

    ### plot the score distribution histogram
    plots.histogram.plot_histogram_score_all_rounds(responses_by_user_and_round, category="user wrt full")  # one histogram for user average for all rounds
    # plots.histogram.plot_histogram_score_each_round(responses_by_user_and_round, category="user wrt full")
    plots.histogram.plot_histogram_score_all_rounds(responses_by_user_and_round, category="full wrt user")
    # plots.histogram.plot_histogram_score_each_round(responses_by_user_and_round, category="full wrt user")
    plots.histogram.plot_histogram_score_all_rounds(responses_by_user_and_round, category="robot wrt full")
    # plots.histogram.plot_histogram_score_each_round(responses_by_user_and_round, category="robot wrt full")
    plots.histogram.plot_histogram_score_all_rounds(responses_by_user_and_round, category="robot wrt user")
    # plots.histogram.plot_histogram_score_each_round(responses_by_user_and_round, category="robot wrt user")
    plots.histogram.plot_histogram_score_all_rounds(responses_by_user_and_round, category="human wrt full")
    # plots.histogram.plot_histogram_score_each_round(responses_by_user_and_round, category="human wrt full")
    plots.histogram.plot_histogram_score_all_rounds(responses_by_user_and_round, category="human wrt user")
    # plots.histogram.plot_histogram_score_each_round(responses_by_user_and_round, category="human wrt user")

    ### plot the responses for each user
    # plots.confusion.plot_confusion_question_responses(responses_by_question, model="user")  # confusion matrix of the user responses to each question
    # plots.confusion.plot_confusion_question_responses(responses_by_question, model="user", category="available")
    # plots.confusion.plot_confusion_question_responses(responses_by_question, model="user", category="where ingredient")
    # plots.confusion.plot_confusion_question_responses(responses_by_question, model="user", category="where agent")
    # plots.confusion.plot_confusion_question_responses(responses_by_question, model="user", category="state agent")
    # plots.confusion.plot_confusion_question_responses(responses_by_question, model="user", category="fullness pot")
    # plots.confusion.plot_confusion_question_responses(responses_by_question, model="user", category="state pot")
    # plots.confusion.plot_confusion_question_responses(responses_by_question, model="user", category="remaining soup")

    ### plot the ground truth responses
    # plots.confusion.plot_confusion_question_responses(responses_by_question, model="ground truth")  # confusion matrix of the true responses to each question
    # plots.confusion.plot_confusion_question_responses(responses_by_question, model="ground truth", category="available")
    # plots.confusion.plot_confusion_question_responses(responses_by_question, model="ground truth", category="where ingredient")
    # plots.confusion.plot_confusion_question_responses(responses_by_question, model="ground truth", category="where agent")
    # plots.confusion.plot_confusion_question_responses(responses_by_question, model="ground truth", category="state agent")
    # plots.confusion.plot_confusion_question_responses(responses_by_question, model="ground truth", category="fullness pot")
    # plots.confusion.plot_confusion_question_responses(responses_by_question, model="ground truth", category="state pot")
    # plots.confusion.plot_confusion_question_responses(responses_by_question, model="ground truth", category="remaining soup")