import matplotlib
import numpy

cmap = matplotlib.cm.Wistia  # color map, this should be set at some point 

# plot a confusion matrix of the responses to questions
#  model: "user", "ground truth"
#  category: category of questions to plot, otherwise "all"
def plot_confusion_question_responses(responses_by_question, model:str="user", category:str="all"):
    if model not in ["user", "ground truth"]:
        raise ValueError("'model' parameter must be in 'user', 'ground truth'")

    
    all_questions = ['Is there at least one available onion', 'Is there at least one available tomato',
                    'Where is the nearest available onion', 'Where is the nearest available tomato',
                    'Where are you', 'Where is your teammate',
                    'What are you doing now', 'What is your teammate doing now',
                    'How full is the leftmost pot', 'How full is the rightmost pot',
                    "What is the leftmost pot's status", "What is the rightmost pot's status",
                    'How many more soups can be made/delivered']
    
    availability_responses = ['Definite yes', 'Likely yes', 'Unsure', 'Likely no', 'Definite no']
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
                    for key in responses_by_question:  
                        if question.lower() in key:
                            _key = key.replace(" make your best guess.", "").replace(", including soups in-progress?", "?")  # remove extraneous parts of the question
                            questions[_key] = {"category": _category, "instances": responses_by_question[key]}

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
    # ignore if no values were provided
    if len(raw_values) == 0:
        return

    # create the axis if it was not provided
    ax = ax if ax is not None else matplotlib.pyplot.subplot(111)
    
    # convert the nominal data to numerical
    x_numerical = numpy.array([x_categories.index(i[0].lower()) for i in raw_values])
    y_numerical = numpy.array([y_categories.index(i[1]) for i in raw_values])

    fontsize = 15

    # create the 2D histogram
    hist, x_edges, y_edges = numpy.histogram2d(x=x_numerical, y=y_numerical, bins=[numpy.arange(len(x_categories)+1), numpy.arange(len(y_categories)+1)])
    orig_hist = hist.copy()
    max_val = numpy.max(hist)
    hist = hist / len(x_numerical) * 0.98  # scale for a nice color range on the color map
    hist[hist > 0] += 0.02  # move up for better visibility

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
