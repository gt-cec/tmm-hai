import os
# Import and patch the production eventlet server if necessary
# if os.getenv('FLASK_ENV', 'production') == 'production':
    # import eventlet
    # eventlet.monkey_patch()

# All other imports must come after patch to ensure eventlet compatibility
import pickle, queue, atexit, json, logging, copy, datetime
from threading import Lock, Event
from env.server.utils import ThreadSafeSet, ThreadSafeDict
from flask import Flask, render_template, jsonify, request, send_file, send_from_directory
from flask_socketio import SocketIO, join_room, leave_room, emit, rooms
from env.server.game import OvercookedGame, Game
import env.server.game
import os
import ast

###########
# Globals #
###########

thread_event = Event()

smm = None
paused = False
pause_time = 0

# Read in global config
CONF_PATH = './env/server/config.json'
with open(CONF_PATH, 'r') as f:
    CONFIG = json.load(f)

LOGFILE = CONFIG['logfile']  # Where errors will be logged
LAYOUTS = CONFIG['layouts']  # Available layout names
LAYOUT_GLOBALS = CONFIG['layout_globals']  # Values that are standard across layouts
MAX_GAME_LENGTH = CONFIG['MAX_GAME_LENGTH']  # Maximum allowable game length (in seconds)
AGENT_DIR = CONFIG['AGENT_DIR']  # Path to where pre-trained agents will be stored on server
MAX_GAMES = CONFIG['MAX_GAMES']  # Maximum number of games that can run concurrently. Contrained by available memory and CPU
MAX_FPS = CONFIG['MAX_FPS']  # Frames per second cap for serving to client
PSITURK_CONFIG = json.dumps(CONFIG['psiturk'])  # Default configuration for psiturk experiment
TUTORIAL_CONFIG = json.dumps(CONFIG['tutorial'])  # Default configuration for tutorial
FREE_IDS = queue.Queue(maxsize=MAX_GAMES)  # Global queue of available IDs. This is how we sync game creation and keep track of how many games are in memory
FREE_MAP = ThreadSafeDict()  # Bitmap that indicates whether ID is currently in use. Game with ID=i is "freed" by setting FREE_MAP[i] = True

USER_ID = "user"

# Initialize our ID tracking data
for i in range(MAX_GAMES):
    FREE_IDS.put(i)
    FREE_MAP[i] = True

GAMES = ThreadSafeDict()  # Mapping of game-id to game objects
ACTIVE_GAMES = ThreadSafeSet()  # Set of games IDs that are currently being played
WAITING_GAMES = queue.Queue()  # Queue of games IDs that are waiting for additional players to join. Note that some of these IDs might be stale (i.e. if FREE_MAP[id] = True)
USERS = ThreadSafeDict()  # Mapping of users to locks associated with the ID. Enforces user-level serialization
USER_ROOMS = ThreadSafeDict()  # Mapping of user id's to the current game (room) they are in

GAME_TIME = 0
LAYOUT = "RSMM1"

# Mapping of string game names to corresponding classes
GAME_NAME_TO_CLS = {
    "overcooked" : OvercookedGame,
}

env.server.game._configure(MAX_GAME_LENGTH, AGENT_DIR, CONFIG["visibility"], CONFIG["visibility_range"])

#######################
# Flask Configuration #
#######################

# Create and configure flask app
app = Flask(__name__, template_folder=os.path.join('static', 'templates'))
app.config['DEBUG'] = os.getenv('FLASK_ENV', 'production') == 'development'
socketio = SocketIO(app, cors_allowed_origins="*", logger=app.config['DEBUG'])

# Attach handler for logging errors to file
handler = logging.FileHandler(LOGFILE)
handler.setLevel(logging.ERROR)  
app.logger.addHandler(handler)  

#################################
# Global Coordination Functions #
#################################

def timestamp():
    return int(datetime.datetime.timestamp(datetime.datetime.now()))

def try_create_game(game_name ,**kwargs):
    """
    Tries to create a brand new Game object based on parameters in `kwargs`
    
    Returns (Game, Error) that represent a pointer to a game object, and error that occured
    during creation, if any. In case of error, `Game` returned in None. In case of sucess, 
    `Error` returned is None

    Possible Errors:
        - Runtime error if server is at max game capacity
        - Propogate any error that occured in game __init__ function
    """

    # remove all previous games
    thread_event.clear()
    ids = [x for x in GAMES.keys()]
    for game_id in ids:
        # if game_id not in FREE_MAP:
            # GAMES[game_id].deactivate()
            # cleanup_game(GAMES[game_id])
        GAMES[game_id].status = Game.Status.DONE
        print("REMOVED GAME")

    # create the game
    try:
        curr_id = FREE_IDS.get(block=False)
        assert FREE_MAP[curr_id], "Current id is already in use"
        game_cls = GAME_NAME_TO_CLS.get(game_name, OvercookedGame)
        game = game_cls(id=curr_id, **kwargs)
    except queue.Empty:
        err = RuntimeError("Server at max capacity")
        return None, err
    except Exception as e:
        return None, e
    else:
        GAMES[game.id] = game
        FREE_MAP[game.id] = False
        return game, None

def cleanup_game(game):
    if FREE_MAP[game.id]:
        raise ValueError("Double free on a game")

    # User tracking
    for user_id in game.players:
        leave_curr_room(user_id)

    # Socketio tracking
    socketio.close_room(game.id)

    # Game tracking
    FREE_MAP[game.id] = True
    FREE_IDS.put(game.id)
    del GAMES[game.id]
    if game.id in ACTIVE_GAMES:
        ACTIVE_GAMES.remove(game.id)

def get_game(game_id):
    return GAMES.get(game_id, None)

def get_curr_game(user_id):
    return get_game(get_curr_room(user_id))

def get_curr_room(user_id):
    return USER_ROOMS.get(user_id, None)

def set_curr_room(user_id, room_id):
    USER_ROOMS[user_id] = room_id

def leave_curr_room(user_id):
    del USER_ROOMS[user_id]

def get_waiting_game():
    """
    Return a pointer to a waiting game, if one exists

    Note: The use of a queue ensures that no two threads will ever receive the same pointer, unless
    the waiting game's ID is re-added to the WAITING_GAMES queue
    """
    try:
        waiting_id = WAITING_GAMES.get(block=False)
        while FREE_MAP[waiting_id]:
            waiting_id = WAITING_GAMES.get(block=False)
    except queue.Empty:
        return None
    else:
        return get_game(waiting_id)


##########################
# Socket Handler Helpers #
##########################

def  _leave_game(user_id):
    """
    Removes `user_id` from it's current game, if it exists. Rebroadcast updated game state to all 
    other users in the relevant game. 

    Leaving an active game force-ends the game for all other users, if they exist

    Leaving a waiting game causes the garbage collection of game memory, if no other users are in the
    game after `user_id` is removed
    """
    # Get pointer to current game if it exists
    game = get_curr_game(user_id)

    if not game:
        # Cannot leave a game if not currently in one
        return False
    
    # Acquire this game's lock to ensure all global state updates are atomic
    with game.lock:
        # Update socket state maintained by socketio
        leave_room(game.id)

        # Update user data maintained by this app
        leave_curr_room(user_id)

        # Update game state maintained by game object
        if user_id in game.players:
            game.remove_player(user_id)
        else:
            game.remove_spectator(user_id)
        
        # Whether the game was active before the user left
        was_active = game.id in ACTIVE_GAMES

        # Rebroadcast data and handle cleanup based on the transition caused by leaving
        if was_active and game.is_empty():
            # Active -> Empty
            game.deactivate()
        elif game.is_empty():
            # Waiting -> Empty
            cleanup_game(game)
        elif not was_active:
            # Waiting -> Waiting
            emit('waiting', { "in_game" : True }, room="jack")
        elif was_active and game.is_ready():
            # Active -> Active
            pass
        elif was_active and not game.is_empty():
            # Active -> Waiting
            game.deactivate()
            
    return was_active

def _create_game(user_id, game_name, params={}, smm=None):
    global game_thread
    print("Socket Create Game")
    print("_create_game params", params)
    game, err = try_create_game(game_name, **params)
    if not game:
        socketio.emit("creation_failed", { "error" : err.__repr__() })
        return
    spectating = True
    with game.lock:
        if not game.is_full():
            spectating = False
            game.add_player(user_id)
        else:
            spectating = True
            game.add_spectator(user_id)
        join_room(game.id)
        set_curr_room(user_id, game.id)
        if game.is_ready():
            folder = os.path.join(os.getcwd(), "env/server/layouts")
            curr_layout = game.layouts.pop()
            # load the layout and use it to initialize the SMM
            with open(folder + "/" + curr_layout + ".layout", "r") as f:
                lines = f.read()
                smm.init_belief_state(ast.literal_eval(lines))
            game.activate(curr_layout=curr_layout, folder=folder)
            ACTIVE_GAMES.add(game.id)
            socketio.emit('start_game', { "spectating" : spectating, "start_info" : game.to_json()}, room="jack")
        else:
            WAITING_GAMES.put(game.id)
            socketio.emit('waiting', { "in_game" : True }, room="jack")

    thread_event.set()
    game_thread = socketio.start_background_task(play_game, game, smm=smm, fps=MAX_FPS)


#####################
# Debugging Helpers #
#####################

def _ensure_consistent_state():
    """
    Simple sanity checks of invariants on global state data

    Let ACTIVE be the set of all active game IDs, GAMES be the set of all existing
    game IDs, and WAITING be the set of all waiting (non-stale) game IDs. Note that
    a game could be in the WAITING_GAMES queue but no longer exist (indicated by 
    the FREE_MAP)

    - Intersection of WAITING and ACTIVE games must be empty set
    - Union of WAITING and ACTIVE must be equal to GAMES
    - id \in FREE_IDS => FREE_MAP[id] 
    - id \in ACTIVE_GAMES => Game in active state
    - id \in WAITING_GAMES => Game in inactive state
    """
    waiting_games = set()
    active_games = set()
    all_games = set(GAMES)

    for game_id in list(FREE_IDS.queue):
        assert FREE_MAP[game_id], "Freemap in inconsistent state"

    for game_id in list(WAITING_GAMES.queue):
        if not FREE_MAP[game_id]:
            waiting_games.add(game_id)

    for game_id in ACTIVE_GAMES:
        active_games.add(game_id)

    assert waiting_games.union(active_games) == all_games, "WAITING union ACTIVE != ALL"

    assert not waiting_games.intersection(active_games), "WAITING intersect ACTIVE != EMPTY"

    assert all([get_game(g_id)._is_active for g_id in active_games]), "Active ID in waiting state"
    assert all([not get_game(g_id)._id_active for g_id in waiting_games]), "Waiting ID in active state"


def get_agent_names():
    return [d for d in os.listdir(AGENT_DIR) if os.path.isdir(os.path.join(AGENT_DIR, d))]


######################
# Application routes #
######################

# Hitting each of these endpoints creates a brand new socket that is closed 
# at after the server response is received. Standard HTTP protocol

@app.route('/')
def index():
    # reset all global variables
    global paused, pause_time, GAMES, ACTIVE_GAMES, WAITING_GAMES, USERS, USER_ROOMS, GAME_TIME, LAYOUT, thread_event, FREE_IDS, FREE_MAP, USER_ID
    USER_ID = request.args.get("user_id")

    if USER_ID is None:
        return "Missing user ID, please reload this page with the user_id parameter"

    paused = False
    pause_time = 0
    thread_event = Event()
    GAMES = ThreadSafeDict()
    ACTIVE_GAMES = ThreadSafeSet()
    WAITING_GAMES = queue.Queue()
    USERS = ThreadSafeDict()
    USER_ROOMS = ThreadSafeDict()
    GAME_TIME = 0
    LAYOUT = "RSMM1"
    FREE_IDS = queue.Queue(maxsize=MAX_GAMES)  # Global queue of available IDs. This is how we sync game creation and keep track of how many games are in memory
    FREE_MAP = ThreadSafeDict()  # Bitmap that indicates whether ID is currently in use. Game with ID=i is "freed" by setting FREE_MAP[i] = True

    # Initialize our ID tracking data
    for i in range(MAX_GAMES):
        FREE_IDS.put(i)
        FREE_MAP[i] = True

    env.server.game._configure(MAX_GAME_LENGTH, AGENT_DIR, CONFIG["visibility"], CONFIG["visibility_range"])

    socketio.emit('end_game', { "status" : Game.Status.DONE }, room="jack")
    agent_names = get_agent_names()
    return render_template('index.html', agent_names=agent_names, layouts=LAYOUTS)

@app.route('/consent-form')
def download_consent_form():
    print("Downloading consent form")
    return send_file("static/pdf/Consent Form.pdf")

@app.route('/log', methods=["POST"])
def log():
    with open("env/server/logs/" + USER_ID + ".txt", "a") as f:
        f.write(str(request.get_json()) + "\n")
    return ""

@app.route("/level", methods=["POST"])
def set_level():
    global LAYOUT, GAME_TIME
    level = request.get_json()
    if "level" in level:
        level = level["level"]

    if level == "intro":
        LAYOUT = "RSMM1"
        GAME_TIME = 60
    elif level == "practice":
        LAYOUT = "RSMM2"
        GAME_TIME = 93
    elif level == "round1":
        LAYOUT = "RSMM3"
        GAME_TIME = 93
    elif level == "round2":
        LAYOUT = "RSMM4"
        GAME_TIME = 93
    elif level == "round3":
        LAYOUT = "RSMM5"
        GAME_TIME = 93
    elif level == "round4":
        LAYOUT = "RSMM6"
        GAME_TIME = 93
        
    print("Setting level to", level, LAYOUT)
        
    return jsonify({"layout": LAYOUT})

@app.route('/debug')
def debug():
    resp = {}
    games = []
    active_games = []
    waiting_games = []
    users = []
    free_ids = []
    free_map = {}
    for game_id in ACTIVE_GAMES:
        game = get_game(game_id)
        active_games.append({"id" : game_id, "state" : game.to_json()})
    for game_id in list(WAITING_GAMES.queue):
        game = get_game(game_id)
        game_state = None if FREE_MAP[game_id] else game.to_json()
        waiting_games.append({ "id" : game_id, "state" : game_state})
    for game_id in GAMES:
        games.append(game_id)
    for user_id in USER_ROOMS:
        users.append({ user_id : get_curr_room(user_id) })
    for game_id in list(FREE_IDS.queue):
        free_ids.append(game_id)
    for game_id in FREE_MAP:
        free_map[game_id] = FREE_MAP[game_id]
    resp['active_games'] = active_games
    resp['waiting_games'] = waiting_games
    resp['all_games'] = games
    resp['users'] = users
    resp['free_ids'] = free_ids
    resp['free_map'] = free_map
    return jsonify(resp)

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')


#########################
# Socket Event Handlers #
#########################

@socketio.on('create')
def on_create(data):
    print("Creating Game!")
    user_id = request.sid
    with USERS[user_id]:
        # Retrieve current game if one exists
        curr_game = get_curr_game(user_id)
        if curr_game:
            # Cannot create if currently in a game
            return
        params = data.get('params', {})
        #hardcoded since there is no input for toggling this flag
        #defnitely want to change this in the future
        params["mdp_params"] = {"old_dynamics":True}
        params["layout"] = LAYOUT + ".layout"
        params["layouts"] = [LAYOUT]
        print("    game layout to " + LAYOUT + ".layout")
        params["gameTime"] = str(GAME_TIME)
        print("Params", params)
        game_name = data.get('game_name', 'overcooked')
        _create_game(user_id, game_name, params, smm=smm)
    
@socketio.on('join')
def on_join(data):
    user_id = request.sid
    with USERS[user_id]:
        create_if_not_found = data.get("create_if_not_found", True)
        # Retrieve current game if one exists
        curr_game = get_curr_game(user_id)
        if curr_game:
            # Cannot join if currently in a game
            return
        # Retrieve a currently open game if one exists
        game = get_waiting_game()
        if not game and create_if_not_found:
            # No available game was found so create a game
            params = data.get('params', {})
            game_name = data.get('game_name', 'overcooked')
            _create_game(user_id, game_name, params)
            return
        elif not game:
            # No available game was found so start waiting to join one
            socketio.emit('waiting', { "in_game" : False })
        else:
            # Game was found so join it
            with game.lock:
                join_room(game.id)
                set_curr_room(user_id, game.id)
                game.add_player(user_id)
                if game.is_ready():
                    # Game is ready to begin play
                    game.activate()
                    ACTIVE_GAMES.add(game.id)
                    socketio.emit('start_game', { "spectating" : False, "start_info" : game.to_json()}, room="jack")
                    thread_event.set()
                    global game_thread
                    game_thread = socketio.start_background_task(play_game, game)
                else:
                    # Still need to keep waiting for players
                    WAITING_GAMES.put(game.id)
                    socketio.emit('waiting', { "in_game" : True }, room="jack")

@socketio.on('leave')
def on_leave(data):
    user_id = request.sid
    with USERS[user_id]:
        was_active = _leave_game(user_id)
        if was_active:
            socketio.emit('end_game', { "status" : Game.Status.DONE, "data" : {}})
        else:
            socketio.emit('end_lobby')

@socketio.on('pause')
def on_pause(data):
    global paused
    paused = bool(data)
    return

@socketio.on('action')
def on_action(data):
    user_id = request.sid
    action = data['action']
    game = get_curr_game(user_id)
    if not game:
        return
    game.enqueue_action(user_id, action)

@socketio.on('connect')
def on_connect():
    user_id = request.sid
    if user_id in USERS:
        return
    USERS[user_id] = Lock()
    join_room("jack")

@socketio.on('disconnect')
def on_disconnect():
    # Ensure game data is properly cleaned-up in case of unexpected disconnect
    user_id = request.sid
    if user_id not in USERS:
        return
    with USERS[user_id]:
        _leave_game(user_id)
    del USERS[user_id]

# Exit handler for server
def on_exit():
    # Force-terminate all games on server termination
    for game_id in GAMES:
        socketio.emit('end_game', { "status" : Game.Status.INACTIVE, "data" : get_game(game_id).get_data() }, room="jack")


#############
# Game Loop #
#############

def play_game(game, smm=None, fps=10):
    """
    Asynchronously apply real-time game updates and broadcast state to all clients currently active
    in the game. Note that this loop must be initiated by a parallel thread for each active game

    game (Game object):     Stores relevant game state. Note that the game id is the same as to socketio
                            room id for all clients connected to this game
    fps (int):              Number of game ticks that should happen every second
    """
    global pause_time
    status = Game.Status.ACTIVE
    old_state = {}
    count = 0
    while status != Game.Status.DONE and status != Game.Status.INACTIVE and thread_event.is_set():
        # hold if paused
        if paused:
            # if just paused, record the pause time
            if pause_time == 0:
                pause_time = timestamp()
            socketio.sleep(1/fps)
            continue
        # if just unpaused, add to time remaining
        if pause_time != 0:
            game.start_time += timestamp() - pause_time
            pause_time = 0
        # cycle a tick
        count += 1
        with game.lock:
            status = game.tick()
        if status == Game.Status.RESET:
            print("play game but game is in RESET state")
            with game.lock:
                data = game.get_data()
            socketio.emit('reset_game', { "state" : game.to_json(), "timeout" : game.reset_timeout, "data" : data}, room="jack")
            socketio.sleep(game.reset_timeout/1000)
        else:
            state = game.get_state()
            # log the state
            with open("env/server/logs/" + USER_ID + ".txt", "a") as f:
                f.write(str(state) + "\n")
            
            # send the game state to the SMM engine, disabled because not running in real time
            # if smm is not None:
            #     smm.update({k : state[k] for k in state if k not in ["all_orders"]})
            
            # convert position tuples to strings for nicer formatting, check 3 layers deep
            belief_state = copy.deepcopy(smm.belief_state if smm is not None else {})
            for item in belief_state:
                if isinstance(belief_state[item], tuple):
                    belief_state[item] = str(belief_state[item])
                if isinstance(belief_state[item], dict):
                    for prop in belief_state[item]:
                        if isinstance(belief_state[item][prop], tuple):
                            belief_state[item][prop] = str(belief_state[item][prop])
                        if isinstance(belief_state[item][prop], dict):
                            for subprop in belief_state[item][prop]:
                                if isinstance(belief_state[item][prop][subprop], tuple):
                                    belief_state[item][prop][subprop] = str(belief_state[item][prop][subprop])
            socketio.emit('state_pong', { "state" : state, "smm" : belief_state }, room="jack")
        socketio.sleep(1/fps)
    
    print("End game")
    thread_event.clear()
    with game.lock:
        data = game.get_data()
        socketio.emit('end_game', { "status" : status, "data" : data }, room="jack")

        if status != Game.Status.INACTIVE:
            game.deactivate()
        cleanup_game(game)

def run(_smm=None):
    # set the shared mental model
    if _smm is not None:
        global smm
        smm = _smm

    # Dynamically parse host and port from environment variables (set by docker build)
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 5000))

    # Attach exit handler to ensure graceful shutdown
    atexit.register(on_exit)

    # https://localhost:80 is external facing address regardless of build environment
    print("Ready to Play!")
    socketio.run(app, host=host, port=port)