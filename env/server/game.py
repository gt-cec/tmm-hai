from abc import ABC, abstractmethod
from threading import Lock, Thread
from queue import Queue, LifoQueue, Empty, Full, PriorityQueue
from time import time
from overcooked_ai.src.overcooked_ai_py.mdp.overcooked_mdp import OvercookedGridworld
from overcooked_ai.src.overcooked_ai_py.mdp.actions import Action, Direction
from overcooked_ai.src.overcooked_ai_py.planning.planners import MotionPlanner, NO_COUNTERS_PARAMS
# from overcooked_ai_py.rllib import load_agent
import random, os, pickle, json

# Relative path to where all static pre-trained agents are stored on server
AGENT_DIR = None

# Maximum allowable game time (in seconds)
MAX_GAME_TIME = None

VISIBILITY = "D"
VISIBILITY_RANGE = 4

def _configure(max_game_time, agent_dir, visibility, visibility_range):
    global AGENT_DIR, MAX_GAME_TIME, VISIBILITY, VISIBILITY_RANGE
    MAX_GAME_TIME = max_game_time
    AGENT_DIR = agent_dir
    VISIBILITY = visibility
    VISIBILITY_RANGE = visibility_range

def fix_bc_path(path):
    """
    Loading a PPO agent trained with a BC agent requires loading the BC model as well when restoring the trainer, even though the BC model is not used in game
    For now the solution is to include the saved BC model and fix the relative path to the model in the config.pkl file
    """

    import pickle 
    #the path is the agents/Rllib.*/agent directory
    agent_path = os.path.dirname(path)
    with open(os.path.join(agent_path,"config.pkl"), "rb") as f:
        data = pickle.load(f)
    bc_model_dir = data["bc_params"]["bc_config"]["model_dir"]
    last_dir = os.path.basename(bc_model_dir)
    bc_model_dir = os.path.join(agent_path,"bc_params",last_dir)
    data["bc_params"]["bc_config"]["model_dir"]= bc_model_dir
    with open(os.path.join(agent_path,"config.pkl"), "wb") as f:
        pickle.dump(data,f)
            


class Game(ABC):

    """
    Class representing a game object. Coordinates the simultaneous actions of arbitrary
    number of players. Override this base class in order to use. 

    Players can post actions to a `pending_actions` queue, and driver code can call `tick` to apply these actions.


    It should be noted that most operations in this class are not on their own thread safe. Thus, client code should
    acquire `self.lock` before making any modifications to the instance. 

    One important exception to the above rule is `enqueue_actions` which is thread safe out of the box
    """

    # Possible TODO: create a static list of IDs used by the class so far to verify id uniqueness
    # This would need to be serialized, however, which might cause too great a performance hit to 
    # be worth it

    EMPTY = 'EMPTY'
    
    class Status:
        DONE = 'done'
        ACTIVE = 'active'
        RESET = 'reset'
        INACTIVE = 'inactive'
        ERROR = 'error'

    def __init__(self, *args, **kwargs):
        """
        players (list): List of IDs of players currently in the game
        spectators (set): Collection of IDs of players that are not allowed to enqueue actions but are currently watching the game
        id (int):   Unique identifier for this game
        pending_actions List[(Queue)]: Buffer of (player_id, action) pairs have submitted that haven't been commited yet
        lock (Lock):    Used to serialize updates to the game state
        is_active(bool): Whether the game is currently being played or not
        """
        self.players = []
        self.spectators = set()
        self.pending_actions = []
        self.id = kwargs.get('id', id(self))
        self.lock = Lock()
        self._is_active = False

    @abstractmethod
    def is_full(self):
        """
        Returns whether there is room for additional players to join or not
        """
        pass

    @abstractmethod
    def apply_action(self, player_idx, action):
        """
        Updates the game state by applying a single (player_idx, action) tuple. Subclasses should try to override this method
        if possible
        """
        pass


    @abstractmethod
    def is_finished(self):
        """
        Returns whether the game has concluded or not
        """
        pass

    def is_ready(self):
        """
        Returns whether the game can be started. Defaults to having enough players
        """
        return self.is_full()

    @property
    def is_active(self):
        """
        Whether the game is currently being played
        """
        return self._is_active

    @property
    def reset_timeout(self):
        """
        Number of milliseconds to pause game on reset
        """
        return 3000

    def apply_actions(self):
        """
        Updates the game state by applying each of the pending actions in the buffer. Is called by the tick method. Subclasses
        should override this method if joint actions are necessary. If actions can be serialized, overriding `apply_action` is 
        preferred
        """
        for i in range(len(self.players)):
            try:
                while True:
                    action = self.pending_actions[i].get(block=False)
                    self.apply_action(i, action)
            except Empty:
                pass

    def activate(self):
        """
        Activates the game to let server know real-time updates should start. Provides little functionality but useful as
        a check for debugging
        """
        self._is_active = True

    def deactivate(self):
        """
        Deactives the game such that subsequent calls to `tick` will be no-ops. Used to handle case where game ends but 
        there is still a buffer of client pings to handle
        """
        self._is_active = False

    def reset(self):
        """
        Restarts the game while keeping all active players by resetting game stats and temporarily disabling `tick`
        """
        if not self.is_active:
            raise ValueError("Inactive Games cannot be reset")
        if self.is_finished():
            return self.Status.DONE
        self.deactivate()
        self.activate()
        return self.Status.RESET

    def needs_reset(self):
        """
        Returns whether the game should be reset on the next call to `tick`
        """
        return False


    def tick(self):
        """
        Updates the game state by applying each of the pending actions. This is done so that players cannot directly modify
        the game state, offering an additional level of safety and thread security. 

        One can think of "enqueue_action" like calling "git add" and "tick" like calling "git commit"

        Subclasses should try to override `apply_actions` if possible. Only override this method if necessary
        """ 
        if not self.is_active:
            return self.Status.INACTIVE
        if self.needs_reset():
            self.reset()
            return self.Status.RESET

        self.apply_actions()
        return self.Status.DONE if self.is_finished() else self.Status.ACTIVE
    
    def enqueue_action(self, player_id, action):
        """
        Add (player_id, action) pair to the pending action queue, without modifying underlying game state

        Note: This function IS thread safe
        """
        if not self.is_active:
            # Could run into issues with is_active not being thread safe
            return
        if player_id not in self.players:
            # Only players actively in game are allowed to enqueue actions
            return
        try:
            player_idx = self.players.index(player_id)
            # Jack: clearing the queue so we can have a lower frame rate
            self.pending_actions[player_idx].empty()
            self.pending_actions[player_idx].put(action)
        except Full:
            pass

    def get_state(self):
        """
        Return a JSON compatible serialized state of the game. Note that this should be as minimalistic as possible
        as the size of the game state will be the most important factor in game performance. This is sent to the client
        every frame update.
        """
        return { "players" : self.players }

    def to_json(self):
        """
        Return a JSON compatible serialized state of the game. Contains all information about the game, does not need to
        be minimalistic. This is sent to the client only once, upon game creation
        """
        return self.get_state()

    def is_empty(self):
        """
        Return whether it is safe to garbage collect this game instance
        """
        return not self.num_players

    def add_player(self, player_id, idx=None, buff_size=-1):
        """
        Add player_id to the game
        """
        if self.is_full():
            raise ValueError("Cannot add players to full game")
        if self.is_active:
            raise ValueError("Cannot add players to active games")
        if not idx and self.EMPTY in self.players:
            idx = self.players.index(self.EMPTY)
        elif not idx:
            idx = len(self.players)
        
        padding = max(0, idx - len(self.players) + 1)
        for _ in range(padding):
            self.players.append(self.EMPTY)
            self.pending_actions.append(self.EMPTY)
        
        self.players[idx] = player_id
        self.pending_actions[idx] = Queue(maxsize=buff_size)

    def add_spectator(self, spectator_id):
        """
        Add spectator_id to list of spectators for this game
        """
        if spectator_id in self.players:
            raise ValueError("Cannot spectate and play at same time")
        self.spectators.add(spectator_id)

    def remove_player(self, player_id):
        """
        Remove player_id from the game
        """
        try:
            idx = self.players.index(player_id)
            self.players[idx] = self.EMPTY
            self.pending_actions[idx] = self.EMPTY
        except ValueError:
            return False
        else:
            return True

    def remove_spectator(self, spectator_id):
        """
        Removes spectator_id if they are in list of spectators. Returns True if spectator successfully removed, False otherwise
        """
        try:
            self.spectators.remove(spectator_id)
        except ValueError:
            return False
        else:
            return True


    def clear_pending_actions(self):
        """
        Remove all queued actions for all players
        """
        for i, player in enumerate(self.players):
            if player != self.EMPTY:
                queue = self.pending_actions[i]
                queue.queue.clear()

    @property
    def num_players(self):
        return len([player for player in self.players if player != self.EMPTY])

    def get_data(self):
        """
        Return any game metadata to server driver. Really only relevant for Psiturk code
        """
        return {}
        


class DummyGame(Game):

    """
    Standin class used to test basic server logic
    """

    def __init__(self, **kwargs):
        super(DummyGame, self).__init__(**kwargs)
        self.counter = 0

    def is_full(self):
        return self.num_players == 2

    def apply_action(self, idx, action):
        pass

    def apply_actions(self):
        self.counter += 1

    def is_finished(self):
        return self.counter >= 100

    def get_state(self):
        state = super(DummyGame, self).get_state()
        state['count'] = self.counter
        return state


class DummyInteractiveGame(Game):

    """
    Standing class used to test interactive components of the server logic
    """

    def __init__(self, **kwargs):
        super(DummyInteractiveGame, self).__init__(**kwargs)
        self.max_players = int(kwargs.get('playerZero', 'human') == 'human') + int(kwargs.get('playerOne', 'human') == 'human')
        self.max_count = kwargs.get('max_count', 30)
        self.counter = 0
        self.counts = [0] * self.max_players

    def is_full(self):
        return self.num_players == self.max_players

    def is_finished(self):
        return max(self.counts) >= self.max_count

    def apply_action(self, player_idx, action):
        if action.upper() == Direction.NORTH:
            self.counts[player_idx] += 1
        if action.upper() == Direction.SOUTH:
            self.counts[player_idx] -= 1

    def apply_actions(self):
        super(DummyInteractiveGame, self).apply_actions()
        self.counter += 1

    def get_state(self):
        state = super(DummyInteractiveGame, self).get_state()
        state['count'] = self.counter
        for i in range(self.num_players):
            state['player_{}_count'.format(i)] = self.counts[i]
        return state

    
class OvercookedGame(Game):
    """
    Class for bridging the gap between Overcooked_Env and the Game interface

    Instance variable:
        - max_players (int): Maximum number of players that can be in the game at once
        - mdp (OvercookedGridworld): Controls the underlying Overcooked game logic
        - score (int): Current reward acheived by all players
        - max_time (int): Number of seconds the game should last
        - npc_policies (dict): Maps user_id to policy (Agent) for each AI player
        - npc_state_queues (dict): Mapping of NPC user_ids to LIFO queues for the policy to process
        - curr_tick (int): How many times the game server has called this instance's `tick` method
        - ticker_per_ai_action (int): How many frames should pass in between NPC policy forward passes. 
            Note that this is a lower bound; if the policy is computationally expensive the actual frames
            per forward pass can be higher
        - action_to_overcooked_action (dict): Maps action names returned by client to action names used by OvercookedGridworld
            Note that this is an instance variable and not a static variable for efficiency reasons
        - human_players (set(str)): Collection of all player IDs that correspond to humans
        - npc_players (set(str)): Collection of all player IDs that correspond to AI
        - randomized (boolean): Whether the order of the layouts should be randomized
    
    Methods:
        - npc_policy_consumer: Background process that asynchronously computes NPC policy forward passes. One thread
            spawned for each NPC
        - _curr_game_over: Determines whether the game on the current mdp has ended
    """

    def __init__(self, layouts=["cramped_room"], mdp_params={}, num_players=2, gameTime=30, playerZero='human', playerOne='human', showPotential=False, randomized=False, **kwargs):
        super(OvercookedGame, self).__init__(**kwargs)
        self.show_potential = showPotential
        self.mdp_params = mdp_params
        self.layouts = layouts
        self.max_players = int(num_players)
        self.mdp = None
        self.mp = None
        self.score = 0
        self.phi = 0
        self.max_time = min(int(gameTime), MAX_GAME_TIME)
        self.npc_policies = {}
        self.npc_state_queues = {}
        self.action_to_overcooked_action = {
            "STAY" : Action.STAY,
            "UP" : Direction.NORTH,
            "DOWN" : Direction.SOUTH,
            "LEFT" : Direction.WEST,
            "RIGHT" : Direction.EAST,
            "SPACE" : Action.INTERACT
        }
        self.ticks_per_ai_action = 5
        self.curr_tick = 0
        self.human_players = set()
        self.npc_players = set()
        self.visibility = VISIBILITY
        self.visibility_range = VISIBILITY_RANGE
        self.stage = 0

        if randomized:
            random.shuffle(self.layouts)

        if playerZero != 'human':
            player_zero_id = playerZero + '_0'
            self.add_player(player_zero_id, idx=0, buff_size=1, is_human=False)
            self.npc_policies[player_zero_id] = self.get_policy(playerZero, idx=0)
            self.npc_state_queues[player_zero_id] = LifoQueue()

        if playerOne != 'human':
            player_one_id = playerOne + '_1'
            self.add_player(player_one_id, idx=1, buff_size=1, is_human=False)
            self.npc_policies[player_one_id] = self.get_policy(playerOne, idx=1)
            self.npc_state_queues[player_one_id] = LifoQueue()
        

    def _curr_game_over(self):
        return time() - self.start_time >= self.max_time


    def needs_reset(self):
        return self._curr_game_over() and not self.is_finished()


    def add_player(self, player_id, idx=None, buff_size=-1, is_human=True):
        super(OvercookedGame, self).add_player(player_id, idx=idx, buff_size=buff_size)
        if is_human:
            self.human_players.add(player_id)
        else:
            self.npc_players.add(player_id)


    def remove_player(self, player_id):
        removed = super(OvercookedGame, self).remove_player(player_id)
        if removed:
            if player_id in self.human_players:
                self.human_players.remove(player_id)
            elif player_id in self.npc_players:
                self.npc_players.remove(player_id)
            else:
                raise ValueError("Inconsistent state")


    def npc_policy_consumer(self, policy_id):
        queue = self.npc_state_queues[policy_id]
        policy = self.npc_policies[policy_id]
        while self._is_active:
            state = queue.get()
            npc_action, _ = policy.action(state)
            super(OvercookedGame, self).enqueue_action(policy_id, npc_action)


    def is_full(self):
        return self.num_players >= self.max_players

    def is_finished(self):
        val = not self.layouts and self._curr_game_over()
        return val

    def is_empty(self):
        """
        Game is considered safe to scrap if there are no active players or if there are no humans (spectating or playing)
        """
        return super(OvercookedGame, self).is_empty() or not self.spectators and not self.human_players

    def is_ready(self):
        """
        Game is ready to be activated if there are a sufficient number of players and at least one human (spectator or player)
        """
        return super(OvercookedGame, self).is_ready() and not self.is_empty()

    def apply_action(self, player_id, action):
        pass

    def apply_actions(self):
        # Default joint action, as NPC policies and clients probably don't enqueue actions fast 
        # enough to produce one at every tick
        joint_action = [Action.STAY] * len(self.players)

        # Synchronize individual player actions into a joint-action as required by overcooked logic
        for i in range(len(self.players)):
            try:
                joint_action[i] = self.pending_actions[i].get(block=False)
            except Empty:
                pass
        
        # Apply overcooked game logic to get state transition
        prev_state = self.state
        self.state, info = self.mdp.get_state_transition(prev_state, joint_action)
        if self.show_potential:
            self.phi = self.mdp.potential_function(prev_state, self.mp, gamma=0.99)

        # Send next state to all background consumers if needed
        if self.curr_tick % self.ticks_per_ai_action == 0:
            for npc_id in self.npc_policies:
                self.npc_state_queues[npc_id].put(self.state, block=False)

        # Update score based on soup deliveries that might have occured
        curr_reward = sum(info['sparse_reward_by_agent'])
        self.score += curr_reward

        # Return about the current transition
        return prev_state, joint_action, info
        

    def enqueue_action(self, player_id, action):
        overcooked_action = self.action_to_overcooked_action[action]
        super(OvercookedGame, self).enqueue_action(player_id, overcooked_action)

    def reset(self):
        status = super(OvercookedGame, self).reset()
        if status == self.Status.RESET:
            # Hacky way of making sure game timer doesn't "start" until after reset timeout has passed
            self.start_time += self.reset_timeout / 1000


    def tick(self):
        self.curr_tick += 1
        return super(OvercookedGame, self).tick()

    def activate(self, curr_layout=None, folder=None):
        super(OvercookedGame, self).activate()

        # Sanity check at start of each game
        if not self.npc_players.union(self.human_players) == set(self.players):
            raise ValueError("Inconsistent State")
        
        self.curr_layout = curr_layout
        self.mdp = OvercookedGridworld.from_layout_name(self.curr_layout, folder=folder, **self.mdp_params)
        if self.show_potential:
            self.mp = MotionPlanner.from_pickle_or_compute(self.mdp, counter_goals=NO_COUNTERS_PARAMS)
        self.state = self.mdp.get_standard_start_state()
        if self.show_potential:
            self.phi = self.mdp.potential_function(self.state, self.mp, gamma=0.99)
        self.start_time = time()
        self.curr_tick = 0
        self.score = 0
        self.threads = []
        for npc_policy in self.npc_policies:
            self.npc_policies[npc_policy].reset()
            self.npc_state_queues[npc_policy].put(self.state)
            t = Thread(target=self.npc_policy_consumer, args=(npc_policy,))
            self.threads.append(t)
            t.start()
        
    def deactivate(self):
        super(OvercookedGame, self).deactivate()
        # Ensure the background consumers do not hang
        for npc_policy in self.npc_policies:
            self.npc_state_queues[npc_policy].put(self.state)

        # Wait for all background threads to exit
        for t in self.threads:
            t.join()

        # Clear all action queues
        self.clear_pending_actions()

    def get_state(self):
        state_dict = {}
        state_dict['potential'] = self.phi if self.show_potential else None
        state_dict['state'] = self.state.to_dict()
        state_dict['score'] = self.score
        state_dict['state']['visibility'] = self.get_visibility()
        state_dict['time_left'] = max(self.max_time - (time() - self.start_time), 0)
        state_dict['layout'] = self.curr_layout
        return state_dict

    def to_json(self):
        obj_dict = {}
        obj_dict['terrain'] = self.mdp.terrain_mtx if self._is_active else None
        obj_dict['state'] = self.get_state() if self._is_active else None
        return obj_dict

    def get_policy(self, npc_id, idx=0):
        return FSMAI(self)
        # return DummyAI()  # Jack: replacing this DummyAI with a FSMAI
    
    def get_visibility(self):
        visible = []
        width = len(self.mdp.terrain_mtx[0])
        height = len(self.mdp.terrain_mtx)
        for row in range(height):
            visible.append([])
            for col in range(width):
                visible[row].append([
                    self.can_see(self.visibility, self.state.players[0].orientation, col - self.state.players[0].position[0], row - (self.state.players[0].position[1])),
                    self.can_see(self.visibility, self.state.players[1].orientation, col - self.state.players[1].position[0], row - (self.state.players[1].position[1]))
                ])
        return visible


    # checks whether the agent can see the object
    def can_see(self, visibility, agent_orientation, dX, dY):       
        # V visibility: agents sees everything in front of them with 90deg field of view (45deg angles)
        if visibility == "V":
            # agent facing right, ignore items to left of agent and beyond 45deg (dY > dX)
            if agent_orientation == (1, 0) and (dX < 0 or abs(dY) > abs(dX) or dY * dY + dX * dX > self.visibility_range * self.visibility_range):
                return False
            # agent facing left, ignore items to right of agent and beyond 45deg (dY > dX)
            if agent_orientation == (-1, 0) and (dX > 0 or abs(dY) > abs(dX) or dY * dY + dX * dX > self.visibility_range * self.visibility_range):
                return False
            # agent facing up, ignore items to down of agent and beyond 45deg (dX > dY)
            if agent_orientation == (0, 1) and (dY < 0 or abs(dX) > abs(dY) or dY * dY + dX * dX > self.visibility_range * self.visibility_range):
                return False
            # agent facing down, ignore items to up of agent and beyond 45deg (dX > dY)
            if agent_orientation == (0, -1) and (dY > 0 or abs(dX) > abs(dY) or dY * dY + dX * dX > self.visibility_range * self.visibility_range):
                return False

        # D visibility: agents see everything in front of them to a radius
        elif visibility == "D":
            # agent facing right, ignore items to left of agent and where dist > max
            if agent_orientation == (1, 0) and (dX < 0 or dY * dY + dX * dX > self.visibility_range * self.visibility_range):
                return False
            # agent facing left, ignore items to right of agent and where dist > max
            if agent_orientation == (-1, 0) and (dX > 0 or dY * dY + dX * dX > self.visibility_range * self.visibility_range):
                return False
            # agent facing up, ignore items to down of agent and where dist > max
            if agent_orientation == (0, 1) and (dY < 0 or dY * dY + dX * dX > self.visibility_range * self.visibility_range):
                return False
            # agent facing down, ignore items to up of agent and where dist > max
            if agent_orientation == (0, -1) and (dY > 0 or dY * dY + dX * dX > self.visibility_range * self.visibility_range):
                return False
        
        # O visibility: agents see everything around them to a radius
        elif visibility == "O":
            # ignore items where dist > max
            if dY * dY + dX * dX > self.visibility_range * self.visibility_range:
                return False
            
        return True

class DummyOvercookedGame(OvercookedGame):
    """
    Class that hardcodes the AI to be random. Used for debugging
    """
    
    def __init__(self, layouts=["cramped_room"], **kwargs):
        super(DummyOvercookedGame, self).__init__(layouts, **kwargs)

    def get_policy(self, *args, **kwargs):
        return DummyAI()


class FSMAI():
    """
    Uses a simple FSM for cooking
    """
    def __init__(self, game):
        self.fsm = ["get ingredient",
                    "place in pot",
                    "check pot full",
                    "get plate",
                    "fill from cooked pot",
                    "serve dish"]  # the recipe
        self.fsm_state_recipe = 0  # the point in the recipe the AI is at
        self.fsm_state = self.fsm[self.fsm_state_recipe]  # the action the AI is doing next
        self.game = game
        self.state = None

        # FSM params
        self.plan = []

    # for A*: gets heuristic (squared dist)
    def h(self, curr, goal):
        return (goal[0] - curr[0]) * (goal[0] - curr[0]) + (goal[1] - curr[1]) * (goal[1] - curr[1])

    # for A*: checks whether a block is a floor
    def check_floor(self, loc):
        # check bounds
        # X
        if loc[0] >= len(self.game.mdp.terrain_mtx[0]) or loc[0] < 0:
            return False
        # Y
        if loc[1] >= len(self.game.mdp.terrain_mtx) or loc[1] < 0:
            return False
        # open space
        if self.game.mdp.terrain_mtx[loc[1]][loc[0]] != ' ':
            return False
        # player is there
        if self.state.players[1].position == loc:
            return False
        return True
    
    # for A*: checks whether a square is valid and adds it to the frontier
    def frontier_push(self, loc, goal, frontier, paths, parent):
        if (loc not in paths and self.check_floor(loc)) or loc == goal:
            frontier.put((self.h(loc, goal), loc))
            paths[loc] = parent
        return frontier, paths

    # for A*: find the path to the goal
    def a_star(self, curr, goal):
        # make the queue
        paths = {}
        frontier = PriorityQueue()
        frontier.put((0, curr))
        # run A*
        while frontier.qsize() > 0:
            # pull from the queue
            loc = frontier.get()[1]
            # end if the goal
            if loc == goal:
                break
            # add neighbors to frontier and paths
            frontier, paths = self.frontier_push((loc[0], loc[1]-1), goal, frontier, paths, loc)
            frontier, paths = self.frontier_push((loc[0]+1, loc[1]), goal, frontier, paths, loc)
            frontier, paths = self.frontier_push((loc[0], loc[1]+1), goal, frontier, paths, loc)
            frontier, paths = self.frontier_push((loc[0]-1, loc[1]), goal, frontier, paths, loc)
        # if no paths to goal, return empty
        if goal not in paths:
            return []
        # reconstruct the path
        stone = goal
        path = [goal]
        while stone != curr:
            stone = paths[stone]
            path.append(stone)
        return path
    
    # uses A* to plan to a go to a square
    def go_to_square(self, curr, goal):
        path = self.a_star(curr, goal)
        return path
    
    # determine the action needed for the agent to face a goal
    def facing_square(self, agent_position, agent_orientation, goal_position):
        # up (< and -1 because 0,0 is at top left)
        if goal_position[1] < agent_position[1] and agent_orientation != (0, -1):
            return Direction.NORTH
        # right
        elif goal_position[0] > agent_position[0] and agent_orientation != (1, 0):
            return Direction.EAST
        # down (> and 1 because 0,0 is at top left)
        elif goal_position[1] > agent_position[1] and agent_orientation != (0, 1):
            return Direction.SOUTH
        # left
        elif goal_position[0] < agent_position[0] and agent_orientation != (-1, 0):
            return Direction.WEST
        return Action.STAY

    # move to the next state
    def move_to_next_recipe_state(self):
        self.fsm_state_recipe = self.fsm_state_recipe + 1 if self.fsm_state_recipe < len(self.fsm) - 1 else 0
        self.fsm_state = self.fsm[self.fsm_state_recipe]

    # gets the closest appliance of type
    def get_closest_appliance(self, player_position, appliance, pot_state=""):
        appliance_position = None
        appliance_dist = float("inf")
        pot_states = self.game.mdp.get_pot_states(self.state)
        for row in range(len(self.game.mdp.terrain_mtx)):
            for col in range(len(self.game.mdp.terrain_mtx[row])):
                position = (col, row)
                # check if the terrain is this appliance
                if self.game.mdp.terrain_mtx[row][col] == appliance:
                    # if appliance is a pot, check the pot state
                    if appliance == 'P' and pot_state != "":
                        # if looking for unfilled pots
                        if pot_state == "unfilled" and position not in pot_states['empty'] and position not in pot_states['1_items'] and position not in pot_states['2_items']:
                            continue
                        # if looking for cooking pots
                        if pot_state == "cooking" and position not in pot_states['cooking'] and position not in pot_states['ready']:
                            continue
                    # if dist is closer update the target ingredient
                    dist = self.h((row, col), player_position)
                    if dist < appliance_dist:
                        appliance_dist = dist
                        appliance_position = position
        return appliance_position
    
    # pick a random direction to go
    def pick_random_direction(self, state):
        dirs = []
        # up
        if self.check_floor([state.player_positions[0][0], state.player_positions[0][1]-1]):
            dirs.append(Direction.NORTH)
        # right
        if self.check_floor([state.player_positions[0][0]+1, state.player_positions[0][1]]):
            dirs.append(Direction.EAST)
        # down
        if self.check_floor([state.player_positions[0][0], state.player_positions[0][1]+1]):
            dirs.append(Direction.SOUTH)
        # left
        if self.check_floor([state.player_positions[0][0]-1, state.player_positions[0][1]]):
            dirs.append(Direction.WEST)
        if len(dirs) > 0:
            return dirs[random.randint(0, len(dirs)-1)]
        return Action.STAY

    # determines the next action
    def action(self, state):
        agent_position = state.player_positions[0]
        agent_orientation = state.player_orientations[0]
        self.state = state
        
        # plan with the FSM
        if self.fsm_state == "moving":
            # if the path if complete (last spot is the goal, which should be on a counter), move on
            if len(self.path) == 1:
                # return to the FSM
                self.fsm_state = self.fsm[self.fsm_state_recipe]

            # check if the agent is on track
            if agent_position == self.path[-1]:
                self.path.pop()

            # check if player if blocking, if so, choose random direction
            if self.path[-1] == self.state.players[1].position:
                return self.pick_random_direction(state), None

            # move to the next position
            # up (-1 because 0,0 is at the top left)
            if self.path[-1][1] == agent_position[1]-1 and self.path[-1][0] == agent_position[0]:
                return Direction.NORTH, None
            # right
            elif self.path[-1][0] == agent_position[0]+1 and self.path[-1][1] == agent_position[1]:
                return Direction.EAST, None
            # down (-1 because 0,0 is at the top left)
            elif self.path[-1][1] == agent_position[1]+1 and self.path[-1][0] == agent_position[0]:
                return Direction.SOUTH, None
            # left
            elif self.path[-1][0] == agent_position[0]-1 and self.path[-1][1] == agent_position[1]:
                return Direction.WEST, None
            # if none of these are true, the agent is off course
            else:
                # should reroute in this case
                self.fsm_state = self.fsm[self.fsm_state_recipe]
                return self.pick_random_direction(state), None

        # 1) goes to nearest ingredient, 2) faces ingredient, 3) picks up ingredient
        if self.fsm_state == "get ingredient":
            # if holding an ingredient, move on
            if state.players[0].held_object is not None:
                self.move_to_next_recipe_state()
                return self.pick_random_direction(state), None
            
            # find the closest ingredient
            ingredient_position = None
            ingredient_dist = float("inf")
            for item_position in state.objects:
                # check if valid ingredient
                if state.objects[item_position].name in ["tomato", "onion"]:
                    # if dist is closer update the target ingredient
                    dist = self.h(agent_position, item_position)
                    if dist < ingredient_dist:
                        ingredient_dist = dist
                        ingredient_position = item_position
            # if no ingredients, just stay
            if ingredient_position is None:
                return Action.STAY, None
            # plan to that ingredient
            self.path = self.go_to_square(agent_position, ingredient_position)
            # if route is blocked, choose a random direction
            if len(self.path) == 0:
                return self.pick_random_direction(state), None
            # if the agent is not immediately in front of the ingredient, move to it
            if len(self.path) > 2:
                self.fsm_state = "moving"
                return self.pick_random_direction(state), None
            # if the agent is not facing the ingredient, face it
            facing = self.facing_square(agent_position, agent_orientation, ingredient_position)
            if facing != Action.STAY:
                return facing, None
            # if the agent is not holding an ingredient, pick it up
            elif state.players[0].held_object is None:
                return Action.INTERACT, None               
            
        # 1) goes to uncooked pot, 2) faces pot, 3) places ingredient in pot
        if self.fsm_state == "place in pot":
            # if not holding an ingredient, move on
            if state.players[0].held_object is None:
                self.move_to_next_recipe_state()
                return self.pick_random_direction(state), None
            
            # find the closest unfull pot
            pot_position = self.get_closest_appliance(agent_position, 'P', pot_state="unfilled")
            # if there are no unfilled pots, wait
            if pot_position is None:
                return self.pick_random_direction(state), None             
            # plan to that pot
            self.path = self.go_to_square(agent_position, pot_position)
            # if the path is empty, go a random direction
            if self.path == []:
                return Action.STAY, None
            # if the agent is not immediately in front of the ingredient, move to it
            if len(self.path) > 2:
                self.fsm_state = "moving"
                return Action.STAY, None
            # if the agent is not facing the pot, face it
            facing = self.facing_square(agent_position, agent_orientation, pot_position)
            if facing != Action.STAY:
                return facing, None
            # if the agent is holding an ingredient, place it in the pot
            elif state.players[0].held_object is not None:
                return Action.INTERACT, None     
            
        # 1) checks if nearest pot is filled
        if self.fsm_state == "check pot full":
            # find the closest pot
            pot_position = self.get_closest_appliance(agent_position, 'P')
            pot_states = self.game.mdp.get_pot_states(self.state)
            # if pot is full, get a plate
            if pot_position in pot_states["cooking"] or pot_position in pot_states["ready"]:
                self.move_to_next_recipe_state()
                return self.pick_random_direction(state), None
            # otherwise, add another ingredient
            else:
                self.fsm_state_recipe = 0  # 0 : get ingredient
                self.fsm_state = self.fsm[self.fsm_state_recipe]
                return self.pick_random_direction(state), None
            
        # 1) goes to nearest plate, 2) picks it up
        if self.fsm_state == "get plate":
            # if not holding a plate, move on
            if state.players[0].held_object is not None and state.players[0].held_object.name == "dish":
                self.move_to_next_recipe_state()
                return self.pick_random_direction(state), None
            
            # find the closest plate
            plate_position = None
            plate_dist = float("inf")
            for item_position in state.objects:
                # check if valid ingredient
                if state.objects[item_position].name == "dish":
                    # if dist is closer update the target plate
                    dist = self.h(agent_position, item_position)
                    if dist < plate_dist:
                        plate_dist = dist
                        plate_position = item_position
            if plate_position is None:
                return self.pick_random_direction(state)
            # plan to that plate
            self.path = self.go_to_square(agent_position, plate_position)
            # if the agent is not immediately in front of the plate, move to it
            if len(self.path) > 2:
                self.fsm_state = "moving"
                return Action.STAY, None
            # if the agent is not facing the plate, face it
            facing = self.facing_square(agent_position, agent_orientation, plate_position)
            if facing != Action.STAY:
                return facing, None
            # if the agent is not holding an plate, pick it up
            elif state.players[0].held_object is None:
                return Action.INTERACT, None      

        # 1) goes to nearest cooking or cooked pot, 2) fills the dish
        if self.fsm_state == "fill from cooked pot":
            # if not holding a plate, start over
            if state.players[0].held_object is None:
                self.fsm_state_recipe = 0
                self.fsm_state = self.fsm[self.fsm_state_recipe]
                return self.pick_random_direction(state), None
            
            # if holding soup, move on
            if state.players[0].held_object.name == "soup":
                self.move_to_next_recipe_state()
                return self.pick_random_direction(state), None

            # find the closest complete or cooking pot
            pot_position = self.get_closest_appliance(agent_position, 'P', pot_state="cooking")
            # if there are no unfilled pots, wait
            if pot_position is None:
                return self.pick_random_direction(state), None  
            # plan to that pot
            self.path = self.go_to_square(agent_position, pot_position)
            # if the agent is not immediately in front of the ingredient, move to it
            if len(self.path) > 2:
                self.fsm_state = "moving"
                return Action.STAY, None
            # if the agent is not facing the pot, face it
            facing = self.facing_square(agent_position, agent_orientation, pot_position)
            if facing != Action.STAY:
                return facing, None
            # if the agent is holding a dish, fill it
            elif state.players[0].held_object is not None:
                return Action.INTERACT, None    

        # 1) goes to nearest serving station, 2) serves dish
        if self.fsm_state == "serve dish":
            # if not holding a soup, start over
            if state.players[0].held_object is None or state.players[0].held_object.name != "soup":
                self.fsm_state_recipe = 0
                self.fsm_state = self.fsm[self.fsm_state_recipe]
                return Action.STAY, None

            # find the closest serving station
            serving_position = self.get_closest_appliance(agent_position, 'S')
            # plan to that station
            self.path = self.go_to_square(agent_position, serving_position)
            # if the agent is not immediately in front of the ingredient, move to it
            if len(self.path) > 2:
                self.fsm_state = "moving"
                return self.pick_random_direction(state), None
            # if the agent is not facing the station, face it
            facing = self.facing_square(agent_position, agent_orientation, serving_position)
            if facing != Action.STAY:
                return facing, None
            # if the agent is holding a soup, serve it
            elif state.players[0].held_object.name == "soup":
                return Action.INTERACT, None  
            
        print("Escaped from FSM!")
        return self.pick_random_direction(state), None

    def reset(self):
        pass


class DummyAI():
    """
    Randomly samples actions. Used for debugging
    """
    def action(self, state):
        [action] = random.sample([Action.STAY, Direction.NORTH, Direction.SOUTH, Direction.WEST, Direction.EAST, Action.INTERACT], 1)
        return action, None

    def reset(self):
        pass

class DummyComputeAI(DummyAI):
    """
    Performs simulated compute before randomly sampling actions. Used for debugging
    """
    def __init__(self, compute_unit_iters=1e5):
        """
        compute_unit_iters (int): Number of for loop cycles in one "unit" of compute. Number of 
                                    units performed each time is randomly sampled
        """
        super(DummyComputeAI, self).__init__()
        self.compute_unit_iters = int(compute_unit_iters)
    
    def action(self, state):
        # Randomly sample amount of time to busy wait
        iters = random.randint(1, 10) * self.compute_unit_iters

        # Actually compute something (can't sleep) to avoid scheduling optimizations
        val = 0
        for i in range(iters):
            # Avoid branch prediction optimizations
            if i % 2 == 0:
                val += 1
            else:
                val += 2
        
        # Return randomly sampled action
        return super(DummyComputeAI, self).action(state)

    
class StayAI():
    """
    Always returns "stay" action. Used for debugging
    """
    def action(self, state):
        return Action.STAY, None

    def reset(self):
        pass


class TutorialAI():

    COOK_SOUP_LOOP = [
        # Grab first onion
        Direction.WEST,
        Direction.WEST,
        Direction.WEST,
        Action.INTERACT,

        # Place onion in pot
        Direction.EAST,
        Direction.NORTH,
        Action.INTERACT,

        # Grab second onion
        Direction.WEST,
        Action.INTERACT,

        # Place onion in pot
        Direction.EAST,
        Direction.NORTH,
        Action.INTERACT,

        # Grab third onion
        Direction.WEST,
        Action.INTERACT,

        # Place onion in pot
        Direction.EAST,
        Direction.NORTH,
        Action.INTERACT,

        # Cook soup
        Action.INTERACT,
        
        # Grab plate
        Direction.EAST,
        Direction.SOUTH,
        Action.INTERACT,
        Direction.WEST,
        Direction.NORTH,

        # Deliver soup
        Action.INTERACT,
        Direction.EAST,
        Direction.EAST,
        Direction.EAST,
        Action.INTERACT,
        Direction.WEST
    ]

    COOK_SOUP_COOP_LOOP = [
        # Grab first onion
        Direction.WEST,
        Direction.WEST,
        Direction.WEST,
        Action.INTERACT,

        # Place onion in pot
        Direction.EAST,
        Direction.SOUTH,
        Action.INTERACT,

        # Move to start so this loops
        Direction.EAST,
        Direction.EAST,

        # Pause to make cooperation more real time
        Action.STAY,
        Action.STAY,
        Action.STAY,
        Action.STAY,
        Action.STAY,
        Action.STAY,
        Action.STAY,
        Action.STAY,
        Action.STAY
    ]

    def __init__(self):
        self.curr_phase = -1
        self.curr_tick = -1

    def action(self, state):
        self.curr_tick += 1
        if self.curr_phase == 0:
            return self.COOK_SOUP_LOOP[self.curr_tick % len(self.COOK_SOUP_LOOP)], None
        elif self.curr_phase == 2:
            return self.COOK_SOUP_COOP_LOOP[self.curr_tick % len(self.COOK_SOUP_COOP_LOOP)], None
        return Action.STAY, None

    def reset(self):
        self.curr_tick = -1
        self.curr_phase += 1

    