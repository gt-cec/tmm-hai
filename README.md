## Team Mental Models - Human-AI Interaction

This repository contains project code, data, and analysis used for our paper *Inferring Belief States in Partially-Observable Human-Robot Teams*, presented at IROS 2024.

### Demonstration

https://github.com/user-attachments/assets/a8be14bc-b4e4-43b9-b500-89e4fc503370

### Citation

If you use this code or a derivative of it, please cite the following paper:

**BibTex:**
```
@inproceedings{kolb2024inferring,
  title={Inferring Belief States in Partially-Observable Human-Robot Teams},
  author={Kolb, Jack and Feigh, Karen M.},
  booktitle={2024 IEEE/RSJ International Conference on Intelligent Robots and Systems (IROS)},
  year={2024},
  organization={IEEE}
}
```

**MLA:**
```
Kolb, Jack, and Karen M. Feigh. "Inferring Belief States in Partially-Observable Human-Robot Teams." 2024 IEEE/RSJ International Conference on Intelligent Robots and Systems (IROS). IEEE, 2024.
```

### Summary

This work is a first step towards how robots can construct a team mental model in a partially-observable human-robot team domain. We are broadly interested in answering the question *"Can a robot predict the belief state of a human teammate?"*. We present a 2D domain based on [Overcooked-AI](https://github.com/HumanCompatibleAI/overcooked_ai), and two baselines for constructing a model of the user's belief state. We relegate the scope of the mental model to Level 1 and Level 2 situation awareness, i.e., predicting the user's knowledge of objects in the scene and the context of what the user and robot teammate are doing. Through a user study we periodically asked participants sitation awareness questions to obtain ground truth data from which we evaluated the baselines.

You may be interested in the following:

1. The experiment domain, which is a lightweight variant of the Overcooked domain complete with a functional UI for a user study. See **Simulation Environment** for the key modifications from the base environment.

2. A dataset of user gameplay runs. See **User Study Data** for the structure and features of this dataset.

3. The *logical predicates* and *LLM* mental model implementations. See **LLM Mental Model Baseline** and the paper for details on the models.

### Quick Start

1. Clone the environment:

`git clone https://github.com/gt-cec/tmm-hai`

2. Install the pip requirements:

`pip install -r requirements.txt`

3. Run main.py (uses Python 3) to start the webserver, which controls a PyGame Gym environment:

`python main.py`

The server uses port 8080 by default, which you can specify: `python main.py 8081`

4. Open the webserver's index page in your web browser:

`http://localhost:8080?user_id=123`

**Note: The user ID `123` is reserved for development, and skips demographic questions and button loading delays.**

### Overview

This repository features four components:

* A functional variant of the Overcooked-AI simulation environment featuring partial observability and user situation awareness questions (SAGAT format).
* Implementation of a *logical predicates* mental model baseline, and an *LLM prompt* mental model baseline.
* User study data from participants running through our domain.
* Analysis scripts to evaluate the performance of the mental models at predicting user responses to situation awareness questions.

### Simulation Environment

This repository is built around a stripped-down version of Overcooked-AI. Various modifications were made to support partial-observability, asking situation awareness questions, and the user study overall. Notable changes include:

* Updated the dependencies to modern versions, removed deprecated dependencies.
* Reworked the codebase so it can run without virtual environments, and across platforms.
* Reworked the UI.
* Reworked the layouts for ease-of-access.
* Added functionality for partial observability of the human agent.
* Added an A* + state machine agent.
* Added a consent form and instructions pipeline.
* Added functionality for asking situation awareness questions and generating questions.
* Added Python-friendly logging of the frame-by-frame state space and user interactions.
* Added automatically saving the user's stage so reloading the page doesn't restart the whole study.
* Removed the Docker build, as it was reliant on Ubuntu 18.04.
* Removed most dependencies on the HCAI lab's RL library.
* Removed most multiplayer functionality.
* Removed most PsiTurk functionality.

There is likely still residual unused code from the base repository, however the current repository is relatively lightweight.

To modify the environment:

*How do I change a layout (map)?*

  `env/server/layouts/`.

*Where are the logs saved?*

  `env/server/logs/`.

*How do I change the sprites?*

  `env/server/static/assets/`, the `.png` files can be edited directly, however changing the sprite bounding boxes requires editing the `.json` files.

*How do I change the UI elements?*

  `env/server/static/css/style.css` contains the CSS descriptors for most of the UI, `env/server/static/templates/index.html` is the base HTML page.

*How do I add or change the kitchen previews (image right before the user presses "Play")*

  Modify `env/server/static/images/preview_kitchen_roundX.png` where X is the layout number. This has to be done manually (screenshot, crop, save). Modifying a kitchen `.layout` file will not affect this image.

*How do I change the instructions images?*

  You can modify the images in `env/server/static/images/`, or add new ones and edit `env/server/static/templates/index.html`.

*I am testing the environment, how do I reset the stage I am on?*

  Open your browser's developer console and run `ClearCookie()` to reset entirely, or `setStudyStage(s)` where s is in `intro, practice, round1, round2, round3, round4`.

*Where do I change the URL that a user gets redirected to if they have an invalid device or do not give consent? Or when they complete the study?*

  `env/server/static/templates/index.html`, search for `study params`.

*Where do I change what is written to introduce each round? Or the debrief script?*

  `env/server/static/js/index.js:introduceStage()`.

*Where do I change the instructions? Or screening/demographics questionnaire?*

  `env/server/static/js/index.js:showIntroductionText(), showInstructions1Text(), showInstructions2Text(), etc` You will notice the questionnaire is a chain of functions, you can modify these at will. You can change the button responses in `env/static/templates/index.html`.

*Where do I modify the situation awareness questions?*

  `env/server/static/js/insitu-questions.js:generateInSituQuestions()`.

*How do I turn off the situation awareness questions?*

  Set the `numSituationAwarenessQuestionsPerInterrupt` variable to `0` in `env/server/static/templates/index.html`.

*How do I change the consent form?*

  Replace `env/server/static/pdf/Consent Form.pdf` with your consent form.

*Where do I change the webpage title?*

  `env/server/static/templates/index.html`.

*Where do I change the order of the kitchen layouts?*

  `env/server/static/templates/index.html:studyStages`.

*How do I hide the visibility "dots" around the user's agent?*

  Set `env/server/static/templates/index.html:visibilityDots` to `false`.

*How do I make the environment fully-observable?*

  Set `env/server/config.json:visibility` to `"O"` and `env/server/config.json:visibility_range` to `99` (O99 is overkill and will cover pretty much any map you make).

*How do I add another layout?*

  Create the layout in `env/server/layouts/`, add the layout name to `env/server/static/templates/index.html:studyStages`, add the layout to `env/server/static/js/index.js:setStudyStage()` and `introduceStage()`, add the layout to `env/server/config.json`, add a new stage to `<experiment-progress-bar>` in `env/server/static/templates/index.html`, add a preview image to `env/server/static/images/` (copy/paste another layout preview and replace it once you've ran your new layout and can screenshot it).

*How do I make the layout larger?*

  Add additional rows or columns in `env/server/layouts/(your layout).layout:grid`, and make sure there are no `objects` with positions on the floor. E.g., if you add a row to `RSMM1.layout`, change `{ "position" : (1, 4), "name": "tomato"},` to `{ "position" : (1, 5), "name": "tomato"},` so the tomato is no longer on the floor.

*How do I add a visibility mode besides V, O, or D?*

  `env/server/game.py:can_see()`

*How do I change the number of AI agents?*

  In this work the layouts were designed for two agents, so introducing additional agents may require you to redesign the layouts. Additionally, the original Overcooked-AI domain was designed for two agents. Regardless, to increase the number of agents, change the `params["num_players"]` parameter in `env/server/app.py`, and add additional agent numbers in `env/server/layouts/*.layout`'s `grid` and start configurations in `start_state:players`. You will need to debug the graphics stack for why the third agent is showing as white instead of purple. If you do so, please reach out so I can integrate your code changes.

*How do I use a custom policy?*

  Copy the dummy or FSMAI policy in `env/server/game.py`. To make agents use that policy, search `game.py` for `FSMAI(self)` and change to your new policy. This will make all agents use your new policy. You can add conditional logic to make some agents use a different policy, e.g., `self.npc_policies[npc_id] = FSMAI() if i < 2 else SomeOtherPolicy()`.

*How do I edit the finite state machine AI?*

  `env/server/game.py:FSMAI`

If you have any questions about the environment, please reach out to me via email at kolb [at] gatech [dot] edu, or open a GitHub issue.

### User Study Data

Log file data from 31 participants are included in `env/server/logs`. Each line of the log file is formatted as a Python dictionary, or JSON, for easy reading and parsing. Several scripts are available to parse the files into intermediary pickle files and compute the quantitative results presented in the paper.

Note that the user data analysis scripts assume two agents and a 10x5 grid layout and would need modifications for more agents or other gameboard sizes.

While the team mental model computations are feasible ad-hoc, we handled them post-hoc so we could test a range of agent visibility parameters.

For the paper, we used several scripts to analyze and visualize our data:

* `make_smm.py` visualizes four mental models frame-by-frame: the ground truth, the mental model given full observability (sanity check, should match ground truth), the robot's mental model, and the robot's estimated human mental model (team mental model).

* `llm.py` contains functions for generating the LLM prompts and computing statistics from their results with respect to user responses. Due to the response "fluff" generated by LLMs, manual review was done to confirm and record the LLM's response. The LLM outputs used in our analysis (40 user responses) are in `llm_outputs_O4.txt` and `llm_outputs_O9.txt`.

* `grader.py` contains utility functions to construct mental models, answer situation awareness questions using the estimated team mental model, and grade the response with respect to ground truth world state. This script is not run directly.

* `extract_results.py` extracts the metrics of interest from the grader across all participants and stores that data as pickle files. The script has an argument for the AI agents visibility when constructing the mental models, e.g., `python extract_results.py V4`. The script will take several minutes to run.

* `visualize_results.py` uses the pickle files generated by `extract_results.py` to compute and generate the plots shown in the paper. There are quite a lot of plots built-in, so open the script and uncomment the plots you are interested in.

* Utility scripts in `plots/` are used by `visualize_results.py` for generating the plots.

### LLM Mental Model Baseline

We used GPT4 prompted on the current state and situation awareness posed to users. This meant the prior state history was **not** provided to the LLM, which is a low-hanging fruit for future work.

The code used to generate the prompt is in `llm.py`. An example prompt follows:

```
You are playing a simple 2D kitchen game. The objective of the game is for two agents, A0 and A1, to cook soups using ingredients from the counters. You are A1. The game board has 11 columns and 5 rows, where the location (0,0) is at the top left and the location (10,4) is at the bottom right. Here are the steps to cook a soup:

1. Bring three ingredients to an unfilled pot. The ingredients can be tomatoes, or onions, or both.
2. The pot will start cooking when it is filled.
3. Once cooking is complete, bring a dish to the pot to plate the soup.
4. Bring the plated soup to a serving station.
5. The plated soup will then be delivered automatically.

A pot is considered cooking if it has a soup at its location, and the soup is cooking. Cooking is complete if the soup at the pot's location is ready. A pot without a soup at its location is empty.

The current objects in the kitchen are:
    [object name] at ([x],[y]) [if soup: "containing: ingredient 1, ..., ingredient, Cooking: [true,false], Ready: [true,false]}

The chefs in the kitchen are:
    A0 at ([x],[y]) facing [up,down,left,right] and holding [nothing,ingredient/item name]
    A1 at ([x],[y]) facing [up,down,left,right] and holding [nothing,ingredient/item name]

Please answer the question as A1, using only one of responses below.

The question is: [question text]

You can answer with only one of:
    - [possible response 1]
    - [possible response 2]
    - [...]

What is your answer?
```

Manual review was required to extract the answer from the LLM, as the LLM would sometimes respond with fluff around the answer (e.g., "I think A1 would respond with: [answer]")
