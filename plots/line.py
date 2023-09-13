import matplotlib
import numpy
import math
import statistics

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
        ax.set_ylim([0, 6.5])
        ax.set_yticks(ticks=[0, 1, 2, 3, 4, 5, 6])
        ax.set_ylabel("Score")

        ax.spines["top"].set_visible(False)  # remove spines
        ax.spines["right"].set_visible(False)

        axes_idx += 1

    matplotlib.pyplot.tight_layout()
    matplotlib.pyplot.show()


def plot_line_scores_by_visibility(dict_of_scores_by_user_and_round:dict, dict_of_responses:dict, category=None):
    if category is None:  # check if category exists
        raise ValueError("Category must be specified!")

    if category not in ["user wrt full", "full wrt user", "robot wrt full", "robot wrt user", "human wrt full", "human wrt user"]:  # check if category is valid
        raise ValueError("Category is not valid!")
    
    if category == "human wrt user":
        category = "estimated wrt user"

    ax = matplotlib.pyplot.subplot(1, 1, 1)  # get the subplot for this user

    scores = []
    variances = []

    visibility_groups = {}  # groupings by O, D, V types

    for visibility in dict_of_scores_by_user_and_round:
        # Define data for each series
        round_scores = {}       
        for user in dict_of_scores_by_user_and_round[visibility]:
            for round in dict_of_scores_by_user_and_round[visibility][user]:
                if round not in round_scores:
                    round_scores[round] = []
                num_questions = len(dict_of_responses[visibility][user][round]) if len(dict_of_responses[visibility][user][round]) >= dict_of_scores_by_user_and_round[visibility][user][round][category] else math.ceil(dict_of_scores_by_user_and_round[visibility][user][round][category])
                round_scores[round].append(dict_of_scores_by_user_and_round[visibility][user][round][category] / num_questions)

        round_means = []
        round_variances = []

        for round in round_scores:
            round_mean = sum(round_scores[round]) / len(round_scores[round])
            round_means.append(round_mean)
            round_variance = statistics.variance(round_scores[round])
            round_variances.append(round_variance)

            if visibility[0] not in visibility_groups:
                visibility_groups[visibility[0]] = {}
                
            if round not in visibility_groups[visibility[0]]:
                visibility_groups[visibility[0]][round] = {"keys": [], "scores": [], "variances": []}

            visibility_groups[visibility[0]][round]["keys"].append("O9\n(Full)" if visibility == "O9" else "D9\n(Half)" if visibility == "D9" else "Quarter" if visibility == "V9" else visibility)
            visibility_groups[visibility[0]][round]["scores"].append(round_mean)
            visibility_groups[visibility[0]][round]["variances"].append(round_variance)
        
        scores.append(round_means)
        variances.append(round_variances)

        print("###", visibility_groups)

    keys = ["O9\n(Full)" if x == "O9" else "D9\n(Half)" if x == "D9" else "Quarter" if x == "V9" else x for x in dict_of_scores_by_user_and_round.keys()]

    colors = ["#604040", cmap(.60), cmap(.101), cmap(.90)]
    markers = ["o", "^", "s", "d"]

    for round in range(1, 5):
        for visibility in visibility_groups:
            # Create the plot
            ax.errorbar(visibility_groups[visibility[0]][round]["keys"], visibility_groups[visibility[0]][round]["scores"], visibility_groups[visibility[0]][round]["variances"], label="Layout " + str(round) if visibility[0] == "O" else "", color=colors[round-1], linewidth=3, marker=markers[round-1], markersize=10)

    # ax.plot(scores)

    ax.set_title("Score of " + r"$\beta^{pred}$" + " w.r.t. User Responses for Each Visibility Type\n(Error bars indicate variance)")
    # ax.set_xlim([-0.5, 3.5])
    ax.set_xlabel(r"Visibility ($R^{robot}$)", fontsize=27)
    ax.set_ylim([0, 1.0])
    ax.set_yticks(ticks=[0, .25, .5, .75, 1], labels=["", "25%", "50%", "75%", "100%"])
    ax.set_ylabel(r"Score of $\beta^{pred}$ Using $\mathcal{B}^{LP}$", fontsize=27)

    ax.spines["top"].set_visible(False)  # remove spines
    ax.spines["right"].set_visible(False)
    legend = ax.legend(loc="lower right")
    legend.get_frame().set_linewidth(0)  # Remove legend border
    legend.get_frame().set_facecolor('none')  # Remove legend background color

    matplotlib.pyplot.tight_layout()
    matplotlib.pyplot.show()
