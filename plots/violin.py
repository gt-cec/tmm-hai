import matplotlib
import numpy
import math

cmap = matplotlib.cm.Wistia  # color map, this should be set at some point 

def plot_violin_scores_by_round(scores_by_user_and_round:dict, category=None, responses=None, visibility=None):
    if category is None:  # check if category exists
        raise ValueError("Category must be specified!")

    score_category = category  # TODO: change the score dict to have the same categories as the responses dict!
    if category == "human wrt user":
        score_category = "estimated wrt user"
    elif category == "robot wrt full":
        score_category = "agent wrt full"
    elif category not in ["user wrt full", "full wrt user", "agent wrt full", "agent wrt user", "human wrt full", "human wrt user"]:  # check if category is valid
        raise ValueError("Category is not valid!")

    # format the scores as {round : [user1 score, user2 score, ...]}
    scores = {}
    for user in scores_by_user_and_round:
        for round in scores_by_user_and_round[user]:
            if len(responses[user][round]) == 0:
                continue
            if round not in scores:  # add the round to the dict if it is not already there
                scores[round] = []
            num_questions = len(responses[user][round]) if len(responses[user][round]) >= scores_by_user_and_round[user][round][score_category] else math.ceil(scores_by_user_and_round[user][round][score_category])
            scores[round].append(scores_by_user_and_round[user][round][score_category] / num_questions)  # the category is which score w.r.t. which model is used

    scores = [scores[x] for x in scores]
    

    print("Violins: Num users", len(scores_by_user_and_round))

    ax = matplotlib.pyplot.subplot(111)
    parts = ax.violinplot(scores, showmedians=True, showextrema=False)

    for i in range(len(parts["bodies"])):  # set the violin face colors
        parts["bodies"][i].set_facecolor(cmap((i+0.5) / len(parts["bodies"])))
        parts["bodies"][i].set_alpha(1)

    for partname in ['cmedians']:  # set the violin median colors
        vp = parts[partname]
        vp.set_edgecolor('white')
        vp.set_linewidth(3)

    if category == "user wrt full":
        ax.set_title("User Scores at Each Round")
    elif category == "robot wrt full":
        ax.set_title("Robot Scores w.r.t. Ground Truth at Each Round\n(Visibility: " + visibility + ")")
    elif category == "agent wrt user":
        ax.set_title("Robot Scores w.r.t. Predicted User Belief State at Each Round\n(Robot Visibility: " + visibility + ")")

    ax.set_xticks(ticks=[1, 2, 3, 4], labels=["Layout 1", "Layout 2", "Layout 3", "Layout 4"])
    ax.tick_params(axis='x', which='both', bottom=False, top=False)
    ax.set_xlim([0.5, 4.5])

    ax.set_yticks(ticks=[0, .25, .5, .75, 1.0], labels=["0%", "25%", "50%", "75%", "100%"])

    if category == "user wrt full":
        ax.set_ylabel("User Score")
    elif category == "robot wrt full":
        ax.set_ylabel("Robot Score")
    elif category == "agent wrt user":
        ax.set_ylabel("Robot Score")

    ax.spines["top"].set_visible(False)
    ax.spines["bottom"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.spines["right"].set_visible(False)
    matplotlib.pyplot.show()