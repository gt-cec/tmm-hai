# make_smm.py: processes logs to construct a mental model

import smm.smm
import ast
import networkx as nx
import matplotlib.pyplot as plt

G = None  # networkx graph
node_colors = None  # networkx node colors
classes = ["pot", "soup", "station", "onion", "tomato", "dish"]
rounds = {
    "RSMM3": 1,
    "RSMM4": 2,
    "RSMM5": 3,
    "RSMM6": 4,
    "RSMM7": 5,
}

def run_smm(user_id, round):
    # pull the lines from the log file
    with open("env/server/logs/" + user_id + ".txt", "r") as f:
        lines = f.readlines()

    # init model
    model = smm.smm.SMM("predicates", visibility="O10")

    # init plot
    plt.show(block=False)
    
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

        print("-----------------------------------")

        # make sure the model is initialized
        if not model.initialized:
            model.init_belief_state_from_file(state["layout"] + ".layout")

        # update the smm
        # print("RAW SEEN", state)
        state = model.convert_log_to_state(state)
        model.update(state, debug=True)
        print([(model.belief_state["objects"][o]["propertyOf"]["title"], model.belief_state["objects"][o]["position"], model.belief_state["objects"][o]["visible"]) for o in model.belief_state["objects"]])
        visualize(model.belief_state)
        # input()

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
def visualize(state):
    global G

    if G is None:
        # create a graph
        G = nx.Graph()
        # add the nodes
        G.add_nodes_from(state["objects"].keys())
        G.add_nodes_from(state["agents"].keys())

    # update the nodes
    for obj in state["objects"]:
        # set the node properties
        node_properties = {
            "x" : state["objects"][obj]["position"][0],
            "y" : 4 - state["objects"][obj]["position"][1],  # the game board is 4 high and 0,0 is at the top left
            "class" : state["objects"][obj]["propertyOf"]["name"],
            "cookTime" : state["objects"][obj]["propertyOf"]["cookTime"],
            "isCooking" : state["objects"][obj]["propertyOf"]["isCooking"],
            "isReady" : state["objects"][obj]["propertyOf"]["isReady"],
            "isIdle" : state["objects"][obj]["propertyOf"]["isIdle"],
        }
        # add a new node if it doesnt exist
        if obj not in G.nodes:
            G.add_node(obj)
        G.nodes[obj].update(node_properties)

    # remove objects that no longer exist or are not marked as visible
    removed = [x for x in G.nodes if (x not in state["objects"] or not state["objects"][x]["visible"]) and x not in state["agents"]]
    [G.remove_node(x) for x in removed]

    # set the edges ("can use with")
    G.clear_edges()
    for object_from in G.nodes:
        if object_from[0] == "A":  # agents do not have edges, only objects
            continue
        # set the node edges
        for object_to_and_weight in state["objects"][object_from]["canUseWith"]:
            if object_to_and_weight[1] > 0 and object_to_and_weight[0] in G.nodes:
                G.add_edge(object_from, object_to_and_weight[0], weight=object_to_and_weight[1])

    # set the node colors by class
    node_colors = [get_color((state["objects"][obj]["propertyOf"]["name"] if obj[0] == "O" else obj)) for obj in G.nodes]
    
    # update the agents
    for agent in state["agents"]:
        # set the node properties
        node_properties = {
            "x" : state["agents"][agent]["position"][0],
            "y" : 4 - state["agents"][agent]["position"][1],  # the game board is 4 high and 0,0 is at the top left
            "facing x" : state["agents"][agent]["facing"][0],
            "facing y" : state["agents"][agent]["facing"][1],
            "holding" : state["agents"][agent]["holding"],
            "goal" : state["agents"][agent]["goal"],
        }
        G.nodes[agent].update(node_properties)

    # plot the graph
    plt.clf()
    pos = nx.rescale_layout_dict({obj : [float(G.nodes[obj]["x"]), float(G.nodes[obj]["y"])] for obj in G.nodes})
    node_labels = {obj : obj for obj in G.nodes}
    nx.draw(G, pos, with_labels=True, labels=node_labels, node_size=700, node_color=node_colors, font_size=10, font_color="black", font_weight="bold", edge_color="gray", linewidths=1, alpha=0.7)

    # record the object pairs
    output = ""
    for object_from in state["objects"]:
        object_from_encoding = get_object_encoding(state, object_from)
        for object_to_and_weight in state["objects"][object_from]["canUseWith"]:
            object_to = object_to_and_weight[0]
            object_to_encoding = get_object_encoding(state, object_to)
            edge_weight = object_to_and_weight[1]
            output += ",".join(object_from_encoding) + "," + ",".join(object_to_encoding) + "," + str(edge_weight) + "\n"

    with open("./dataset.txt", "a+") as f:
        f.write(output)

    # display the plot
    plt.pause(0.1)

if __name__ == "__main__":
    run_smm("64776e3beba1085215214ec0", 1)