# visualize_results.py: plots useful data visualizations

import numpy
import matplotlib.pyplot
import pandas
import pickle
import seaborn
import grader  # for some lookup tables

# load the pickled data
def load_data(path="./processed_data/"):
    with open(path + "smm_results_by_round.pkl", "rb") as f:
        results_by_round = pickle.load(f)
    with open(path + "smm_results_by_user.pkl", "rb") as f:
        results_by_user = pickle.load(f)
    with open(path + "smm_results_by_user_and_round.pkl", "rb") as f:
        results_by_user_and_round = pickle.load(f)
    with open(path + "smm_results_by_question.pkl", "rb") as f:
        results_by_question = pickle.load(f)
    print("Loaded results data.")
    return results_by_round, results_by_user, results_by_user_and_round, results_by_question
    

# plot a histogram of the frequency of each question
def plot_histogram_question_frequency(results_by_question:dict):
    data = {k.replace(" make your best guess.", "").replace(",", ",\n").capitalize() : len(results_by_question[k]) for k in results_by_question}

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
        bar.set_facecolor(matplotlib.pyplot.cm.RdPu(r / max_val))
        bar.set_alpha(1)

    matplotlib.pyplot.title("Question Frequency")

    ax.set_xticks(range(len(data.keys())))
    ax.set_xticklabels(data.keys(), ha="right")

    matplotlib.pyplot.xticks(fontsize=12)
    matplotlib.pyplot.ylabel("Count")
    matplotlib.pyplot.ylim([0, 100])

    if False:
        ax.set(yticklabels=[])
        ax.get_yaxis().set_ticks([])
        ax.spines["left"].set_visible(False)

    matplotlib.pyplot.xticks(rotation=30)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    matplotlib.pyplot.tight_layout()
    matplotlib.pyplot.show()


# plot a histogram of the scores of users, across all rounds
def plot_histogram_score_all_rounds(results_by_user_and_round:dict):
    scores = []
    for user in results_by_user_and_round:
        user_scores = []
        for round in results_by_user_and_round[user]:
            for question in results_by_user_and_round[user][round]:
                for instance in results_by_user_and_round[user][round][question]:
                    # instance: [user_response, ground_truth_response, _score, smm_ground_truth.belief_state]
                    user_scores.append(instance[2])
        if len(user_scores) == 0:
            raise ValueError("User had no scores, perhaps discard them: " + str(user))
        scores.append(sum(user_scores) / len(user_scores))

    make_histogram(raw_values=scores, title="Overall Score Distribution", y_label="Count", x_label="Score", x_max=1, x_tick_frequency=0.1)
    matplotlib.pyplot.show()

# plot a histogram of the scores of users, for each round
def plot_histogram_score_each_round(results_by_user_and_round:dict):
    scores = {}

    # pull the scores
    for user in results_by_user_and_round:
        for round in results_by_user_and_round[user]:
            if round not in scores:
                scores[round] = {}
            if user not in scores[round]:
                scores[round][user] = []
            for question in results_by_user_and_round[user][round]:
                for instance in results_by_user_and_round[user][round][question]:
                    # instance: [user_response, ground_truth_response, _score, smm_ground_truth.belief_state]
                    scores[round][user].append(instance[2])
            
            if len(results_by_user_and_round[user][round]) == 0:
                raise ValueError("User had no scores, perhaps discard them: " + str(user) + " round " + str(round))
            
    # Create a figure and a grid of subplots
    fig, axs = matplotlib.pyplot.subplots(2, 2)

    # average the scores
    for round in scores:
        scores[round] = [sum(scores[round][u]) / len(scores[round][u]) for u in scores[round]]
        make_histogram(raw_values=scores[round], title="Round " + str(round) + " Score Distribution", y_label="Count", x_label="Score", x_max=1, x_tick_frequency=0.1, ax=axs[((round + 1) // 2) - 1, (round + 1) % 2])
    matplotlib.pyplot.show()

# base histogram
def make_histogram(frequencies={}, raw_values=[], title="", y_label="", x_label="", y_max=None, x_max=None, x_tick_frequency=None, ax=None):
    ax = ax if ax is not None else matplotlib.pyplot.subplot(111)
    
    max_val = max(frequencies.values() if frequencies != {} else raw_values)
    num_items = len(frequencies) if frequencies != {} else len(raw_values)
    x_max = x_max if x_max is not None else num_items
    y_max = y_max if y_max is not None else max_val + 5 - (max_val % 5)

    if raw_values != []:
        _, _, patches = ax.hist(x=raw_values, bins=numpy.arange(0, 1, 0.1 if x_tick_frequency is None else x_tick_frequency), align="mid", edgecolor="white", linewidth=2)
        for i in range(len(patches)):
            color = matplotlib.pyplot.cm.RdPu(1 - patches[i].get_height() / y_max)
            patches[i].set_facecolor(color)

    elif frequencies != {}:
        bars = ax.bar(frequencies.keys(), frequencies.values(), align="center")
        # Use custom colors and opacity
        for r, bar in zip(frequencies.values(), bars):
            bar.set_facecolor(matplotlib.pyplot.cm.RdPu(1 - r / max_val))
            bar.set_alpha(1)

    ax.set_title(title)
    fontsize = 12

    if x_tick_frequency is not None:
        ax.set_xticks(numpy.arange(0, 1.01, x_tick_frequency))

    ax.set_xlabel(x_label, fontsize=fontsize)
    ax.set_xlim([0, x_max])

    ax.set_ylabel(y_label, fontsize=fontsize)
    ax.set_ylim([0, y_max])

    ax.tick_params(axis='both', which='major', labelsize=fontsize, length=0)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    matplotlib.pyplot.tight_layout()
    
    return ax

# plot a confusion matrix of the responses to questions
#  model: "user", "ground truth"
#  category: category of questions to plot, otherwise "all"
def plot_confusion_question_responses(results_by_question, model:str="user", category:str="all"):
    if model not in ["user", "ground truth"]:
        raise ValueError("'model' parameter must be in 'user', 'ground truth'")

    
    all_questions = ['Is there at least one available onion', 'Is there at least one available tomato',
                    'Where is the nearest available onion', 'Where is the nearest available tomato',
                    'Where are you', 'Where is your teammate',
                    'What are you doing now', 'What is your teammate doing now',
                    'How full is the leftmost pot', 'How full is the rightmost pot',
                    "What is the leftmost pot's status", "What is the rightmost pot's status",
                    'How many more soups can be made/delivered']
    
    availability_responses = ['Definite yes', 'Likely yes', 'Likely no', 'Definite no']
    location_rough_responses = ['Left half', 'Right half', 'Center-ish', 'None available']
    location_precise_responses = ['Top left', 'Top right', 'Bottom left', 'Bottom right', 'Center']
    agent_state_responses = ['Getting ingredient for pot', 'Getting dish for soup', 'Idling, all soups complete', 'Bringing soup to station']
    pot_fullness_responses = ['Empty', '1-2 ingredients', '3 ingredients (full/cooking)']
    pot_state_responses = ['Empty', '1-2 ingredients', 'Cooking', 'Finished cooking']
    soups_remaining_responses = ['No soups', '1-2 soups', '3-4 soups', '5+ soups']
    
    # definitions of each question category
    category_map = {
        "available": {"title": "Availability of Ingredients (Level 1)", "filters": ["at least"], "responses": availability_responses},
        "where ingredient": {"title": "Location of Ingredients (Level 1)", "filters": ["where is the nearest available"], "responses": location_rough_responses},
        "where agent": {"title": "Location of Agents (Level 1)", "filters": ["where is your teammate", "where are you"], "responses": location_precise_responses},
        "state agent": {"title": "State of Agents (Level 2)", "filters": ["what is your", "what are you"], "responses": agent_state_responses},
        "fullness pot": {"title": "Fullness of Pots (Level 1)", "filters": ["how full"], "responses": pot_fullness_responses},
        "state pot": {"title": "State of Pots (Level 2)", "filters": ["pot's status"], "responses": pot_state_responses},
        "remaining soup": {"title": "Remaining Soups (Level 2)", "filters": ["how many more"], "responses": soups_remaining_responses},
        "all": {"title": "All (Level 1, 2)", "filters": [], "responses": [],}
    }

    if category not in category_map:
        raise ValueError("'category' parameter must be in '" + "', '".join(category_map.keys()) + "'")
    
    # dedupe and add all category responses to the all category
    if category == "all":
        all_responses = availability_responses + location_rough_responses + location_precise_responses + agent_state_responses + pot_fullness_responses + pot_state_responses + soups_remaining_responses
        [category_map["all"]["responses"].append(x) for x in all_responses if x not in category_map["all"]["responses"]]

    # choose questions based on the category specified
    questions = {}
    for question in all_questions:
        if category == "all":  # if all, check all categories
            categories = category_map.keys()
        else:  # otherwise, check only the provided category
            categories = [category]
        for _category in categories:  # for each category
            for filter in category_map[_category]["filters"]:  # for each question filter
                if filter in question.lower():  # if the filter is in the question
                    # add the question to the questions dictionary
                    for key in results_by_question:  
                        if question.lower() in key:
                            _key = key.replace(" make your best guess.", "").replace(", including soups in-progress?", "?")  # remove extraneous parts of the question
                            questions[_key] = {"category": _category, "instances": results_by_question[key]}

    # format the results to [question, answer] pairs
    values = []
    for question in questions:
        _question = question.lower()
        for instance in questions[_question]["instances"]:
            response = instance[0] if model == "user" else instance[1].lower() if model == "ground truth" else instance[0]
            # handle true/false questions
            if questions[_question]["category"] == "available":
                response = "definite yes" if response == "true" else "definite no" if response == "false" else response
            # handle location questions
            elif questions[_question]["category"] == "where ingredient":
                response = "left half" if "left" in response else 'right half' if "right" in response else "center-ish"
            # handle centerish questions
            elif questions[_question]["category"] == "where agent":
                response = response.replace("center-", "").lower().strip()
                response = "center" if "center" in response else response
            # handle odd state machine maps
            elif questions[_question]["category"] == "state agent":
                response = grader.smm_to_recipe[response] if response in grader.smm_to_recipe else response
            # handle soup approximation questions
            elif questions[_question]["category"] == "remaining soup":
                response = "No soups" if response in ["0 soups"] else "1-2 soups" if response in ["1 soups", "2 soups"] else "3-4 soups" if response in ["3 soups", "4 soups"] else "5+ soups" if response in ["5 soups"] else response
            values.append([question.capitalize(), response.capitalize()])
    
    make_histogram_2d(values, title="Distribution of " + model.title() + " Question Responses\n" + category_map[category]["title"], x_categories=list(questions.keys()), y_categories=category_map[category]["responses"] + ["No idea"])
    matplotlib.pyplot.show()

# base 2D histogram from categorical data
def make_histogram_2d(raw_values=[], title="", xlabel="", ylabel="", x_categories=[], y_categories=[], ax=None):
    # create the axis if it was not provided
    ax = ax if ax is not None else matplotlib.pyplot.subplot(111)
    
    # convert the nominal data to numerical
    x_numerical = numpy.array([x_categories.index(i[0].lower()) for i in raw_values])
    y_numerical = numpy.array([y_categories.index(i[1]) for i in raw_values])

    # create a custom color map that extends RdPu with white at 0, for a white background instead of the default
    colors = [(1, 1, 1)]
    colors.extend(matplotlib.pyplot.cm.RdPu(numpy.linspace(.3, 1, 256)))  # RdPu colormap
    cmap = matplotlib.colors.ListedColormap(colors)

    fontsize = 15

    # create the 2D histogram
    hist, x_edges, y_edges = numpy.histogram2d(x=x_numerical, y=y_numerical, bins=[numpy.arange(len(x_categories)+1), numpy.arange(len(y_categories)+1)])
    orig_hist = hist.copy()
    max_val = numpy.max(hist)
    hist = hist / len(x_numerical) * 0.9  # scale for a nice color range on the color map
    hist[hist > 0] += 0.1  # move up for better visibility

    # plot the histogram
    matplotlib.pyplot.imshow(hist.T, origin='lower', extent=[x_edges[0], x_edges[-1], y_edges[0], y_edges[-1]], cmap=cmap)  # extent aligns the axis labels

    # add the text annotations to the boxes
    for i in range(len(x_edges) - 1):
        for j in range(len(y_edges) - 1):
            if orig_hist[i,j] != 0:
                matplotlib.pyplot.text((x_edges[i] + x_edges[i+1]) / 2, (y_edges[j] + y_edges[j+1]) / 2, int(orig_hist[i, j]),
                    color='white' if hist[i,j] > .0 else "dimgrey", ha='center', va='center', fontsize=18 if len(x_categories) < 10 else 8)

    # configure the ticks, labels, titles, spines, aspect ratio
    ax.set_xticks(ticks=numpy.arange(len(x_categories)) + 0.5, labels=[x.capitalize() for x in x_categories], rotation=30, ha="right", fontsize=fontsize)
    ax.set_yticks(ticks=numpy.arange(len(y_categories)) + 0.5, labels=[y.capitalize() for y in y_categories], rotation=0, va="center", fontsize=fontsize)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title, fontsize=fontsize)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["bottom"].set_visible(False)
    ax.spines["left"].set_visible(False)
    matplotlib.pyplot.gca().set_aspect('equal', adjustable='box')  # square boxes


# when this script is run
if __name__ == "__main__":
    # load the data
    results_by_round, results_by_user, results_by_user_and_round, results_by_question = load_data()

    ### plot the question frequency histogram
    # plot_histogram_question_frequency(results_by_question)

    ### plot the score distribution histogram
    # plot_histogram_score_all_rounds(results_by_user_and_round)  # one histogram for user average for all rounds
    # plot_histogram_score_each_round(results_by_user_and_round)  # one histogram for user average for each round

    ### plot the responses for each user
    # plot_confusion_question_responses(results_by_question, model="user")  # confusion matrix of the user responses to each question
    # plot_confusion_question_responses(results_by_question, model="user", category="available")
    # plot_confusion_question_responses(results_by_question, model="user", category="where ingredient")
    # plot_confusion_question_responses(results_by_question, model="user", category="where agent")
    # plot_confusion_question_responses(results_by_question, model="user", category="state agent")
    # plot_confusion_question_responses(results_by_question, model="user", category="fullness pot")
    # plot_confusion_question_responses(results_by_question, model="user", category="state pot")
    # plot_confusion_question_responses(results_by_question, model="user", category="remaining soup")

    ### plot the ground truth responses
    plot_confusion_question_responses(results_by_question, model="ground truth")  # confusion matrix of the true responses to each question
    plot_confusion_question_responses(results_by_question, model="ground truth", category="available")
    plot_confusion_question_responses(results_by_question, model="ground truth", category="where ingredient")
    plot_confusion_question_responses(results_by_question, model="ground truth", category="where agent")
    plot_confusion_question_responses(results_by_question, model="ground truth", category="state agent")
    plot_confusion_question_responses(results_by_question, model="ground truth", category="fullness pot")
    plot_confusion_question_responses(results_by_question, model="ground truth", category="state pot")
    plot_confusion_question_responses(results_by_question, model="ground truth", category="remaining soup")