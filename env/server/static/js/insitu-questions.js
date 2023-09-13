function showInSituQuestions() {
    document.getElementById("left-panel").style.display = "none"
    document.getElementById("insitu-questions-container").style.display = "flex"
    document.getElementById("insitu-questions-container").style.height = document.getElementById("instructions-content").scrollHeight + "px"
    generateInSituQuestions()
    nextInSituQuestion()
}

// moves on to the next in situ question
function nextInSituQuestion() {
    // move on to the next question
    let q = inSituQuestions.pop()
    if (q != undefined) {
        setInSituQuestion(q[0], q[1], q[2])
    }
    // go back to the study
    else {
        hideInSituQuestions()
    }
}

// hides the in situ questions and returns to the base overcooked state
function hideInSituQuestions() {
    inSituQuestions = []
    document.getElementById("left-panel").style.display = "flex"
    document.getElementById("insitu-questions-container").style.display = "none"
    document.getElementById("insitu-questions-container").style.height = document.getElementById("instructions-content").scrollHeight + "px"
}

function generateInSituQuestions() {
    inSituQuestions.push(["Some example question", "multiple choice", ["Some answer", "another answer", "a third answer"]])
}

// records the button response press
function recordInSituResponse(question, response) {
    // log the answer
    console.log("Q: " + question + ", R: " + response)
    nextInSituQuestion()
}

// shows the question, questionType can be "multiple choice" or "quadrant" or "side"
function setInSituQuestion(text, questionType, questions) {
    document.getElementById("insitu-questions-container").style.display = "flex"
    document.getElementById("insitu-questions-questions-container").innerHTML = ""
    // set the question title
    document.getElementById("insitu-questions-text").innerHTML = text
    // format by the question type
    if (questionType == "multiple choice") {
        questions.forEach(element => {
            // create the response div
            q = document.createElement("div")
            q.setAttribute("class", "insitu-questions-question")
            q.innerHTML = element
            q.onclick = () => {recordInSituResponse(text, element)}
            document.getElementById("insitu-questions-questions-container").appendChild(q)
        })
    }
}