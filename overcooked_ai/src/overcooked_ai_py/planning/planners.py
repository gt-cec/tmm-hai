import itertools
import os
import pickle
import time

import numpy as np

from overcooked_ai.src.overcooked_ai_py.data.planners import (
    PLANNERS_DIR,
    load_saved_action_manager,
    load_saved_motion_planner,
)
from overcooked_ai.src.overcooked_ai_py.mdp.actions import Action, Direction
from overcooked_ai.src.overcooked_ai_py.mdp.overcooked_mdp import (
    EVENT_TYPES,
    OvercookedGridworld,
    OvercookedState,
    PlayerState,
)
from overcooked_ai.src.overcooked_ai_py.planning.search import Graph, NotConnectedError
from overcooked_ai.src.overcooked_ai_py.utils import manhattan_distance

# Run planning logic with additional checks and
# computation to prevent or identify possible minor errors
SAFE_RUN = False

NO_COUNTERS_PARAMS = {
    "start_orientations": False,
    "wait_allowed": False,
    "counter_goals": [],
    "counter_drop": [],
    "counter_pickup": [],
    "same_motion_goals": True,
}

NO_COUNTERS_START_OR_PARAMS = {
    "start_orientations": True,
    "wait_allowed": False,
    "counter_goals": [],
    "counter_drop": [],
    "counter_pickup": [],
    "same_motion_goals": True,
}


class MotionPlanner(object):
    """A planner that computes optimal plans for a single agent to
    arrive at goal positions and orientations in an OvercookedGridworld.

    Args:
        mdp (OvercookedGridworld): gridworld of interest
        counter_goals (list): list of positions of counters we will consider
                              as valid motion goals
    """

    def __init__(self, mdp, counter_goals=[]):
        self.mdp = mdp

        # If positions facing counters should be
        # allowed as motion goals
        self.counter_goals = counter_goals

        # Graph problem that solves shortest path problem
        # between any position & orientation start-goal pair
        self.graph_problem = self._graph_from_grid()
        self.motion_goals_for_pos = self._get_goal_dict()

        self.all_plans = self._populate_all_plans()

    def save_to_file(self, filename):
        with open(filename, "wb") as output:
            pickle.dump(self, output, pickle.HIGHEST_PROTOCOL)

    @staticmethod
    def from_file(filename):
        return load_saved_motion_planner(filename)

    @staticmethod
    def from_pickle_or_compute(
        mdp,
        counter_goals,
        custom_filename=None,
        force_compute=False,
        info=False,
    ):
        assert isinstance(mdp, OvercookedGridworld)

        filename = (
            custom_filename
            if custom_filename is not None
            else mdp.layout_name + "_mp.pkl"
        )

        if force_compute:
            return MotionPlanner.compute_mp(filename, mdp, counter_goals)

        try:
            mp = MotionPlanner.from_file(filename)

            if mp.counter_goals != counter_goals or mp.mdp != mdp:
                if info:
                    print(
                        "motion planner with different counter goal or mdp found, computing from scratch"
                    )
                return MotionPlanner.compute_mp(filename, mdp, counter_goals)

        except (
            FileNotFoundError,
            ModuleNotFoundError,
            EOFError,
            AttributeError,
        ) as e:
            if info:
                print("Recomputing motion planner due to:", e)
            return MotionPlanner.compute_mp(filename, mdp, counter_goals)

        if info:
            print(
                "Loaded MotionPlanner from {}".format(
                    os.path.join(PLANNERS_DIR, filename)
                )
            )
        return mp

    @staticmethod
    def compute_mp(filename, mdp, counter_goals):
        final_filepath = os.path.join(PLANNERS_DIR, filename)
        print(
            "Computing MotionPlanner to be saved in {}".format(final_filepath)
        )
        start_time = time.time()
        mp = MotionPlanner(mdp, counter_goals)
        print(
            "It took {} seconds to create mp".format(time.time() - start_time)
        )
        mp.save_to_file(final_filepath)
        return mp

    def get_plan(self, start_pos_and_or, goal_pos_and_or):
        """
        Returns pre-computed plan from initial agent position
        and orientation to a goal position and orientation.

        Args:
            start_pos_and_or (tuple): starting (pos, or) tuple
            goal_pos_and_or (tuple): goal (pos, or) tuple
        """
        plan_key = (start_pos_and_or, goal_pos_and_or)
        action_plan, pos_and_or_path, plan_cost = self.all_plans[plan_key]
        return action_plan, pos_and_or_path, plan_cost

    def get_gridworld_distance(self, start_pos_and_or, goal_pos_and_or):
        """Number of actions necessary to go from starting position
        and orientations to goal position and orientation (not including
        interaction action)"""
        assert self.is_valid_motion_start_goal_pair(
            start_pos_and_or, goal_pos_and_or
        ), "Goal position and orientation were not a valid motion goal"
        _, _, plan_cost = self.get_plan(start_pos_and_or, goal_pos_and_or)
        # Removing interaction cost
        return plan_cost - 1

    def get_gridworld_pos_distance(self, pos1, pos2):
        """Minimum (over possible orientations) number of actions necessary
        to go from starting position to goal position (not including
        interaction action)."""
        # NOTE: currently unused, pretty bad code. If used in future, clean up
        min_cost = np.Inf
        for d1, d2 in itertools.product(Direction.ALL_DIRECTIONS, repeat=2):
            start = (pos1, d1)
            end = (pos2, d2)
            if self.is_valid_motion_start_goal_pair(start, end):
                plan_cost = self.get_gridworld_distance(start, end)
                if plan_cost < min_cost:
                    min_cost = plan_cost
        return min_cost

    def _populate_all_plans(self):
        """Pre-computes all valid plans from any valid pos_or to any valid motion_goal"""
        all_plans = {}
        valid_pos_and_ors = (
            self.mdp.get_valid_player_positions_and_orientations()
        )
        valid_motion_goals = filter(
            self.is_valid_motion_goal, valid_pos_and_ors
        )
        for start_motion_state, goal_motion_state in itertools.product(
            valid_pos_and_ors, valid_motion_goals
        ):
            if not self.is_valid_motion_start_goal_pair(
                start_motion_state, goal_motion_state
            ):
                continue
            action_plan, pos_and_or_path, plan_cost = self._compute_plan(
                start_motion_state, goal_motion_state
            )
            plan_key = (start_motion_state, goal_motion_state)
            all_plans[plan_key] = (action_plan, pos_and_or_path, plan_cost)
        return all_plans

    def is_valid_motion_start_goal_pair(
        self, start_pos_and_or, goal_pos_and_or
    ):
        if not self.is_valid_motion_goal(goal_pos_and_or):
            return False
        # the valid motion start goal needs to be in the same connected component
        if not self.positions_are_connected(start_pos_and_or, goal_pos_and_or):
            return False
        return True

    def is_valid_motion_goal(self, goal_pos_and_or):
        """Checks that desired single-agent goal state (position and orientation)
        is reachable and is facing a terrain feature"""
        goal_position, goal_orientation = goal_pos_and_or
        if goal_position not in self.mdp.get_valid_player_positions():
            return False

        # Restricting goals to be facing a terrain feature
        pos_of_facing_terrain = Action.move_in_direction(
            goal_position, goal_orientation
        )
        facing_terrain_type = self.mdp.get_terrain_type_at_pos(
            pos_of_facing_terrain
        )
        if facing_terrain_type == " " or (
            facing_terrain_type == "X"
            and pos_of_facing_terrain not in self.counter_goals
        ):
            return False
        return True

    def _compute_plan(self, start_motion_state, goal_motion_state):
        """Computes optimal action plan for single agent movement

        Args:
            start_motion_state (tuple): starting positions and orientations
            goal_motion_state (tuple): goal positions and orientations
        """
        assert self.is_valid_motion_start_goal_pair(
            start_motion_state, goal_motion_state
        )
        positions_plan = self._get_position_plan_from_graph(
            start_motion_state, goal_motion_state
        )
        (
            action_plan,
            pos_and_or_path,
            plan_length,
        ) = self.action_plan_from_positions(
            positions_plan, start_motion_state, goal_motion_state
        )
        return action_plan, pos_and_or_path, plan_length

    def positions_are_connected(self, start_pos_and_or, goal_pos_and_or):
        return self.graph_problem.are_in_same_cc(
            start_pos_and_or, goal_pos_and_or
        )

    def _get_position_plan_from_graph(self, start_node, end_node):
        """Recovers positions to be reached by agent after the start node to reach the end node"""
        node_path = self.graph_problem.get_node_path(start_node, end_node)
        assert node_path[0] == start_node and node_path[-1] == end_node
        positions_plan = [state_node[0] for state_node in node_path[1:]]
        return positions_plan

    def action_plan_from_positions(
        self, position_list, start_motion_state, goal_motion_state
    ):
        """
        Recovers an action plan reaches the goal motion position and orientation, and executes
        and interact action.

        Args:
            position_list (list): list of positions to be reached after the starting position
                                  (does not include starting position, but includes ending position)
            start_motion_state (tuple): starting position and orientation
            goal_motion_state (tuple): goal position and orientation

        Returns:
            action_plan (list): list of actions to reach goal state
            pos_and_or_path (list): list of (pos, or) pairs visited during plan execution
                                    (not including start, but including goal)
        """
        goal_position, goal_orientation = goal_motion_state
        action_plan, pos_and_or_path = [], []
        position_to_go = list(position_list)
        curr_pos, curr_or = start_motion_state

        # Get agent to goal position
        while position_to_go and curr_pos != goal_position:
            next_pos = position_to_go.pop(0)
            action = Action.determine_action_for_change_in_pos(
                curr_pos, next_pos
            )
            action_plan.append(action)
            curr_or = action if action != Action.STAY else curr_or
            pos_and_or_path.append((next_pos, curr_or))
            curr_pos = next_pos

        # Fix agent orientation if necessary
        if curr_or != goal_orientation:
            new_pos, _ = self.mdp._move_if_direction(
                curr_pos, curr_or, goal_orientation
            )
            assert new_pos == goal_position
            action_plan.append(goal_orientation)
            pos_and_or_path.append((goal_position, goal_orientation))

        # Add interact action
        action_plan.append(Action.INTERACT)
        pos_and_or_path.append((goal_position, goal_orientation))

        return action_plan, pos_and_or_path, len(action_plan)

    def _graph_from_grid(self):
        """Creates a graph adjacency matrix from an Overcooked MDP class."""
        state_decoder = {}
        for state_index, motion_state in enumerate(
            self.mdp.get_valid_player_positions_and_orientations()
        ):
            state_decoder[state_index] = motion_state

        pos_encoder = {
            motion_state: state_index
            for state_index, motion_state in state_decoder.items()
        }
        num_graph_nodes = len(state_decoder)

        adjacency_matrix = np.zeros((num_graph_nodes, num_graph_nodes))
        for state_index, start_motion_state in state_decoder.items():
            for (
                action,
                successor_motion_state,
            ) in self._get_valid_successor_motion_states(start_motion_state):
                adj_pos_index = pos_encoder[successor_motion_state]
                adjacency_matrix[state_index][
                    adj_pos_index
                ] = self._graph_action_cost(action)

        return Graph(adjacency_matrix, pos_encoder, state_decoder)

    def _graph_action_cost(self, action):
        """Returns cost of a single-agent action"""
        assert action in Action.ALL_ACTIONS
        return 1

    def _get_valid_successor_motion_states(self, start_motion_state):
        """Get valid motion states one action away from the starting motion state."""
        start_position, start_orientation = start_motion_state
        return [
            (
                action,
                self.mdp._move_if_direction(
                    start_position, start_orientation, action
                ),
            )
            for action in Action.ALL_ACTIONS
        ]

    def min_cost_between_features(
        self, pos_list1, pos_list2, manhattan_if_fail=False
    ):
        """
        Determines the minimum number of timesteps necessary for a player to go from any
        terrain feature in list1 to any feature in list2 and perform an interact action
        """
        min_dist = np.Inf
        min_manhattan = np.Inf
        for pos1, pos2 in itertools.product(pos_list1, pos_list2):
            for mg1, mg2 in itertools.product(
                self.motion_goals_for_pos[pos1],
                self.motion_goals_for_pos[pos2],
            ):
                if not self.is_valid_motion_start_goal_pair(mg1, mg2):
                    if manhattan_if_fail:
                        pos0, pos1 = mg1[0], mg2[0]
                        curr_man_dist = manhattan_distance(pos0, pos1)
                        if curr_man_dist < min_manhattan:
                            min_manhattan = curr_man_dist
                    continue
                curr_dist = self.get_gridworld_distance(mg1, mg2)
                if curr_dist < min_dist:
                    min_dist = curr_dist

        # +1 to account for interaction action
        if manhattan_if_fail and min_dist == np.Inf:
            min_dist = min_manhattan
        min_cost = min_dist + 1
        return min_cost

    def min_cost_to_feature(
        self,
        start_pos_and_or,
        feature_pos_list,
        with_argmin=False,
        debug=False,
    ):
        """
        Determines the minimum number of timesteps necessary for a player to go from the starting
        position and orientation to any feature in feature_pos_list and perform an interact action
        """
        start_pos = start_pos_and_or[0]
        assert self.mdp.get_terrain_type_at_pos(start_pos) != "X"
        min_dist = np.Inf
        best_feature = None
        for feature_pos in feature_pos_list:
            for feature_goal in self.motion_goals_for_pos[feature_pos]:
                if not self.is_valid_motion_start_goal_pair(
                    start_pos_and_or, feature_goal
                ):
                    continue
                curr_dist = self.get_gridworld_distance(
                    start_pos_and_or, feature_goal
                )
                if curr_dist < min_dist:
                    best_feature = feature_pos
                    min_dist = curr_dist
        # +1 to account for interaction action
        min_cost = min_dist + 1
        if with_argmin:
            # assert best_feature is not None, "{} vs {}".format(start_pos_and_or, feature_pos_list)
            return min_cost, best_feature
        return min_cost

    def _get_goal_dict(self):
        """Creates a dictionary of all possible goal states for all possible
        terrain features that the agent might want to interact with."""
        terrain_feature_locations = []
        for terrain_type, pos_list in self.mdp.terrain_pos_dict.items():
            if terrain_type != " ":
                terrain_feature_locations += pos_list
        return {
            feature_pos: self._get_possible_motion_goals_for_feature(
                feature_pos
            )
            for feature_pos in terrain_feature_locations
        }

    def _get_possible_motion_goals_for_feature(self, goal_pos):
        """Returns a list of possible goal positions (and orientations)
        that could be used for motion planning to get to goal_pos"""
        goals = []
        valid_positions = self.mdp.get_valid_player_positions()
        for d in Direction.ALL_DIRECTIONS:
            adjacent_pos = Action.move_in_direction(goal_pos, d)
            if adjacent_pos in valid_positions:
                goal_orientation = Direction.OPPOSITE_DIRECTIONS[d]
                motion_goal = (adjacent_pos, goal_orientation)
                goals.append(motion_goal)
        return goals


class JointMotionPlanner(object):
    """A planner that computes optimal plans for a two agents to
    arrive at goal positions and orientations in a OvercookedGridworld.

    Args:
        mdp (OvercookedGridworld): gridworld of interest
    """

    def __init__(self, mdp, params, debug=False):
        self.mdp = mdp

        # Whether starting orientations should be accounted for
        # when solving all motion problems
        # (increases number of plans by a factor of 4)
        # but removes additional fudge factor <= 1 for each
        # joint motion plan
        self.debug = debug
        self.start_orientations = params["start_orientations"]

        # Enable both agents to have the same motion goal
        self.same_motion_goals = params["same_motion_goals"]

        # Single agent motion planner
        self.motion_planner = MotionPlanner(
            mdp, counter_goals=params["counter_goals"]
        )

        # Graph problem that returns optimal paths from
        # starting positions to goal positions (without
        # accounting for orientations)
        self.joint_graph_problem = self._joint_graph_from_grid()
        self.all_plans = self._populate_all_plans()

    def get_low_level_action_plan(self, start_jm_state, goal_jm_state):
        """
        Returns pre-computed plan from initial joint motion state
        to a goal joint motion state.

        Args:
            start_jm_state (tuple): starting pos & orients ((pos1, or1), (pos2, or2))
            goal_jm_state (tuple): goal pos & orients ((pos1, or1), (pos2, or2))

        Returns:
            joint_action_plan (list): joint actions to be executed to reach end_jm_state
            end_jm_state (tuple): the pair of (pos, or) tuples corresponding
                to the ending timestep (this will usually be different from
                goal_jm_state, as one agent will end before other).
            plan_lengths (tuple): lengths for each agent's plan
        """
        assert self.is_valid_joint_motion_pair(
            start_jm_state, goal_jm_state
        ), "start: {} \t end: {} was not a valid motion goal pair".format(
            start_jm_state, goal_jm_state
        )

        if self.start_orientations:
            plan_key = (start_jm_state, goal_jm_state)
        else:
            starting_positions = tuple(
                player_pos_and_or[0] for player_pos_and_or in start_jm_state
            )
            goal_positions = tuple(
                player_pos_and_or[0] for player_pos_and_or in goal_jm_state
            )
            # If beginning positions are equal to end positions, the pre-stored
            # plan (not dependent on initial positions) will likely return a
            # wrong answer, so we compute it from scratch.
            #
            # This is because we only compute plans with starting orientations
            # (North, North), so if one of the two agents starts at location X
            # with orientation East it's goal is to get to location X with
            # orientation North. The precomputed plan will just tell that agent
            # that it is already at the goal, so no actions (or just 'interact')
            # are necessary.
            #
            # We also compute the plan for any shared motion goal with SAFE_RUN,
            # as there are some minor edge cases that could not be accounted for
            # but I expect should not make a difference in nearly all scenarios
            if any(
                [s == g for s, g in zip(starting_positions, goal_positions)]
            ) or (SAFE_RUN and goal_positions[0] == goal_positions[1]):
                return self._obtain_plan(start_jm_state, goal_jm_state)

            dummy_orientation = Direction.NORTH
            dummy_start_jm_state = tuple(
                (pos, dummy_orientation) for pos in starting_positions
            )
            plan_key = (dummy_start_jm_state, goal_jm_state)

        if plan_key not in self.all_plans:
            num_player = len(goal_jm_state)
            return [], None, [np.inf] * num_player
        joint_action_plan, end_jm_state, plan_lengths = self.all_plans[
            plan_key
        ]
        return joint_action_plan, end_jm_state, plan_lengths

    def _populate_all_plans(self):
        """Pre-compute all valid plans"""
        all_plans = {}

        # Joint states are valid if players are not in same location
        if self.start_orientations:
            valid_joint_start_states = (
                self.mdp.get_valid_joint_player_positions_and_orientations()
            )
        else:
            valid_joint_start_states = (
                self.mdp.get_valid_joint_player_positions()
            )

        valid_player_states = (
            self.mdp.get_valid_player_positions_and_orientations()
        )
        possible_joint_goal_states = list(
            itertools.product(valid_player_states, repeat=2)
        )
        valid_joint_goal_states = list(
            filter(self.is_valid_joint_motion_goal, possible_joint_goal_states)
        )

        if self.debug:
            print(
                "Number of plans being pre-calculated: ",
                len(valid_joint_start_states) * len(valid_joint_goal_states),
            )
        for joint_start_state, joint_goal_state in itertools.product(
            valid_joint_start_states, valid_joint_goal_states
        ):
            # If orientations not present, joint_start_state just includes positions.
            if not self.start_orientations:
                dummy_orientation = Direction.NORTH
                joint_start_state = tuple(
                    (pos, dummy_orientation) for pos in joint_start_state
                )

            # If either start-end states are not connected, skip to next plan
            if not self.is_valid_jm_start_goal_pair(
                joint_start_state, joint_goal_state
            ):
                continue

            # Note: we might fail to get the plan, just due to the nature of the layouts
            joint_action_list, end_statuses, plan_lengths = self._obtain_plan(
                joint_start_state, joint_goal_state
            )
            if end_statuses is None:
                continue
            plan_key = (joint_start_state, joint_goal_state)
            all_plans[plan_key] = (
                joint_action_list,
                end_statuses,
                plan_lengths,
            )
        return all_plans

    def is_valid_jm_start_goal_pair(self, joint_start_state, joint_goal_state):
        """Checks if the combination of joint start state and joint goal state is valid"""
        if not self.is_valid_joint_motion_goal(joint_goal_state):
            return False
        check_valid_fn = self.motion_planner.is_valid_motion_start_goal_pair
        return all(
            [
                check_valid_fn(joint_start_state[i], joint_goal_state[i])
                for i in range(2)
            ]
        )

    def _obtain_plan(self, joint_start_state, joint_goal_state):
        """Either use motion planner or actually compute a joint plan"""
        # Try using MotionPlanner plans and join them together
        (
            action_plans,
            pos_and_or_paths,
            plan_lengths,
        ) = self._get_plans_from_single_planner(
            joint_start_state, joint_goal_state
        )

        # Check if individual plans conflict
        have_conflict = self.plans_have_conflict(
            joint_start_state, joint_goal_state, pos_and_or_paths, plan_lengths
        )

        # If there is no conflict, the joint plan computed by joining single agent MotionPlanner plans is optimal
        if not have_conflict:
            (
                joint_action_plan,
                end_pos_and_orientations,
            ) = self._join_single_agent_action_plans(
                joint_start_state,
                action_plans,
                pos_and_or_paths,
                min(plan_lengths),
            )
            return joint_action_plan, end_pos_and_orientations, plan_lengths

        # If there is a conflict in the single motion plan and the agents have the same goal,
        # the graph problem can't be used either as it can't handle same goal state: we compute
        # manually what the best way to handle the conflict is
        elif self._agents_are_in_same_position(joint_goal_state):
            (
                joint_action_plan,
                end_pos_and_orientations,
                plan_lengths,
            ) = self._handle_path_conflict_with_same_goal(
                joint_start_state,
                joint_goal_state,
                action_plans,
                pos_and_or_paths,
            )
            return joint_action_plan, end_pos_and_orientations, plan_lengths

        # If there is a conflict, and the agents have different goals, we can use solve the joint graph problem
        return self._compute_plan_from_joint_graph(
            joint_start_state, joint_goal_state
        )

    def _get_plans_from_single_planner(
        self, joint_start_state, joint_goal_state
    ):
        """
        Get individual action plans for each agent from the MotionPlanner to get each agent
        independently to their goal state. NOTE: these plans might conflict
        """
        single_agent_motion_plans = [
            self.motion_planner.get_plan(start, goal)
            for start, goal in zip(joint_start_state, joint_goal_state)
        ]
        action_plans, pos_and_or_paths = [], []
        for action_plan, pos_and_or_path, _ in single_agent_motion_plans:
            action_plans.append(action_plan)
            pos_and_or_paths.append(pos_and_or_path)
        plan_lengths = tuple(len(p) for p in action_plans)
        assert all(
            [plan_lengths[i] == len(pos_and_or_paths[i]) for i in range(2)]
        )
        return action_plans, pos_and_or_paths, plan_lengths

    def plans_have_conflict(
        self,
        joint_start_state,
        joint_goal_state,
        pos_and_or_paths,
        plan_lengths,
    ):
        """Check if the sequence of pos_and_or_paths for the two agents conflict"""
        min_length = min(plan_lengths)
        prev_positions = tuple(s[0] for s in joint_start_state)
        for t in range(min_length):
            curr_pos_or0, curr_pos_or1 = (
                pos_and_or_paths[0][t],
                pos_and_or_paths[1][t],
            )
            curr_positions = (curr_pos_or0[0], curr_pos_or1[0])
            if self.mdp.is_transition_collision(
                prev_positions, curr_positions
            ):
                return True
            prev_positions = curr_positions
        return False

    def _join_single_agent_action_plans(
        self, joint_start_state, action_plans, pos_and_or_paths, finishing_time
    ):
        """Returns the joint action plan and end joint state obtained by joining the individual action plans"""
        assert finishing_time > 0
        end_joint_state = (
            pos_and_or_paths[0][finishing_time - 1],
            pos_and_or_paths[1][finishing_time - 1],
        )
        joint_action_plan = list(
            zip(
                *[
                    action_plans[0][:finishing_time],
                    action_plans[1][:finishing_time],
                ]
            )
        )
        return joint_action_plan, end_joint_state

    def _handle_path_conflict_with_same_goal(
        self,
        joint_start_state,
        joint_goal_state,
        action_plans,
        pos_and_or_paths,
    ):
        """Assumes that optimal path in case two agents have the same goal and their paths conflict
        is for one of the agents to wait. Checks resulting plans if either agent waits, and selects the
        shortest cost among the two."""

        (
            joint_plan0,
            end_pos_and_or0,
            plan_lengths0,
        ) = self._handle_conflict_with_same_goal_idx(
            joint_start_state,
            joint_goal_state,
            action_plans,
            pos_and_or_paths,
            wait_agent_idx=0,
        )

        (
            joint_plan1,
            end_pos_and_or1,
            plan_lengths1,
        ) = self._handle_conflict_with_same_goal_idx(
            joint_start_state,
            joint_goal_state,
            action_plans,
            pos_and_or_paths,
            wait_agent_idx=1,
        )

        assert any([joint_plan0 is not None, joint_plan1 is not None])

        best_plan_idx = np.argmin([min(plan_lengths0), min(plan_lengths1)])
        solutions = [
            (joint_plan0, end_pos_and_or0, plan_lengths0),
            (joint_plan1, end_pos_and_or1, plan_lengths1),
        ]
        return solutions[best_plan_idx]

    def _handle_conflict_with_same_goal_idx(
        self,
        joint_start_state,
        joint_goal_state,
        action_plans,
        pos_and_or_paths,
        wait_agent_idx,
    ):
        """
        Determines what is the best joint plan if whenether there is a conflict between the two agents' actions,
        the agent with index `wait_agent_idx` waits one turn.

        If the agent that is assigned to wait is "in front" of the non-waiting agent, this could result
        in an endless conflict. In this case, we return infinite finishing times.
        """
        idx0, idx1 = 0, 0
        prev_positions = [
            start_pos_and_or[0] for start_pos_and_or in joint_start_state
        ]
        curr_pos_or0, curr_pos_or1 = joint_start_state

        agent0_plan_original, agent1_plan_original = action_plans

        joint_plan = []
        # While either agent hasn't finished their plan
        while idx0 != len(agent0_plan_original) and idx1 != len(
            agent1_plan_original
        ):
            next_pos_or0, next_pos_or1 = (
                pos_and_or_paths[0][idx0],
                pos_and_or_paths[1][idx1],
            )
            next_positions = (next_pos_or0[0], next_pos_or1[0])

            # If agents collide, let the waiting agent wait and the non-waiting
            # agent take a step
            if self.mdp.is_transition_collision(
                prev_positions, next_positions
            ):
                if wait_agent_idx == 0:
                    curr_pos_or0 = (
                        curr_pos_or0  # Agent 0 will wait, stays the same
                    )
                    curr_pos_or1 = next_pos_or1
                    curr_joint_action = [
                        Action.STAY,
                        agent1_plan_original[idx1],
                    ]
                    idx1 += 1
                elif wait_agent_idx == 1:
                    curr_pos_or0 = next_pos_or0
                    curr_pos_or1 = (
                        curr_pos_or1  # Agent 1 will wait, stays the same
                    )
                    curr_joint_action = [
                        agent0_plan_original[idx0],
                        Action.STAY,
                    ]
                    idx0 += 1

                curr_positions = (curr_pos_or0[0], curr_pos_or1[0])

                # If one agent waiting causes other to crash into it, return None
                if self._agents_are_in_same_position(
                    (curr_pos_or0, curr_pos_or1)
                ):
                    return None, None, [np.Inf, np.Inf]

            else:
                curr_pos_or0, curr_pos_or1 = next_pos_or0, next_pos_or1
                curr_positions = next_positions
                curr_joint_action = [
                    agent0_plan_original[idx0],
                    agent1_plan_original[idx1],
                ]
                idx0 += 1
                idx1 += 1

            joint_plan.append(curr_joint_action)
            prev_positions = curr_positions

        assert idx0 != idx1, "No conflict found"

        end_pos_and_or = (curr_pos_or0, curr_pos_or1)
        finishing_times = (
            (np.Inf, idx1) if wait_agent_idx == 0 else (idx0, np.Inf)
        )
        return joint_plan, end_pos_and_or, finishing_times

    def is_valid_joint_motion_goal(self, joint_goal_state):
        """Checks whether the goal joint positions and orientations are a valid goal"""
        if not self.same_motion_goals and self._agents_are_in_same_position(
            joint_goal_state
        ):
            return False
        multi_cc_map = (
            len(self.motion_planner.graph_problem.connected_components) > 1
        )
        players_in_same_cc = self.motion_planner.graph_problem.are_in_same_cc(
            joint_goal_state[0], joint_goal_state[1]
        )
        if multi_cc_map and players_in_same_cc:
            return False
        return all(
            [
                self.motion_planner.is_valid_motion_goal(player_state)
                for player_state in joint_goal_state
            ]
        )

    def is_valid_joint_motion_pair(self, joint_start_state, joint_goal_state):
        if not self.is_valid_joint_motion_goal(joint_goal_state):
            return False
        return all(
            [
                self.motion_planner.is_valid_motion_start_goal_pair(
                    joint_start_state[i], joint_goal_state[i]
                )
                for i in range(2)
            ]
        )

    def _agents_are_in_same_position(self, joint_motion_state):
        agent_positions = [
            player_pos_and_or[0] for player_pos_and_or in joint_motion_state
        ]
        return len(agent_positions) != len(set(agent_positions))

    def _compute_plan_from_joint_graph(
        self, joint_start_state, joint_goal_state
    ):
        """Compute joint action plan for two agents to achieve a
        certain position and orientation with the joint motion graph

        Args:
            joint_start_state: pair of start (pos, or)
            joint_goal_state: pair of goal (pos, or)
        """
        assert self.is_valid_joint_motion_pair(
            joint_start_state, joint_goal_state
        ), joint_goal_state
        # Solve shortest-path graph problem
        start_positions = list(zip(*joint_start_state))[0]
        goal_positions = list(zip(*joint_goal_state))[0]
        try:
            joint_positions_node_path = self.joint_graph_problem.get_node_path(
                start_positions, goal_positions
            )[1:]
        except NotConnectedError:
            # The cost will be infinite if there is no path
            num_player = len(goal_positions)
            return [], None, [np.inf] * num_player
        (
            joint_actions_list,
            end_pos_and_orientations,
            finishing_times,
        ) = self.joint_action_plan_from_positions(
            joint_positions_node_path, joint_start_state, joint_goal_state
        )
        return joint_actions_list, end_pos_and_orientations, finishing_times

    def joint_action_plan_from_positions(
        self, joint_positions, joint_start_state, joint_goal_state
    ):
        """
        Finds an action plan and it's cost, such that at least one of the agent goal states is achieved

        Args:
            joint_positions (list): list of joint positions to be reached after the starting position
                                    (does not include starting position, but includes ending position)
            joint_start_state (tuple): pair of starting positions and orientations
            joint_goal_state (tuple): pair of goal positions and orientations
        """
        action_plans = []
        for i in range(2):
            agent_position_sequence = [
                joint_position[i] for joint_position in joint_positions
            ]
            action_plan, _, _ = self.motion_planner.action_plan_from_positions(
                agent_position_sequence,
                joint_start_state[i],
                joint_goal_state[i],
            )
            action_plans.append(action_plan)

        finishing_times = tuple(len(plan) for plan in action_plans)
        trimmed_action_plans = self._fix_plan_lengths(action_plans)
        joint_action_plan = list(zip(*trimmed_action_plans))
        end_pos_and_orientations = self._rollout_end_pos_and_or(
            joint_start_state, joint_action_plan
        )
        return joint_action_plan, end_pos_and_orientations, finishing_times

    def _fix_plan_lengths(self, plans):
        """Truncates the longer plan when shorter plan ends"""
        plans = list(plans)
        finishing_times = [len(p) for p in plans]
        delta_length = max(finishing_times) - min(finishing_times)
        if delta_length != 0:
            index_long_plan = np.argmax(finishing_times)
            plans[index_long_plan] = plans[index_long_plan][
                : min(finishing_times)
            ]
        return plans

    def _rollout_end_pos_and_or(self, joint_start_state, joint_action_plan):
        """Execute plan in environment to determine ending positions and orientations"""
        # Assumes that final pos and orientations only depend on initial ones
        # (not on objects and other aspects of state).
        # Also assumes can't deliver more than two orders in one motion goal
        # (otherwise Environment will terminate)
        from overcooked_ai_py.mdp.overcooked_env import OvercookedEnv

        dummy_state = OvercookedState.from_players_pos_and_or(
            joint_start_state, all_orders=self.mdp.start_all_orders
        )
        env = OvercookedEnv.from_mdp(
            self.mdp, horizon=200, info_level=int(self.debug)
        )  # Plans should be shorter than 200 timesteps, or something is likely wrong
        successor_state, is_done = env.execute_plan(
            dummy_state, joint_action_plan
        )
        assert not is_done
        return successor_state.players_pos_and_or

    def _joint_graph_from_grid(self):
        """Creates a graph instance from the mdp instance. Each graph node encodes a pair of positions"""
        state_decoder = {}
        # Valid positions pairs, not including ones with both players in same spot
        valid_joint_positions = self.mdp.get_valid_joint_player_positions()
        for state_index, joint_pos in enumerate(valid_joint_positions):
            state_decoder[state_index] = joint_pos

        state_encoder = {v: k for k, v in state_decoder.items()}
        num_graph_nodes = len(state_decoder)

        adjacency_matrix = np.zeros((num_graph_nodes, num_graph_nodes))
        for start_state_index, start_joint_positions in state_decoder.items():
            for (
                joint_action,
                successor_jm_state,
            ) in self._get_valid_successor_joint_positions(
                start_joint_positions
            ).items():
                successor_node_index = state_encoder[successor_jm_state]

                this_action_cost = self._graph_joint_action_cost(joint_action)
                current_cost = adjacency_matrix[start_state_index][
                    successor_node_index
                ]

                if current_cost == 0 or this_action_cost < current_cost:
                    adjacency_matrix[start_state_index][
                        successor_node_index
                    ] = this_action_cost

        return Graph(adjacency_matrix, state_encoder, state_decoder)

    def _graph_joint_action_cost(self, joint_action):
        """The cost used in the graph shortest-path problem for a certain joint-action"""
        num_of_non_stay_actions = len(
            [a for a in joint_action if a != Action.STAY]
        )
        # NOTE: Removing the possibility of having 0 cost joint_actions
        if num_of_non_stay_actions == 0:
            return 1
        return num_of_non_stay_actions

    def _get_valid_successor_joint_positions(self, starting_positions):
        """Get all joint positions that can be reached by a joint action.
        NOTE: this DOES NOT include joint positions with superimposed agents.
        """
        successor_joint_positions = {}
        joint_motion_actions = itertools.product(
            Action.MOTION_ACTIONS, Action.MOTION_ACTIONS
        )

        # Under assumption that orientation doesn't matter
        dummy_orientation = Direction.NORTH
        dummy_player_states = [
            PlayerState(pos, dummy_orientation) for pos in starting_positions
        ]
        for joint_action in joint_motion_actions:
            new_positions, _ = self.mdp.compute_new_positions_and_orientations(
                dummy_player_states, joint_action
            )
            successor_joint_positions[joint_action] = new_positions
        return successor_joint_positions

    def derive_state(self, start_state, end_pos_and_ors, action_plans):
        """
        Given a start state, end position and orientations, and an action plan, recovers
        the resulting state without executing the entire plan.
        """
        if len(action_plans) == 0:
            return start_state

        end_state = start_state.deepcopy()
        end_players = []
        for player, end_pos_and_or in zip(end_state.players, end_pos_and_ors):
            new_player = player.deepcopy()
            position, orientation = end_pos_and_or
            new_player.update_pos_and_or(position, orientation)
            end_players.append(new_player)

        end_state.players = tuple(end_players)

        # Resolve environment effects for t - 1 turns
        plan_length = len(action_plans)
        assert plan_length > 0
        for _ in range(plan_length - 1):
            self.mdp.step_environment_effects(end_state)

        # Interacts
        last_joint_action = tuple(
            a if a == Action.INTERACT else Action.STAY
            for a in action_plans[-1]
        )

        events_dict = {
            k: [[] for _ in range(self.mdp.num_players)] for k in EVENT_TYPES
        }
        self.mdp.resolve_interacts(end_state, last_joint_action, events_dict)
        self.mdp.resolve_movement(end_state, last_joint_action)
        self.mdp.step_environment_effects(end_state)
        return end_state


class MediumLevelActionManager(object):
    """
    Manager for medium level actions (specific joint motion goals).
    Determines available medium level actions for each state.

    Args:
        mdp (OvercookedGridWorld): gridworld of interest
        mlam_params (dictionary): parameters for the medium level action manager
    """

    def __init__(self, mdp, mlam_params):
        self.mdp = mdp

        self.params = mlam_params
        self.wait_allowed = mlam_params["wait_allowed"]
        self.counter_drop = mlam_params["counter_drop"]
        self.counter_pickup = mlam_params["counter_pickup"]

        self.joint_motion_planner = JointMotionPlanner(mdp, mlam_params)
        self.motion_planner = self.joint_motion_planner.motion_planner

    def save_to_file(self, filename):
        with open(filename, "wb") as output:
            pickle.dump(self, output, pickle.HIGHEST_PROTOCOL)

    @staticmethod
    def from_file(filename):
        return load_saved_action_manager(filename)

    @staticmethod
    def from_pickle_or_compute(
        mdp, mlam_params, custom_filename=None, force_compute=False, info=False
    ):
        assert isinstance(mdp, OvercookedGridworld)

        filename = (
            custom_filename
            if custom_filename is not None
            else mdp.layout_name + "_am.pkl"
        )

        if force_compute:
            return MediumLevelActionManager.compute_mlam(
                filename, mdp, mlam_params, info=info
            )

        try:
            mlam = MediumLevelActionManager.from_file(filename)

            if mlam.params != mlam_params or mlam.mdp != mdp:
                if info:
                    print(
                        "medium level action manager with different params or mdp found, computing from scratch"
                    )
                return MediumLevelActionManager.compute_mlam(
                    filename, mdp, mlam_params, info=info
                )

        except (
            FileNotFoundError,
            ModuleNotFoundError,
            EOFError,
            AttributeError,
        ) as e:
            if info:
                print("Recomputing planner due to:", e)
            return MediumLevelActionManager.compute_mlam(
                filename, mdp, mlam_params, info=info
            )

        if info:
            print(
                "Loaded MediumLevelActionManager from {}".format(
                    os.path.join(PLANNERS_DIR, filename)
                )
            )
        return mlam

    @staticmethod
    def compute_mlam(filename, mdp, mlam_params, info=False):
        final_filepath = os.path.join(PLANNERS_DIR, filename)
        if info:
            print(
                "Computing MediumLevelActionManager to be saved in {}".format(
                    final_filepath
                )
            )
        start_time = time.time()
        mlam = MediumLevelActionManager(mdp, mlam_params=mlam_params)
        if info:
            print(
                "It took {} seconds to create mlam".format(
                    time.time() - start_time
                )
            )
        mlam.save_to_file(final_filepath)
        return mlam

    def joint_ml_actions(self, state):
        """Determine all possible joint medium level actions for a certain state"""
        agent1_actions, agent2_actions = tuple(
            self.get_medium_level_actions(state, player)
            for player in state.players
        )
        joint_ml_actions = list(
            itertools.product(agent1_actions, agent2_actions)
        )

        # ml actions are nothing but specific joint motion goals
        valid_joint_ml_actions = list(
            filter(
                lambda a: self.is_valid_ml_action(state, a), joint_ml_actions
            )
        )

        # HACK: Could cause things to break.
        # Necessary to prevent states without successors (due to no counters being allowed and no wait actions)
        # causing A* to not find a solution
        if len(valid_joint_ml_actions) == 0:
            agent1_actions, agent2_actions = tuple(
                self.get_medium_level_actions(
                    state, player, waiting_substitute=True
                )
                for player in state.players
            )
            joint_ml_actions = list(
                itertools.product(agent1_actions, agent2_actions)
            )
            valid_joint_ml_actions = list(
                filter(
                    lambda a: self.is_valid_ml_action(state, a),
                    joint_ml_actions,
                )
            )
            if len(valid_joint_ml_actions) == 0:
                print(
                    "WARNING: Found state without valid actions even after adding waiting substitute actions. State: {}".format(
                        state
                    )
                )
        return valid_joint_ml_actions

    def is_valid_ml_action(self, state, ml_action):
        return self.joint_motion_planner.is_valid_jm_start_goal_pair(
            state.players_pos_and_or, ml_action
        )

    def get_medium_level_actions(
        self, state, player, waiting_substitute=False
    ):
        """
        Determine valid medium level actions for a player.

        Args:
            state (OvercookedState): current state
            player (PlayerState): the player's current state
            waiting_substitute (bool): add a substitute action that takes the place of
                                       a waiting action (going to closest feature)

        Returns:
            player_actions (list): possible motion goals (pairs of goal positions and orientations)
        """
        player_actions = []
        counter_pickup_objects = self.mdp.get_counter_objects_dict(
            state, self.counter_pickup
        )
        if not player.has_object():
            onion_pickup = self.pickup_onion_actions(counter_pickup_objects)
            tomato_pickup = self.pickup_tomato_actions(counter_pickup_objects)
            dish_pickup = self.pickup_dish_actions(counter_pickup_objects)
            soup_pickup = self.pickup_counter_soup_actions(
                counter_pickup_objects
            )

            pot_states_dict = self.mdp.get_pot_states(state)
            start_cooking = self.start_cooking_actions(pot_states_dict)
            player_actions.extend(
                onion_pickup
                + tomato_pickup
                + dish_pickup
                + soup_pickup
                + start_cooking
            )

        else:
            player_object = player.get_object()
            pot_states_dict = self.mdp.get_pot_states(state)

            # No matter the object, we can place it on a counter
            if len(self.counter_drop) > 0:
                player_actions.extend(self.place_obj_on_counter_actions(state))

            if player_object.name == "soup":
                player_actions.extend(self.deliver_soup_actions())
            elif player_object.name == "onion":
                player_actions.extend(
                    self.put_onion_in_pot_actions(pot_states_dict)
                )
            elif player_object.name == "tomato":
                player_actions.extend(
                    self.put_tomato_in_pot_actions(pot_states_dict)
                )
            elif player_object.name == "dish":
                # Not considering all pots (only ones close to ready) to reduce computation
                # NOTE: could try to calculate which pots are eligible, but would probably take
                # a lot of compute
                player_actions.extend(
                    self.pickup_soup_with_dish_actions(
                        pot_states_dict, only_nearly_ready=False
                    )
                )
            else:
                raise ValueError("Unrecognized object")

        if self.wait_allowed:
            player_actions.extend(self.wait_actions(player))

        if waiting_substitute:
            # Trying to mimic a "WAIT" action by adding the closest allowed feature to the avaliable actions
            # This is because motion plans that aren't facing terrain features (non counter, non empty spots)
            # are not considered valid
            player_actions.extend(self.go_to_closest_feature_actions(player))

        is_valid_goal_given_start = (
            lambda goal: self.motion_planner.is_valid_motion_start_goal_pair(
                player.pos_and_or, goal
            )
        )
        player_actions = list(
            filter(is_valid_goal_given_start, player_actions)
        )
        return player_actions

    def pickup_onion_actions(self, counter_objects, only_use_dispensers=False):
        """If only_use_dispensers is True, then only take onions from the dispensers"""
        onion_pickup_locations = self.mdp.get_onion_dispenser_locations()
        if not only_use_dispensers:
            onion_pickup_locations += counter_objects["onion"]
        return self._get_ml_actions_for_positions(onion_pickup_locations)

    def pickup_tomato_actions(self, counter_objects):
        tomato_dispenser_locations = self.mdp.get_tomato_dispenser_locations()
        tomato_pickup_locations = (
            tomato_dispenser_locations + counter_objects["tomato"]
        )
        return self._get_ml_actions_for_positions(tomato_pickup_locations)

    def pickup_dish_actions(self, counter_objects, only_use_dispensers=False):
        """If only_use_dispensers is True, then only take dishes from the dispensers"""
        dish_pickup_locations = self.mdp.get_dish_dispenser_locations()
        if not only_use_dispensers:
            dish_pickup_locations += counter_objects["dish"]
        return self._get_ml_actions_for_positions(dish_pickup_locations)

    def pickup_counter_soup_actions(self, counter_objects):
        soup_pickup_locations = counter_objects["soup"]
        return self._get_ml_actions_for_positions(soup_pickup_locations)

    def start_cooking_actions(self, pot_states_dict):
        """This is for start cooking a pot that is cookable"""
        cookable_pots_location = self.mdp.get_partially_full_pots(
            pot_states_dict
        ) + self.mdp.get_full_but_not_cooking_pots(pot_states_dict)
        return self._get_ml_actions_for_positions(cookable_pots_location)

    def place_obj_on_counter_actions(self, state):
        all_empty_counters = set(self.mdp.get_empty_counter_locations(state))
        valid_empty_counters = [
            c_pos for c_pos in self.counter_drop if c_pos in all_empty_counters
        ]
        return self._get_ml_actions_for_positions(valid_empty_counters)

    def deliver_soup_actions(self):
        serving_locations = self.mdp.get_serving_locations()
        return self._get_ml_actions_for_positions(serving_locations)

    def put_onion_in_pot_actions(self, pot_states_dict):
        partially_full_onion_pots = self.mdp.get_partially_full_pots(
            pot_states_dict
        )
        fillable_pots = partially_full_onion_pots + pot_states_dict["empty"]
        return self._get_ml_actions_for_positions(fillable_pots)

    def put_tomato_in_pot_actions(self, pot_states_dict):
        partially_full_onion_pots = self.mdp.get_partially_full_pots(
            pot_states_dict
        )
        fillable_pots = partially_full_onion_pots + pot_states_dict["empty"]
        return self._get_ml_actions_for_positions(fillable_pots)

    def pickup_soup_with_dish_actions(
        self, pot_states_dict, only_nearly_ready=False
    ):
        ready_pot_locations = pot_states_dict["ready"]
        nearly_ready_pot_locations = pot_states_dict["cooking"]
        if not only_nearly_ready:
            partially_full_pots = self.mdp.get_partially_full_pots(
                pot_states_dict
            )
            nearly_ready_pot_locations = (
                nearly_ready_pot_locations
                + pot_states_dict["empty"]
                + partially_full_pots
            )
        return self._get_ml_actions_for_positions(
            ready_pot_locations + nearly_ready_pot_locations
        )

    def go_to_closest_feature_actions(self, player):
        feature_locations = (
            self.mdp.get_onion_dispenser_locations()
            + self.mdp.get_tomato_dispenser_locations()
            + self.mdp.get_pot_locations()
            + self.mdp.get_dish_dispenser_locations()
        )
        closest_feature_pos = self.motion_planner.min_cost_to_feature(
            player.pos_and_or, feature_locations, with_argmin=True
        )[1]
        return self._get_ml_actions_for_positions([closest_feature_pos])

    def go_to_closest_feature_or_counter_to_goal(
        self, goal_pos_and_or, goal_location
    ):
        """Instead of going to goal_pos_and_or, go to the closest feature or counter to this goal, that ISN'T the goal itself"""
        valid_locations = (
            self.mdp.get_onion_dispenser_locations()
            + self.mdp.get_tomato_dispenser_locations()
            + self.mdp.get_pot_locations()
            + self.mdp.get_dish_dispenser_locations()
            + self.counter_drop
        )
        valid_locations.remove(goal_location)
        closest_non_goal_feature_pos = self.motion_planner.min_cost_to_feature(
            goal_pos_and_or, valid_locations, with_argmin=True
        )[1]
        return self._get_ml_actions_for_positions(
            [closest_non_goal_feature_pos]
        )

    def wait_actions(self, player):
        waiting_motion_goal = (player.position, player.orientation)
        return [waiting_motion_goal]

    def _get_ml_actions_for_positions(self, positions_list):
        """Determine what are the ml actions (joint motion goals) for a list of positions

        Args:
            positions_list (list): list of target terrain feature positions
        """
        possible_motion_goals = []
        for pos in positions_list:
            # All possible ways to reach the target feature
            for (
                motion_goal
            ) in self.joint_motion_planner.motion_planner.motion_goals_for_pos[
                pos
            ]:
                possible_motion_goals.append(motion_goal)
        return possible_motion_goals
