import matplotlib
import numpy

cmap = matplotlib.cm.Wistia  # color map, this should be set at some point 

def plot_line_matrix_scores_by_round(scores_by_user_and_round:dict, category=None):
    if category is None:  # check if category exists
        raise ValueError("Category must be specified!")

    if category not in ["user wrt full", "full wrt user", "robot wrt full", "robot wrt user", "human wrt full", "human wrt user"]:  # check if category is valid
        raise ValueError("Category is not valid!")
    
    axes_rows = int(numpy.sqrt(len(scores_by_user_and_round))) + 1
    axes_cols = int(numpy.sqrt(len(scores_by_user_and_round))) + 1

    # format the scores as {round : [user1 score, user2 score, ...]}
    axes_idx = 1
    for user in scores_by_user_and_round:
        scores = []
        for round in scores_by_user_and_round[user]:
            scores.append(scores_by_user_and_round[user][round][category])  # the category is which score w.r.t. which model is used

        ax = matplotlib.pyplot.subplot(axes_rows, axes_cols, axes_idx)  # get the subplot for this user
        ax.plot(scores)

        ax.set_title(user)
        ax.set_xticks(ticks=[0, 1, 2, 3], labels=[1, 2, 3, 4])
        ax.set_xlim([-0.5, 3.5])
        ax.set_xlabel("Round")
        ax.set_ylim([0, 4.5])
        ax.set_yticks(ticks=[0, 1, 2, 3, 4])
        ax.set_ylabel("Score")

        ax.spines["top"].set_visible(False)  # remove spines
        ax.spines["right"].set_visible(False)

        axes_idx += 1

    matplotlib.pyplot.tight_layout()
    matplotlib.pyplot.show()
