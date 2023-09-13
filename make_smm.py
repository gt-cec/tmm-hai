# make_smm.py: processes logs to construct a mental model

import smm.smm
import ast
import networkx as nx
import matplotlib.pyplot as plt
import matplotlib
import math
import numpy
import sys


axes = None  # matplotlib plots
G = None  # networkx graph
node_colors = None  # networkx node colors
classes = ["pot", "soup", "station", "onion", "tomato", "dish"]
human_image = matplotlib.pyplot.imread("./env/server/static/images/human.png")
robot_image = matplotlib.pyplot.imread("./env/server/static/images/robot.png")
tomato_image = matplotlib.pyplot.imread("./env/server/static/images/tomato.png")
onion_image = matplotlib.pyplot.imread("./env/server/static/images/onion.png")
dish_image = matplotlib.pyplot.imread("./env/server/static/images/dish.png")
soup_image = matplotlib.pyplot.imread("./env/server/static/images/soup.png")
rounds = {
    "RSMM3": 1,
    "RSMM4": 2,
    "RSMM5": 3,
    "RSMM6": 4,
    "RSMM7": 5,
}

matplotlib.rcParams["font.sans-serif"] = "Roboto"
# matplotlib.rcParams['figure.dpi'] = 600

def run_smm(user_id, round):
    # pull the lines from the log file
    with open("env/server/logs/" + user_id + ".txt", "r") as f:
        lines = f.readlines()

    # init models
    observed_model = smm.smm.SMM("predicates", visibility="O20", agent="A0")  # model that only uses observations, no updates
    true_model = smm.smm.SMM("predicates", visibility="O20", agent="A0")  # robot model with full observability, ground truth
    agent_model = smm.smm.SMM("predicates", visibility=sys.argv[1], agent="A0")  # robot model with partial observability
    human_model = smm.smm.SMM("predicates", visibility="D2", agent="A1")  # estimated human model with partial observability 

    # init plot
    plt.show(block=False)

    first_view = True  # on the first view, sync all belief states to the ground truth
    
    # process each line
    for line in lines:
        # convert to a state dict
        state = ast.literal_eval(line)

        # ignore non-state logs
        if "stage" in state:
            continue

        # ignore incorrect rounds
        if "layout" not in state or state["layout"] not in rounds or rounds[state["layout"]] != round:  # ignore if incorrect layout/round
            continue

        # make sure the model is initialized
        if not true_model.initialized:
            true_model.init_belief_state_from_file(state["layout"] + ".layout")

        # update the mental models
        state = true_model.convert_log_to_state(state)
        observed_model.belief_state = state  # directly set the belief state of the observed model
        true_model.update(state, debug=False)
        true_belief_state = true_model.get_visible_belief_state()

        if first_view:
            agent_model.model.domain_knowledge = true_belief_state
            human_model.model.domain_knowledge = true_belief_state
            first_view = False

        agent_model.update(true_belief_state, debug=False)
        agent_belief_state = agent_model.get_visible_belief_state()
        human_model.update(agent_belief_state, debug=False)
        visualize(models=[observed_model, true_model, agent_model, human_model], titles=[(r"Raw Observations ($O$)", "(current world state)"), (r"Full Observability Belief State ($\beta^{true}$)", "(oracle with all world state information)"), (r"Robot's Partial Observability Belief State ($\beta^{robot}$)", "(only access to local world state information)"), (r"Estimated Human's Belief State ($\beta^{pred}$)", r"(only access to robot's belief state $\beta^{robot}$)")], game_round=str(round))

    # keep the plot visible
    plt.show()

# gets the node color of an object, for the networkx plot
def get_color(name):
    if name == "tomato":
        return "red"
    if name == "onion":
        return "orange"
    if name == "soup":
        return "skyblue"
    if name == "dish":
        return "yellow"
    if name == "station":
        return "purple"
    if name == "pot":
        return "grey"
    if name == "A0":
        return "blue"
    if name == "A1":
        return "green"
    print("NAME", name)
    return "orange"

# get the class encoding
def get_object_encoding(state, obj):
    # pot soup station onion tomato isCooking isReady isIdle numIngredients
    encoding = ['0', '0', '0', '0', '0', '0', '0', '0', '0', '0']
    # set the class encoding
    encoding[classes.index(state["objects"][obj]["propertyOf"]["name"])] = '1'
    # set the property encoding
    encoding[5] = '1' if state["objects"][obj]["propertyOf"]["isCooking"] else '0'
    encoding[6] = '1' if state["objects"][obj]["propertyOf"]["isReady"] else '0'
    encoding[7] = '1' if state["objects"][obj]["propertyOf"]["isIdle"] else '0'
    encoding[8] = str(get_num_ingredient_list(state, obj))
    return encoding

# gets the number of ingredients of an object
def get_num_ingredient_list(state, object_id):
    return state["objects"][object_id]["propertyOf"]["title"].count(":") + state["objects"][object_id]["propertyOf"]["title"].count("+")

# shows the networkx plot
def visualize(models:list, titles:list, game_round:str="practice"):
    global G, axes

    game_round = "round" + str(game_round) if str(game_round).isdigit() else game_round  # have the game round start with "round" if it is a number
    background_image  = plt.imread("./env/server/static/images/blank_kitchen_" + str(game_round) + ".png")  # read the image for the background

    if axes is None:
        _, a = plt.subplots(nrows=math.ceil(len(models)/2), ncols=2 if len(models) > 1 else 1)  # generate the subplots

        if isinstance(a, numpy.ndarray):  # if needed, flatten the subplot nested tuple into an array
            axes = []
            for row in a:
                if isinstance(row, numpy.ndarray):
                    for col in row:
                        axes.append(col)
                else:
                    axes.append(row)
        else:
            axes = [a]

    # on the first iteration, initialize the graphs
    if G is None:
        G = []
        for i in range(len(models)):
            # create a graph
            G.append(nx.grid_2d_graph(5, 10))

            # add the nodes
            G[i].add_nodes_from(models[i].belief_state["objects"].keys())
            G[i].add_nodes_from(models[i].belief_state["agents"].keys())

    for i in range(len(models)):
        if i == 0:
            for agent in models[i].belief_state["agents"]:
                if models[i].belief_state["agents"][agent]["holding"] is not None:
                    models[i].belief_state["objects"][agent + "-h"] =  models[i].belief_state["agents"][agent]["holding"]
                    models[i].belief_state["objects"][agent + "-h"]["visible"] = True

        # update the nodes
        for obj in models[i].belief_state["objects"]:
            # set the node properties
            node_properties = {
                "x" : models[i].belief_state["objects"][obj]["position"][0],
                "y" : 4 - models[i].belief_state["objects"][obj]["position"][1],  # the game board is 4 high and 0,0 is at the top left
                "class" : models[i].belief_state["objects"][obj]["propertyOf"]["name"],
                "cookTime" : models[i].belief_state["objects"][obj]["propertyOf"]["cookTime"] if "cookTime" in models[i].belief_state["objects"][obj]["propertyOf"] else None,
                "isCooking" : models[i].belief_state["objects"][obj]["propertyOf"]["isCooking"] if "isCooking" in models[i].belief_state["objects"][obj]["propertyOf"] else None,
                "isReady" : models[i].belief_state["objects"][obj]["propertyOf"]["isReady"] if "isReady" in models[i].belief_state["objects"][obj]["propertyOf"] else None,
                "isIdle" : models[i].belief_state["objects"][obj]["propertyOf"]["isIdle"] if "isIdle" in models[i].belief_state["objects"][obj]["propertyOf"] else None,
            }
            # add a new node if it doesnt exist
            if obj not in G[i].nodes:
                G[i].add_node(obj)
            G[i].nodes[obj].update(node_properties)

        # remove objects that no longer exist or are not marked as visible
        removed = [x for x in G[i].nodes if (x not in models[i].belief_state["objects"] or not models[i].belief_state["objects"][x]["visible"]) and x not in models[i].belief_state["agents"]]
        [G[i].remove_node(x) for x in removed]

        # set the edges ("can use with")
        G[i].clear_edges()
        for object_from in G[i].nodes:
            if object_from[0] == "A":  # agents do not have edges, only objects
                continue
            # set the node edges
            for object_to in models[i].belief_state["objects"][object_from]["canUseWith"]:
                if models[i].belief_state["objects"][object_from]["canUseWith"][object_to] > 0 and object_to in G[i].nodes:
                    G[i].add_edge(object_from, object_to, weight=models[i].belief_state["objects"][object_from]["canUseWith"][object_to])

        # set the node colors by class
        node_colors = [get_color((models[i].belief_state["objects"][obj]["propertyOf"]["name"] if obj[0] == "O" else obj)) for obj in G[i].nodes]
        
        # update the agents
        for agent in models[i].belief_state["agents"]:
            # set the node properties
            node_properties = {
                "x" : models[i].belief_state["agents"][agent]["position"][0],
                "y" : 4 - models[i].belief_state["agents"][agent]["position"][1],  # the game board is 4 high and 0,0 is at the top left
                "facing x" : models[i].belief_state["agents"][agent]["facing"][0],
                "facing y" : models[i].belief_state["agents"][agent]["facing"][1],
                "holding" : models[i].belief_state["agents"][agent]["holding"],
                "goal" : models[i].belief_state["agents"][agent]["goal"] if "goal" in models[i].belief_state["agents"][agent] else None,
                "name": agent,
            }
            G[i].nodes[agent].update(node_properties)

        pos = {obj : [float(G[i].nodes[obj]["x"]), float(G[i].nodes[obj]["y"])] for obj in G[i].nodes}
        node_labels = {obj : obj for obj in G[i].nodes}
        axes[i].clear()  # clear the axis content
        axes[i].imshow(background_image, extent=[-0.5, 10.5, -0.5, 4.5])
        axes[i].set_title(titles[i][0] + "\n", fontsize=20, fontfamily="Roboto", fontweight=400)
        axes[i].text(0.5, 1.06, titles[i][1], ha='center', va='center', fontsize=16, transform=axes[i].transAxes)

        agent_name = models[i].agent_name
        agent_pos = pos[agent_name]
        agent_visible_radius = models[i].visibility_range
        patch_color = "#1E5E9877" if models[i].agent_name == "A0" else "#00A26777"

        if models[i].visibility_type == "O":  # for O-type visibility
            if agent_visible_radius >= 10:  # we use a large O-type for full observability, so don't bother coloring that
                visibility_patch = None
            else:
                visibility_patch = matplotlib.patches.Circle(agent_pos, agent_visible_radius, edgecolor='none', facecolor=patch_color)  # draw a circle around the agent
        
        elif models[i].visibility_type == "D":  # for D-type visibility
            center = agent_pos
            radius = agent_visible_radius
            facing = models[i].belief_state["agents"][agent_name]["facing"]
            range_start = numpy.pi / 2 if facing[0] in [1, -1] else 0
            range_end = -numpy.pi / 2 if facing[0] in [1, -1] else numpy.pi
            theta = numpy.linspace(range_start, range_end)
            x = center[0] + numpy.cos(theta) * radius * (1 if facing[0] == 1 or facing[1] == -1 else -1)
            y = center[1] + numpy.sin(theta) * radius * (1 if facing[0] == -1 or facing[1] == -1 else -1)
            visibility_patch = matplotlib.patches.Polygon(numpy.column_stack((x, y)), closed=False, edgecolor='none', facecolor=patch_color)

        elif models[i].visibility_type == "V":  # for V-type visibility
            facing = models[i].belief_state["agents"][agent_name]["facing"]
            center = agent_pos
            radius = agent_visible_radius
            theta_start = 315 if facing[0] == 1 else 135 if facing[0] == -1 else 225 if facing[1] == 1 else 45
            theta_end = 45 if facing[0] == 1 else 225 if facing[0] == -1 else 315 if facing[1] == 1 else 135
            visibility_patch = matplotlib.patches.Wedge(center, radius, theta_start, theta_end, edgecolor='none', facecolor=patch_color)

        else:
            raise ValueError("The model's visibility type, " + str(models[i].visibility_type) + " does not have a visual implementation!")

        if visibility_patch is not None:  # add the patch
            axes[i].add_patch(visibility_patch)

        axes[i].set_aspect('equal', adjustable='box')
        margin = 0.4
        axes[i].set_xlim([0-margin, 10+margin])  # set the boundaries 
        axes[i].set_ylim([0-margin, 4+margin])  # set the boundaries
        axes[i].set_xticks([])
        axes[i].set_yticks([])
        
        # show the agents
        axes[i].imshow(robot_image, extent=[pos["A0"][0]-0.35, pos["A0"][0]+0.35, pos["A0"][1]-0.35, pos["A0"][1]+0.35])
        axes[i].imshow(human_image, extent=[pos["A1"][0]-0.35, pos["A1"][0]+0.35, pos["A1"][1]-0.35, pos["A1"][1]+0.35])

        for node in G[i].nodes:
            if "name" in G[i].nodes[node]:  # ignore agents
                continue
            if G[i].nodes[node]["class"] == "tomato":
                axes[i].imshow(tomato_image, extent=[pos[node][0]-0.20, pos[node][0]+0.20, pos[node][1]-0.20, pos[node][1]+0.20])
            elif G[i].nodes[node]["class"] == "onion":
                axes[i].imshow(onion_image, extent=[pos[node][0]-0.20, pos[node][0]+0.20, pos[node][1]-0.20, pos[node][1]+0.20])
            elif G[i].nodes[node]["class"] == "dish":
                axes[i].imshow(dish_image, extent=[pos[node][0]-0.25, pos[node][0]+0.25, pos[node][1]-0.25, pos[node][1]+0.25])
            elif G[i].nodes[node]["class"] == "soup":
                axes[i].imshow(soup_image, extent=[pos[node][0]-0.20, pos[node][0]+0.20, pos[node][1]-0.20, pos[node][1]+0.20])

        nx.draw_networkx_edges(G[i], pos, ax=axes[i], width=1.0, alpha=0.9, edge_color="gray")

    # record the object pairs
    output = ""
    for object_from in models[i].belief_state["objects"]:
        object_from_encoding = get_object_encoding(models[i].belief_state, object_from)
        for object_to in models[i].belief_state["objects"][object_from]["canUseWith"]:
            object_to_encoding = get_object_encoding(models[i].belief_state, object_to)
            edge_weight = models[i].belief_state["objects"][object_from]["canUseWith"][object_to]
            output += ",".join(object_from_encoding) + "," + ",".join(object_to_encoding) + "," + str(edge_weight) + "\n"

    # add arrows between axes
    arrowprops = dict(arrowstyle="->", mutation_scale=30, linewidth=2, color='#fc4b36')
    plt.annotate('', xy=(-0.01, .5), xycoords=axes[1].transAxes, xytext=(1.01, .5), textcoords=axes[0].transAxes, arrowprops=arrowprops)
    # plt.annotate('', xy=(1.01, 1.01), xycoords=axes[2].transAxes, xytext=(-0.01, -0.01), textcoords=axes[1].transAxes, arrowprops=arrowprops)
    plt.annotate('', xy=(-0.01, .5), xycoords=axes[3].transAxes, xytext=(1.01, .5), textcoords=axes[2].transAxes, arrowprops=arrowprops)

    # display the plot
    plt.pause(0.1)

if __name__ == "__main__":
    run_smm("5e2c9026f4a3052be159c494", 1)