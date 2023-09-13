// Persistent network connection that will be used to transmit real-time data
var socket = io()

$(document).ready(function(){
    // sending a connect request to the server.
    socket = io.connect('http://localhost:5000');
});

$(window).on('beforeunload', function(){
    socket.close();
});

/* * * * * * * * * * * * * * * * 
 * Button click event handlers *
 * * * * * * * * * * * * * * * */

var paused = false

function startGame(layout) {
    if (paused) {
        document.getElementById("create").style.display = "none";
        document.getElementById("create").setAttribute("disabled", true);
    }
    else {
        const formData = new FormData(document.getElementById("environment-configure-form"));
        let data = [];

        formData.forEach((value, name) => {
            data.push({ name, value });
        });

        params = arrToJSON(data)
        params.layouts = [params.layout]
        params.layout = layout
        paramsData = {
            "params" : params,
            "game_name" : "overcooked",
            "create_if_not_found" : false
        };
        socket.emit("create", paramsData)
        
        // set a timer for showing the questions
        window.setTimeout(() => {

        }, 5000)
    }
}

/* * * * * * * * * * * * * 
 * Socket event handlers *
 * * * * * * * * * * * * */

window.intervalID = -1;
window.spectating = true;

socket.on('waiting', function(data) {
    // Show game lobby
    $('#error-exit').hide();
    $('#game-over').hide();
    $('#tutorial').hide();
    $("#overcooked").empty();
    $('#join').hide();
    $('#join').attr("disabled", true)
    $('#create').hide();
    $('#create').attr("disabled", true)
    $('#leave').show();
    $('#leave').attr("disabled", false);
    if (!data.in_game) {
        // Begin pinging to join if not currently in a game
        if (window.intervalID === -1) {
            window.intervalID = setInterval(function() {
                socket.emit('join', {});
            }, 1000);
        }
    }
});

socket.on('creation_failed', function(data) {
    // Tell user what went wrong
    let err = data['error']
    $("#overcooked").empty();
    $('#tutorial').show();
    $('#join').show();
    $('#join').attr("disabled", false);
    $('#create').show();
    $('#create').attr("disabled", false);
    $('#overcooked').append(`<h4>Sorry, game creation code failed with error: ${JSON.stringify(err)}</>`);
});

socket.on('start_game', function(data) {
    // Hide game-over and lobby, show game title header
    if (window.intervalID !== -1) {
        clearInterval(window.intervalID);
        window.intervalID = -1;
    }
    graphics_config = {
        container_id : "overcooked",
        start_info : data.start_info
    };
    window.spectating = data.spectating;
    $('#error-exit').hide();
    $("#overcooked").empty();
    $('#game-over').hide();
    $('#join').hide();
    $('#join').attr("disabled", true);
    $('#create').hide();
    $('#create').attr("disabled", true)
    $('#tutorial').hide();
    $('#leave').show();
    $('#leave').attr("disabled", false)
    $('#game-title').show();
    
    if (!window.spectating) {
        enable_key_listener();
    }
    
    graphics_start(graphics_config);
});

socket.on('reset_game', function(data) {
    graphics_end();
    if (!window.spectating) {
        disable_key_listener();
    }
    
    $("#overcooked").empty();
    $("#reset-game").show();
    setTimeout(function() {
        $("reset-game").hide();
        graphics_config = {
            container_id : "overcooked",
            start_info : data.state
        };
        if (!window.spectating) {
            enable_key_listener();
        }
        graphics_start(graphics_config);
    }, data.timeout);
});


socket.on('state_pong', function(data) {
    drawState(data['state']);  // Draw state update
    displaySMM(data['smm'])  // update the SMM
});

function displaySMM(smm) {
    // format the SMM dictionary onto the browser panel
    let s = JSON.stringify(smm, null, 4).replace(/[{},'"[\]]/g, '').replace(/(^[ \t]*\n)/gm, "").replace(/^(    +)/gm, (match, tabs) => tabs.replace(/    /, ''))
    document.getElementById("smm-content").innerHTML = "<b>- Mental Model -</b>" + "<pre>" + s + "</pre>";
}

socket.on('end_game', function(data) {
    // Hide game data and display game-over html
    graphics_end();
    if (!window.spectating) {
        disable_key_listener();
    }
    $('#game-title').hide();
    $('#game-over').show();
    $("#join").show();
    $('#join').attr("disabled", false);
    $("#create").show();
    $('#create').attr("disabled", false)
    $('#tutorial').show();
    $("#leave").hide();
    $('#leave').attr("disabled", true)
    
    // Game ended unexpectedly
    if (data.status === 'inactive') {
        $('#error-exit').show();
    }
    
    // move on to the next stage
    endStage()
});

socket.on('end_lobby', function() {
    // Hide lobby
    $("#join").show();
    $('#join').attr("disabled", false);
    $("#create").show();
    $('#create').attr("disabled", false)
    $("#leave").hide();
    $('#leave').attr("disabled", true)
    $('#tutorial').show();

    // Stop trying to join
    clearInterval(window.intervalID);
    window.intervalID = -1;
})


/* * * * * * * * * * * * * * 
 * Game Key Event Listener *
 * * * * * * * * * * * * * */

function enable_key_listener() {
    $(document).on('keydown', function(e) {
        let action = 'STAY'
        switch (e.which) {
            case 37: // left
                action = 'LEFT';
                break;

            case 38: // up
                action = 'UP';
                break;

            case 39: // right
                action = 'RIGHT';
                break;

            case 40: // down
                action = 'DOWN';
                break;

            case 32: //space
                action = 'SPACE';
                break;

            default: // exit this handler for other keys
                return; 
        }
        e.preventDefault();
        socket.emit('action', { 'action' : action });
    });
};

function disable_key_listener() {
    $(document).off('keydown');
};

function pause(val) {
    paused = val
    socket.emit('pause', val)
}

/* * * * * * * * * * *
 * Utility Functions *
 * * * * * * * * * * */

var arrToJSON = function(arr) {
    let retval = {}
    for (let i = 0; i < arr.length; i++) {
        elem = arr[i];
        key = elem['name'];
        value = elem['value'];
        retval[key] = value;
    }
    return retval;
};

/* * * * * * * * * * * * *
 *  User Study Functions *
 * * * * * * * * * * * * */

async function setStudyStage(s, indicator="") {
    studyStage = s;
    studyStages.forEach ((i) => {
        s = s.startsWith("practice") ? "practice" : s
        s = s.startsWith("intro") ? "intro" : s
        document.getElementById("stage-" + i).className = i == s ? "study-stage study-stage-active" : "study-stage"
    })

    // update the server's level
    let resp = await fetch('/level', {
        method: 'POST',
        headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({"level": s})
    })
    let data = await resp.json()
    let layout = data["layout"]

    // activate/deactivate UI elements depending on the study stage
    if (studyStage == "intro-text") {
        showInstructions()
        // fill the instructions content
        showIntroductionText()
    }
    if (["intro", "practice", "round1", "round2", "round3", "round4"].includes(studyStage)) {
        showOvercooked()
    }
    return layout + ".layout"
}

// show the overcooked div
function showOvercooked() {
    // enable the overcooked div
    document.getElementById("overcooked").style.display = "flex";
    // disable the instructions content div
    document.getElementById("instructions-content").style.display = "none";
    // disable the instructions continue button
    document.getElementById("instructions-continue").style.display = "none";
    // enable the right side instructions panel
    document.getElementById("right-panel-instructions").style.display = "flex"
}

// show the instructions div
function showInstructions(text = "") {
    // hide the demographic divs
    hideDemographics()
    // disable the overcooked div
    document.getElementById("overcooked").style.display = "none";
    // disable the right side instructions panel
    document.getElementById("right-panel-instructions").style.display = "none"
    // enable the instructions content div
    document.getElementById("instructions-content").style.display = "flex";
    document.getElementById("instructions-content").setAttribute("class", "instructions-content")
    // enable the instructions continue div
    document.getElementById("instructions-continue").style.display = "flex";
    // set the instructions text
    if (text != "") {
        document.getElementById("instructions-content-text-top").innerHTML = text
    }
}

// move on the next stage
function endStage() {
    // after the intro stage, give a 20 second break
    if (studyStage == "intro") {
        // show the instructions
        showInstructions("Well done! Let's do one more practice, try to cook all the soups before time runs out. This time, you will be asked a few questions every 30 seconds.")
        setInstructionsButtonToContinue(undefined, () => {previewRound("preview_kitchen_practice.png", "practice")}, 1)
        return
    }

    // after the practice stage, give a 20 second break
    if (studyStage == "practice") {
        // show the instructions
        showInstructions("Great! You are ready for the real deal. Let's take a few seconds break and then start the first round!")
        setInstructionsButtonToContinue(undefined, () => {previewRound("preview_kitchen_round1.png", "round1")}, 1)
        return
    }

    // after the round1 stage, give a 20 second break
    if (studyStage == "round1") {
        // show the instructions
        showInstructions("Nice work! Let's take a 30 second break before starting the next round.")
        setInstructionsButtonToContinue(undefined, () => {previewRound("preview_kitchen_round2.png", "round2")}, 1)
        return
    }

    // after the round2 stage, give a 20 second break
    if (studyStage == "round2") {
        // show the instructions
        showInstructions("Nice work! Let's take a 30 second break before starting the next round.")
        setInstructionsButtonToContinue(undefined, () => {previewRound("preview_kitchen_round2.png", "round3")}, 1)
        return
    }

    // after the round3 stage, give a 20 second break
    if (studyStage == "round3") {
        // show the instructions
        showInstructions("Nice work! Let's take a 30 second break before starting the next round.")
        setInstructionsButtonToContinue(undefined, () => {previewRound("preview_kitchen_round2.png", "round4")}, 1)
        return
    }

    // after the round4 stage, end the study
    if (studyStage == "round4") {
        // show the instructions
        showInstructions("Nice work! You have completed the study!")
        setInstructionsButtonToContinue(undefined, () => {previewRound("preview_kitchen_round2.png", "round2")}, 1)
        return
    }
}

// record a demographic button press
function recordDemographic(obj) {
    resetButtons(obj)
    // log the selection
    log({"type":"demographics", "selection":obj.id})
}

// record a screening button press
function recordScreening(obj) {
    resetButtons(obj)
    // record the screening value
    if (obj.id.startsWith("screening-location"))
        screeningLocation = obj.innerHTML
    else if (obj.id.startsWith("screening-age"))
        screeningAge = obj.innerHTML
    else if (obj.id.startsWith("screening-vulnerable"))
        screeningVulnerable = obj.innerHTML
    // log the selection
    log({"type":"screening", "selection":obj.id, "value": obj.innerHTML})
}

// reset the object's button background color
function resetButtons(obj) {
    // set the background color
    let children = obj.parentElement.childNodes    
    obj.style.backgroundColor = "lightgreen"
    for (var i in children) {
        if (children[i].id == obj.id) {
            console.log(i, children)
            children[i].style.backgroundcolor = "lightgreen"
        }
        else if (children[i].className == "demographics-button") {
            children[i].style.backgroundColor = "lightblue"
        }
    }
}

// show the welcome text
function showIntroductionText() {
    showInstructions("Welcome to our study!<br><br>In this game you are a restaurant chef trying to cook vegetable soups.<br><br>Your goal is to use the ingredients at your disposal to create as many soups as you can within three minutes. If you are familiar with the game Overcooked, this is very similar.<br><br>You have an AI partner that is trying to help you, however they are not very considerate. We need your help to improve the AI's helpfulness!")
    setInstructionsButtonToContinue(undefined, showInstructions3Text /*showInstructions1Text*/, 1)
}

// show the game instructions "This is your chef"
function showInstructions1Text() {
    showInstructions("This is your chef:<br><br><img height='150rem' src='static/images/chef.png'/><br>To play the game, control your chef with the arrow keys or WASD keys.<br><br><img height='200rem' src='static/images/controls.png'/><br>")
    setInstructionsButtonToContinue(showIntroductionText, showInstructions2Text, 1)
}

// show the game instructions "How to make a soup"
function showInstructions2Text() {
    showInstructions("Your goal is to cook as many soups as you can! Onions and tomatoes are placed around the kitchen, use them to make soups:<br><br><img width='100%' src='static/images/cooking_instructions.png'/><br><br>Try to cook all the available ingredients!<br><br>If you accidentally pick up an object, you can set it down on an empty counter.")
    setInstructionsButtonToContinue(showInstructions1Text, showResearchText, 1)
}

// show the research overview
function showResearchText() {
    showInstructions("As you play the game, the study will pause to ask you questions such as where you think kitchen objects are located.<br><br>On our end, we will use your responses to make the AI agent (and real-life robots) better able to assist people with household tasks.<br><br>We hope you enjoy this study :-)<br><br>- Jack")
    setInstructionsButtonToContinue(showInstructions2Text, showConsent, 1)
}

// consent
function showConsent() {
    showInstructions("Please review the consent form. If you consent to the study, please enter your name in the text box. If not, you can close this tab and return the study.")
    document.getElementById("consent-input").value = ""
    document.getElementById("consent-form").style.display = "flex"
    setInstructionsButtonToContinue(showResearchText, () => {
        // check if a name was given
        if (document.getElementById("consent-input").value != "") {
            showScreeningInfo();
        }
        else {
            alert("If you consent to the study, please enter your name in the text field!")
        }
    }, 1)
}

// screening: initial info
function showScreeningInfo() {
    showInstructions("Let's start with a few screening questions to determine if you are eligible for this study.")
    setInstructionsButtonToContinue(showConsent, showScreeningAge, 1)
}

// screening: age
function showScreeningAge() {
    showInstructions("What is your age?")
    document.getElementById("screening-age-input").value = 1
    document.getElementById("screening-age").style.display = "flex"
    setInstructionsButtonToContinue(showScreeningInfo, () => {
        // if a valid age, show the location screening, otherwise exit
        if (!isNaN(document.getElementById("screening-age-input").value) && document.getElementById("screening-age-input").value >= 18) {
            showScreeningLocation();
        }
        else {
            showScreeningExit();
        }
    }, 1)
}

// screening: check location
function showScreeningLocation() {
    showInstructions("Where are you located?")
    document.getElementById("screening-location").style.display = "flex"
    setInstructionsButtonToContinue(showScreeningAge, () => {
        // if a valid location, show the protected group screening, otherwise exit
        if (screeningLocation == "USA") {
            showScreeningVulnerable();
        }
        else {
            showScreeningExit();
        }
    }, 1)
}

// screening: check vulnerable group
function showScreeningVulnerable() {
    showInstructions("Are you part of a vulnerable group or are otherwise unable to provide consent for a research study? Vulnerable groups include prisoners, mentally disabled persons, and economically or educationally disadvantaged persons.")
    document.getElementById("screening-vulnerable").style.display = "flex"
    setInstructionsButtonToContinue(showScreeningLocation, () => {
        // if a valid location, show the protected group screening, otherwise exit
        if (screeningVulnerable != "Yes") {
            showDemographicsIntro();
        }
        else {
            showScreeningExit();
        }
    }, 1)
}

// demographics: intro
function showDemographicsIntro() {
    showInstructions("Great! You are eligible for our study. Next we will ask a few demographics questions.")
    hideDemographics()
    setInstructionsButtonToContinue(showScreeningVulnerable, showDemographics1Text, 1)
}

// demographics: gender
function showDemographics1Text() {
    showInstructions("What is your gender?")
    hideDemographics()
    document.getElementById("demographics-gender").style.display = "flex"
    setInstructionsButtonToContinue(showDemographicsIntro, showDemographicsGamingText, 1)
}

// hide all demographic info
function hideDemographics() {
    document.getElementById("consent-form").style.display = "none"
    document.getElementById("screening-age").style.display = "none"
    document.getElementById("screening-location").style.display = "none"
    document.getElementById("screening-vulnerable").style.display = "none"
    document.getElementById("demographics-gender").style.display = "none"
    document.getElementById("demographics-gaming").style.display = "none"
}

// screening: exit on invalid
function showScreeningExit() {
    // should send a ping to Prolific that this user has been returned
    showInstructions("We are sorry, but your responses make you ineligible for this study. Thank you for your participation, you can close this tab and return the task.")
    hideDemographics()
    // disable the instructions continue button
    document.getElementById("instructions-continue").style.display = "none";
}

// demographics: experience
function showDemographicsGamingText() {
    showInstructions("What is your experience with fast-paced team coordination video games, for example, Overcooked, League of Legends, Black Ops?")
    document.getElementById("demographics-gaming").style.display = "flex"
    setInstructionsButtonToContinue(showDemographics1Text, showInstructions3Text, 1)
}

// show the game instructions "Let's try a practice round"
function showInstructions3Text() {
    showInstructions("Let's try a practice round! Press 'Continue', take a moment to take in the environment, and then press 'Play'.")
    setInstructionsButtonToContinue(showDemographicsGamingText, () => {previewRound("preview_kitchen_practice.png", "intro")}, 1)
}

function setInstructionsButtonToPlay(nextStep) {
    document.getElementById("instructions-continue-text").innerHTML = "Play"
    document.getElementById("instructions-continue").setAttribute("class", "instructions-play")
    document.getElementById("instructions-continue").onclick = nextStep
    document.getElementById("instructions-continue-bar").style.backgroundColor = "green"
    hideDemographics()
    // init the loading bar
    setInstructionsButtonLoading(1, () => { 
        document.getElementById("instructions-continue").onclick = nextStep
    })   
}

function setInstructionsButtonToContinue(prevStep, nextStep, loadingDuration) {
    document.getElementById("instructions-continue-text").innerHTML = "Continue"
    document.getElementById("instructions-continue").setAttribute("class", "instructions-continue")
    document.getElementById("instructions-continue-bar").style.backgroundColor = "blue"
    // init the loading bar
    setInstructionsButtonLoading(loadingDuration, () => { 
        document.getElementById("instructions-continue").onclick = nextStep
    })
    // set up the back button
    if (prevStep != undefined) {
        document.getElementById("instructions-back").style.display = "flex"
        document.getElementById("instructions-back").onclick = prevStep
    } else {
        document.getElementById("instructions-back").style.display = "none"
    }
}

function setInstructionsButtonLoading(timeout, after) {
    framerate = 30
    initTime = new Date().getTime()
    timeout *= 1000
    document.getElementById("instructions-continue").style.backgroundColor = "lightgrey"
    document.getElementById("instructions-continue").onclick = () => {}
    const loading = window.setInterval(() => {
        current = 100 * (new Date().getTime() - initTime) / timeout
        document.getElementById("instructions-continue-bar").style.width = (current) + "%"
        if (current >= 100) {
            document.getElementById("instructions-continue").style.backgroundColor = ""
            window.clearInterval(loading)
            after()
        }
    }, 1 / framerate)
}

// show the round's initial game state
function previewRound(img, stage) {
    // enable the right side instructions panel
    document.getElementById("right-panel-instructions").style.display = "flex"
    // free the instructions content's class
    document.getElementById("instructions-content").setAttribute("class", "")
    // set the game image to show
    document.getElementById("instructions-content-text-top").innerHTML = "<img src='static/images/" + img + "' width=800px, height=500px />"
    setInstructionsButtonToPlay(async () => {
        let layout = await setStudyStage(stage)
        startGame(layout)  // setStudyStage returns the layout, startGame starts the game
    })
}