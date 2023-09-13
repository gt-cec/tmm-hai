// Persistent network connection that will be used to transmit real-time data
var socket = io()

$(document).ready(function(){
    // sending a connect request to the server.
    socket = io.connect('https://2d16-130-207-94-34.ngrok-free.app');
});

$(window).on('beforeunload', function(){
    socket.close();
});

/* * * * * * * * * * * * * * * * 
 * Button click event handlers *
 * * * * * * * * * * * * * * * */

function startGame(layout) {
    if (paused) {
        document.getElementById("create").style.display = "none";
        document.getElementById("create").setAttribute("disabled", true);
    }
    else {
        const formData = new FormData(document.getElementById("environment-configure-form"));
        let data = [];

        formData.forEach((value, name) => {
            data.push({ name, value })
        })

        params = arrToJSON(data)
        params.layouts = [params.layout]
        params.layout = layout
        paramsData = {
            "params" : params,
            "game_name" : "overcooked",
            "create_if_not_found" : false
        };
        socket.emit("create", paramsData)   
        // starts the in-situ question timeout if not on the intro stage
        if (studyStage != "intro") {
            startInSituQuestionTimeout()            
        }     
    }
}

function startInSituQuestionTimeout() {
    // set a timer for showing the questions
    questionTimeout = window.setTimeout(() => {
        pause(true)
        showInSituQuestions()
    }, 1000 * 30)
}

function setInSituButtonLoading(timeout, after) {
    framerate = 30
    initTime = new Date().getTime()
    timeout *= 1000
    document.getElementById("insitu-submit").style.backgroundColor = "lightgrey"
    document.getElementById("insitu-submit-bar").style.backgroundColor = "green"
    document.getElementById("insitu-submit").onclick = () => {}
    const loading = window.setInterval(() => {
        current = 100 * (new Date().getTime() - initTime) / timeout
        document.getElementById("insitu-submit-bar").style.width = (current) + "%"
        if (current >= 100) {
            document.getElementById("insitu-submit").style.backgroundColor = ""
            window.clearInterval(loading)
            after()
        }
    }, 1 / framerate)
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
    paused = false // unpause in case the game is already paused

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
        // ignore if paused
        if (paused) {
            return
        }
        let action = 'STAY'
        switch (e.which) {
            case 37: // left
            case 65:
                action = 'LEFT';
                break;

            case 38: // up
            case 87:
                action = 'UP';
                break;

            case 39: // right
            case 68:
                action = 'RIGHT';
                break;

            case 40: // down
            case 83:
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

function setFullscreen() {
    if (!document.fullscreenElement) {
        document.getElementsByTagName("html")[0].requestFullscreen()
    }
}

function highlightStudyStage(s) {
    studyStages.forEach ((i) => {
        s = s.startsWith("practice") ? "practice" : s
        s = s.startsWith("intro") ? "intro" : s
        document.getElementById("stage-" + i).className = i == s ? "study-stage study-stage-active" : "study-stage"
    })
}

async function setStudyStage(s, indicator="") {
    studyStage = s;
    highlightStudyStage(s)

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
    log({"type": "show overcooked"})
    // enable the overcooked div
    document.getElementById("overcooked").style.display = "flex"
    // disable the instructions content div
    document.getElementById("instructions-content").style.display = "none"
    // disable the instructions continue button
    hideInstructionsButtons()
    // enable the side panels
    document.getElementById("right-panel-instructions").style.display = "flex"
    document.getElementById("left-panel-controls").style.display = "flex"
}

// show the instructions div
function showInstructions(text = "") {
    log({"type": "show instructions"})
    setFullscreen()
    // hide the demographic divs
    hideDemographics()
    // disable the overcooked div
    document.getElementById("overcooked").style.display = "none"
    // disable the right side instructions panel
    document.getElementById("right-panel-instructions").style.display = "none"
    document.getElementById("left-panel-controls").style.display = "none"
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
    log({"type": "end stage"})
    // cancel the SA question timeout
    if (questionTimeout != undefined) {
        clearTimeout(questionTimeout)
    }    

    // hide the in situ questions
    hideInSituQuestions()
    askedQuestions = []

    // update the study stage
    studyStage = studyStages[studyStages.indexOf(studyStage)+1]

    // set the cookie for the stage ending
    setCookie("lastStage", studyStage, 30)

    // introduce the next stage
    introduceStage()
}

// show instructions to introduce a stage
function introduceStage() { 
    log({"type": "introduce stage"})
    highlightStudyStage(studyStage)

    // if device is mobile or tablet, exit
    if (window.mobileAndTabletCheck()) {
        showInstructions("Hi! We would love for you to participate in our study, but it looks like you are using a phone or tablet. This study requires a laptop or desktop computer -- you can click below to return to Prolific without penalty.")
        setInstructionsButtonToContinue(undefined, () => {window.location = "https://app.prolific.com/submissions/complete?cc=CTUREFP5"}, 1)
        document.getElementById("instructions-continue-text").innerHTML = "End Study"
    }

    // the beginning of the study
    if (studyStage == "intro-text") {
        showIntroductionText()
    }   

    // after the intro stage, give a 20 second break
    if (studyStage == "practice") {
        // show the instructions
        showInstructions("Well done! Let's do one more practice, try to cook all the soups before time runs out. This time, you will be asked a few questions every 30 seconds. Press \"Continue\", take in in the environment, and then \"Play\"")
        setInstructionsButtonToContinue(undefined, () => {previewRound("preview_kitchen_practice2.png", "practice")}, 1)
        return
    }

    // after the practice stage, give a 20 second break
    if (studyStage == "round1") {
        // show the instructions
        showInstructions("Great! You are ready for the real deal. Press \"Continue\", take in the environment, and go for it.")
        setInstructionsButtonToContinue(undefined, () => {previewRound("preview_kitchen_round1.png", "round1")}, 5)
        return
    }

    // after the round1 stage, give a 20 second break
    if (studyStage == "round2") {
        // show the instructions
        showInstructions("Nice work! Let's pause a few seconds before starting the second round.")
        setInstructionsButtonToContinue(undefined, () => {previewRound("preview_kitchen_round2.png", "round2")}, 5)
        return
    }

    // after the round2 stage, give a 20 second break
    if (studyStage == "round3") {
        // show the instructions
        showInstructions("You are halfway done! We will pause for a few seconds before starting the next round.")
        setInstructionsButtonToContinue(undefined, () => {previewRound("preview_kitchen_round3.png", "round3")}, 5)
        return
    }

    // after the round3 stage, give a 20 second break
    if (studyStage == "round4") {
        // show the instructions
        showInstructions("Just one more, you got this! Take some deep breaths to relax.")
        setInstructionsButtonToContinue(undefined, () => {previewRound("preview_kitchen_round4.png", "round4")}, 5)
        return
    }

    // after the round4 stage, end the study
    if (studyStage == "debrief") {
        // show the instructions
        showInstructions("And that's all! You have completed our study, thank you so much for your participation! We will be using your responses as a dataset to help robots better predict how people perceive your surroundings.<br><br>Thank you again, and please email me at <b>kolb@gatech.edu</b> if you have any questions or experienced issues with this study.<br><br>Also, if you would like to be sent the research papers we plan to publish from this data, let me know :-)<br><br>Click \"End Study\" to return to Prolific.")
        // set the instruction button to return back to Prolific
        setInstructionsButtonToContinue(undefined, () => {window.location = "https://app.prolific.com/submissions/complete?cc=C105IU9F"}, 1)
        document.getElementById("instructions-continue-text").innerHTML = "End Study"
        return
    }
}

// record a demographic button press
function recordDemographic(obj) {
    resetButtons(obj)
    // log the selection
    log({"type":"demographics", "selection": obj.id, "value": obj.innerHTML})
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
    log({"type": "screening", "selection": obj.id, "value": obj.innerHTML})
}

// reset the object's button background color
function resetButtons(obj) {
    // set the background color
    let children = obj.parentElement.childNodes    
    obj.style.backgroundColor = "lightgreen"
    for (var i in children) {
        if (children[i].id == obj.id) {
            children[i].style.backgroundcolor = "lightgreen"
        }
        else if (children[i].className == "demographics-button") {
            children[i].style.backgroundColor = "lightblue"
        }
    }
}

// show the welcome text
function showIntroductionText() {
    showInstructions("Welcome to our study!<br><br>In this game you are a restaurant chef trying to cook vegetable soups.<br><br>Your goal is to use the ingredients at your disposal to cook as many soups as you can within three minutes. If you are familiar with the game Overcooked, this is very similar.<br><br>You have an AI partner that is trying to help you, however they are not very considerate. We need your help to improve the AI's helpfulness!<br><br><b>This study webpage will automatically make itself fullscreen.</b>")
    setInstructionsButtonToContinue(undefined, showInstructions1Text, 5)
}

// show the game instructions "This is your chef"
function showInstructions1Text() {
    
    showInstructions("This is your chef. Cute, right?<br><br><img height='150rem' src='static/images/chef.png'/><br>To play the game, control your chef with the arrow keys or WASD keys.<br><br><img class='instructions-controls-image' src='static/images/controls.png'/><br>")
    setInstructionsButtonToContinue(showIntroductionText, showInstructions2Text, 3)
}

// show the game instructions "How to make a soup"
function showInstructions2Text() {
    showInstructions("Your goal is to cook as many soups as you can! Onions and tomatoes are placed around the kitchen, use them to make soups:<br><br><img width='100%' src='static/images/cooking_instructions.png'/><br><br>Try to cook all the available ingredients! You can mix and match ingredients in your soups. If you accidentally pick up an object, you can set it down on an empty counter.")
    setInstructionsButtonToContinue(showInstructions1Text, showResearchText, 10)
}

// show the research overview
function showResearchText() {
    showInstructions("As you play the game, the study will pause to ask you questions such as where you think kitchen objects are located.<br><br>On our end, we will use your responses to make the AI agent (and real-life robots) better able to assist people with household tasks.<br><br>We hope you enjoy this study :-)<br><br>- Jack<br><br>(PS: you can email me at <b>kolb@gatech.edu</b> if something breaks!)")
    setInstructionsButtonToContinue(showInstructions2Text, showConsent, 5)
}

// consent
function showConsent() {
    showInstructions("Please review the consent form. If you consent to the study, please enter your Prolific ID in the text box. If not, you can close this tab and return the study with the code <b style='user-select:text'>CIQE9XIY</b> for no penalty.")
    document.getElementById("consent-input").value = ""
    document.getElementById("consent-form").style.display = "flex"
    setInstructionsButtonToContinue(showResearchText, () => {
        // check if a name was given
        if (!["", ".", ",", "<", ">", ".."].includes(document.getElementById("consent-input").value.trim())) {
            log({"type": "consent", "selection": "yes"})
            showDemographicsIntro();
        }
        else {
            log({"type": "consent", "selection": "alert"})
            alert("If you consent to the study, please enter your Prolific ID in the text field!")
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
    var inputDiv = document.getElementById("screening-age-input")
    inputDiv.value = 1
    inputDiv.oninput = () => {
        log({"type": "screening age", "value": inputDiv.value})
    }
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
    showInstructions("Great! Next we have a demographic question.")
    hideDemographics()
    setInstructionsButtonToContinue(showConsent, showDemographicsGamingText, 1)
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
    showInstructions("We are sorry, but your responses make you ineligible for this study. Thank you for your participation, you can close this tab and return the task with the code <b style='user-select:text'>CIQE9XIY</b> for no penalty")
    hideDemographics()
    // disable the instructions continue button
    document.getElementById("instructions-continue").style.display = "none";
}

// demographics: experience
function showDemographicsGamingText() {
    showInstructions("What is your experience with fast-paced team coordination video games, for example, Overcooked, League of Legends, Black Ops?")
    document.getElementById("demographics-gaming").style.display = "flex"
    setInstructionsButtonToContinue(showDemographicsIntro, showInstructions3Text, 1)
}

// show the game instructions "Let's try a practice round"
function showInstructions3Text() {
    showInstructions("Awesome! Let's get started with a practice round! Press \"Continue\", take in the environment, and then press \"Play\".<br><br><b><u>As a reminder, you can mix onions and tomatoes in your soups.</u></b>")
    setInstructionsButtonToContinue(showDemographicsGamingText, () => {previewRound("preview_kitchen_practice.png", "intro")}, 1)
}

function setInstructionsButtonToPlay(nextStep) {
    document.getElementById("instructions-continue-text").innerHTML = "Play"
    document.getElementById("instructions-continue").setAttribute("class", "instructions-play")
    document.getElementById("instructions-continue").onclick = nextStep
    document.getElementById("instructions-continue-bar").style.backgroundColor = "green"
    hideDemographics()
    // init the loading bar
    setInstructionsButtonLoading(10, () => { 
        document.getElementById("instructions-continue").onclick = nextStep
    })   
}

function hideInstructionsButtons() {
    document.getElementById("instructions-continue").style.display = "none";
    document.getElementById("instructions-back").style.display = "none"
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
    log({"type": "preview round"})
    // enable the right side instructions panel
    document.getElementById("right-panel-instructions").style.display = "flex"
    document.getElementById("left-panel-controls").style.display = "flex"
    // free the instructions content's class
    document.getElementById("instructions-content").setAttribute("class", "")
    // set the game image to show
    document.getElementById("instructions-content-text-top").innerHTML = "<img class='preview-round' src='static/images/" + img + "' width=800px, height=500px />"
    setInstructionsButtonToPlay(async () => {
        let layout = await setStudyStage(stage)
        startGame(layout)  // setStudyStage returns the layout, startGame starts the game
    })
}