import matplotlib
import numpy

cmap = matplotlib.cm.Wistia  # color map, this should be set at some point 


# plot a histogram of the frequency of each question
def plot_histogram_question_frequency(responses_by_question:dict):
    data = {k.replace(" make your best guess.", "").replace(",", ",\n").capitalize() : len(responses_by_question[k]) for k in responses_by_question}

    sa_level_1 = {k:data[k] for k in sorted(data.keys()) if "how full" in k.lower() or "where is" in k.lower() or "is there" in k.lower()}
    sa_level_2 = {k:data[k] for k in sorted(data.keys()) if "how full" in k.lower() or "what is" in k.lower() or "what are" in k.lower() or "how many more soups" in k.lower()}

    data = sa_level_1 | sa_level_2

    x = data.values()

    ax = matplotlib.pyplot.subplot(111)
    bars = ax.bar(data.keys(), x, align="center")

    # set the annotation for level 1 SA
    x_min = 0.04
    x_max = 1 / len(data) * len(sa_level_1) - 0.02
    matplotlib.pyplot.axhline(y=90, xmin=x_min, xmax=x_max, color='grey', linestyle='-')
    matplotlib.pyplot.text((len(sa_level_1)+1) / 2, 92, "World State (Level 1) [" + str(sum(sa_level_1.values())) + "]", fontsize=13, ha="right")

    # set the annotation for level 2 SA
    x_min = 1 / len(data) * len(sa_level_1) + 0.01
    x_max = 0.95
    matplotlib.pyplot.axhline(y=90, xmin=x_min, xmax=x_max, color='grey', linestyle='-')
    matplotlib.pyplot.text((len(sa_level_1)+len(data)+1) / 2, 92, "Context (Level 2) [" + str(sum(sa_level_2.values())) + "]", fontsize=13, ha="right")

    max_val = max(x) * 1.5  # multiply so we get a nice max color

    # Use custom colors and opacity
    for r, bar in zip(x, bars):
        bar.set_facecolor(cmap(r / max_val))
        bar.set_alpha(1)

    matplotlib.pyplot.title("Question Frequency")

    ax.set_xticks(range(len(data.keys())))
    ax.set_xticklabels(data.keys(), ha="right")

    # matplotlib.pyplot.xticks(fontsize=12)
    matplotlib.pyplot.ylabel("Count")
    matplotlib.pyplot.ylim([0, 100])

    matplotlib.pyplot.xticks(rotation=30)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    matplotlib.pyplot.tight_layout()
    matplotlib.pyplot.show()


# plot a histogram of the scores of users, across all rounds
def plot_histogram_score_all_rounds(responses_by_user_and_round:dict, category:str="user wrt full", save=False):
    scores = []
    for user in responses_by_user_and_round:
        user_scores = []
        for round in responses_by_user_and_round[user]:
            for question in responses_by_user_and_round[user][round]:
                for instance in responses_by_user_and_round[user][round][question]:
                    # instance: [user_response, true_response, _user_score_wrt_true, _true_score_wrt_user, agent_response, _agent_score_wrt_true, _agent_score_wrt_user, estimated_human_response, _estimated_human_score_wrt_true, _estimated_human_score_wrt_user]
                    if category == "user wrt full":
                        user_scores.append(instance[2])
                        title = "Scores of User Responses w.r.t. Full-Observability Responses"
                    elif category == "full wrt user":
                        user_scores.append(instance[3])
                        title = "Scores of Full-Observability Responses w.r.t. User Responses"
                    elif category == "robot wrt full":
                        user_scores.append(instance[5])
                        title = "Scores of Robot Agent Responses w.r.t. Full-Observability Responses"
                    elif category == "robot wrt user":
                        user_scores.append(instance[6])
                        title = "Scores of Robot Agent Responses w.r.t. User Responses"
                    elif category == "human wrt full":
                        user_scores.append(instance[8])
                        title = "Scores of Estimated Human Responses w.r.t. Full-Observability Responses"
                    elif category == "human wrt user":
                        user_scores.append(instance[9])
                        title = "Scores of Estimated Human Responses w.r.t. User Responses"
        if len(user_scores) == 0:
            print("User had no scores, perhaps discard them:", user)
            # raise ValueError("User had no scores, perhaps discard them: " + str(user))
            continue
        scores.append(sum(user_scores) / len(user_scores))

    if save:
        matplotlib.pyplot.gcf().set_dpi(1500)

    make_histogram(raw_values=scores, title=title if not save else "", y_label="Count", y_max=8, x_label=("Mean Score for Each User" if not save else "Mean " + title.replace("Scores", "Score")) + "\n[0-1, higher is better]", x_max=1, x_tick_frequency=0.1, x_proportion=True)
    
    if save:
        matplotlib.pyplot.gcf().tight_layout()
        matplotlib.pyplot.savefig(title.replace(".", "") + ".svg", bbox_inches='tight', transparent="True", pad_inches=0)
    matplotlib.pyplot.show()

# plot a histogram of the scores of users, for each round
def plot_histogram_score_each_round(responses_by_user_and_round:dict, category:str=""):
    scores = {}
    title = "Generic Title"

    # pull the scores
    for user in responses_by_user_and_round:
        for round in responses_by_user_and_round[user]:
            if round not in scores:
                scores[round] = {}
            if user not in scores[round]:
                scores[round][user] = []
            for question in responses_by_user_and_round[user][round]:
                for instance in responses_by_user_and_round[user][round][question]:
                    # instance: [user_response, true_response, _user_score_wrt_true, _true_score_wrt_user, agent_response, _agent_score_wrt_true, _agent_score_wrt_user, estimated_human_response, _estimated_human_score_wrt_true, _estimated_human_score_wrt_user]
                    if category == "user wrt full":
                        scores[round][user].append(instance[2])
                        title = "Scores of User Responses w.r.t. Full-Observability Responses"
                    elif category == "full wrt user":
                        scores[round][user].append(instance[3])
                        title = "Scores of Full-Observability Responses w.r.t. User Responses"
                    elif category == "robot wrt full":
                        scores[round][user].append(instance[5])
                        title = "Scores of Robot Agent Responses w.r.t. Full-Observability Responses"
                    elif category == "robot wrt user":
                        scores[round][user].append(instance[6])
                        title = "Scores of Robot Agent Responses w.r.t. User Responses"
                    elif category == "human wrt full":
                        scores[round][user].append(instance[8])
                        title = "Scores of Estimated Human Responses w.r.t. Full-Observability Responses"
                    elif category == "human wrt user":
                        scores[round][user].append(instance[9])
                        title = "Scores of Estimated Human Responses w.r.t. User Responses"
            
            if len(responses_by_user_and_round[user][round]) == 0:
                print("User had no scores, perhaps discard them:", user, round)
                # raise ValueError("User had no scores, perhaps discard them: " + str(user))
                continue
            
    # Create a figure and a grid of subplots
    fig, axs = matplotlib.pyplot.subplots(2, 2)

    # average the scores
    for round in scores:
        scores[round] = [sum(scores[round][u]) / len(scores[round][u]) for u in scores[round] if len(scores[round][u]) > 0]
        make_histogram(raw_values=scores[round], title=title + "\nRound " + str(round), y_label="Count", y_max=10, x_label="Score", x_max=1, x_tick_frequency=0.1, ax=axs[((round + 1) // 2) - 1, (round + 1) % 2])
    matplotlib.pyplot.show()

# base histogram
def make_histogram(frequencies={}, raw_values=[], title="", y_label="", x_label="", y_max=None, x_max=None, x_tick_frequency=None, ax=None, x_proportion=False):
    if raw_values == [] and frequencies == {}:
        raise ValueError("Either frequencies or raw values need to be defined.")
    
    ax = ax if ax is not None else matplotlib.pyplot.subplot(111)
    
    max_val = max(frequencies.values() if frequencies != {} else raw_values)
    num_items = len(frequencies) if frequencies != {} else len(raw_values)
    x_max = x_max if x_max is not None else num_items
    y_max = y_max if y_max is not None else max_val + 5 - (max_val % 5)

    if raw_values != []:
        _, _, patches = ax.hist(x=raw_values, bins=numpy.arange(0, 1, 0.1 if x_tick_frequency is None else x_tick_frequency), align="mid", facecolor=cmap(.1), edgecolor="white", linewidth=2)
        # for i in range(len(patches)):
        #     color = cmap(1 - patches[i].get_height() / y_max)
        #     patches[i].set_facecolor(color)

    elif frequencies != {}:
        bars = ax.bar(frequencies.keys(), frequencies.values(), align="center")
        # for r, bar in zip(frequencies.values(), bars):
        #     bar.set_facecolor(cmap(1 - r / max_val))
        #     bar.set_alpha(1)

    ax.set_title(title)
    # fontsize = 12

    if x_tick_frequency is not None:
        ax.set_xticks(numpy.arange(0, 1.01, x_tick_frequency))

    ax.set_xlabel(x_label)#, fontsize=fontsize)
    ax.set_xlim([0, x_max])

    ax.set_ylabel(y_label)#, fontsize=fontsize)
    ax.set_ylim([0, y_max])

    ax.tick_params(axis='both', which='major', length=0)#, labelsize=fontsize, length=0)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    matplotlib.pyplot.tight_layout()
    
    return ax