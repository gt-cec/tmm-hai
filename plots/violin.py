import matplotlib
import numpy

cmap = matplotlib.cm.Wistia  # color map, this should be set at some point 

def plot_violin_scores_by_round(scores_by_user_and_round:dict, category=None):
    if category is None:  # check if category exists
        raise ValueError("Category must be specified!")

    if category not in ["user wrt full", "full wrt user", "robot wrt full", "robot wrt user", "human wrt full", "human wrt user"]:  # check if category is valid
        raise ValueError("Category is not valid!")

    # format the scores as {round : [user1 score, user2 score, ...]}
    scores = {}
    for user in scores_by_user_and_round:
        for round in scores_by_user_and_round[user]:
            if round not in scores:  # add the round to the dict if it is not already there
                scores[round] = []
            scores[round].append(scores_by_user_and_round[user][round][category])  # the category is which score w.r.t. which model is used

    scores = [scores[x] for x in scores]

    ax = matplotlib.pyplot.subplot(111)
    parts = ax.violinplot(scores, showmedians=True, showextrema=False)

    for i in range(len(parts["bodies"])):  # set the violin face colors
        parts["bodies"][i].set_facecolor(cmap((i+0.5) / len(parts["bodies"])))
        parts["bodies"][i].set_alpha(1)

    for partname in ['cmedians']:  # set the violin median colors
        vp = parts[partname]
        vp.set_edgecolor('white')

    ax.set_title("User Scores at Each Round")

    ax.set_xticks(ticks=[1, 2, 3, 4], labels=["Round 1", "Round 2", "Round 3", "Round 4"])
    ax.tick_params(axis='x', which='both', bottom=False, top=False)
    ax.set_xlim([0.5, 4.5])

    ax.set_yticks(ticks=[0, 1, 2, 3, 4, 5, 6], )
    ax.set_ylabel("User Score")

    ax.spines["top"].set_visible(False)
    ax.spines["bottom"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.spines["right"].set_visible(False)
    matplotlib.pyplot.show()