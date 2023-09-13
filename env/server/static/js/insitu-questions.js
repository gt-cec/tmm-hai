currentInSituQuestion = null
currentInSituResponse = null

function showInSituQuestions() {
    document.getElementById("left-panel").style.display = "flex"
    document.getElementById("right-panel-instructions").style.display = "none"
    document.getElementById("insitu-questions-container").style.display = "flex"
    document.getElementById("overcooked").classList.add("fadeout")

    generateInSituQuestions()
    nextInSituQuestion()
}

// moves on to the next in situ question
function nextInSituQuestion() {
    // move on to the next question
    let q = inSituQuestions.pop()
    if (q != undefined) {
        setInSituQuestion(q[0], q[1], q[2])
        setInSituButtonLoading(5, () => { activateInSituSubmit() })
    }
    // go back to the study
    else {
        hideInSituQuestions()
        pause(false)
        startInSituQuestionTimeout()
    }
}

function activateInSituSubmit() {
    document.getElementById("insitu-submit").style.backgroundColor = "grey";
    t = window.setInterval(() => {
        if (selectedInSituQuestion != null) {
            console.log("Submit timer is complete.")
            document.getElementById("insitu-submit").style.backgroundColor = "lightgreen"
            document.getElementById("insitu-submit").onclick = () => {
                console.log("Clicked submit!")
                log({"type": "in situ submission", "question": currentInSituQuestion, "response": currentInSituResponse})
                selectedInSituQuestion = null
                nextInSituQuestion()
            }
            window.clearTimeout(t)
        }
    }, 100)
    
}

// hides the in situ questions and returns to the base overcooked state
function hideInSituQuestions() {
    inSituQuestions = []
    document.getElementById("left-panel").style.display = "flex"
    document.getElementById("right-panel-instructions").style.display = "flex"
    document.getElementById("insitu-questions-container").style.display = "none"
    document.getElementById("overcooked").classList.remove("fadeout")
}

// pulls a random item from a list
function randomFromList(l) {
    return l[Math.floor(Math.random() * l.length)];
}

// generate the questions to ask the user at each question point
function generateInSituQuestions() {
    categories = ["SA1 ingredientloc", "SA1 playerloc", "SA1 potstate", "SA2 playerstate", "SA2 numremaining", /*"SA3 playerplan", "SA3 teammateplan",*/]
    ingredients = ["<b style='color:goldenrod'>Onion</b>", "<b style='color:red'>Tomato</b>"]

    // generate n questions
    for (let i = 0; i < 2; i++) {
        // filter the applicable categories to remove question categories that have been asked
        applicableCategories = []
        categories.forEach((category) => {
            if (!askedQuestions.includes(category)) {
                applicableCategories.push(category)
            }
        })
        if (applicableCategories.length == 0) {  // if all categories have been asked, reset the categories
            applicableCategories = categories
            askedQuestions = []
        }

        // select a category
        category = randomFromList(applicableCategories)
        askedQuestions.push(category)

        // remove selected category from the possible categories
        // categories.splice(categories.indexOf(category), 1)
    
        // ingredient location
        if (category == "SA1 ingredientloc") {
            ingredient = randomFromList(ingredients)
            questionType = randomFromList(["nearest", "exists"])
            if (questionType == "nearest") {
                inSituQuestions.push(["Where is the nearest available " + ingredient + "? Make your best guess.", "multiple choice", ["Left half", "Right half", "Center-ish", "None available", "No idea"]])
            }
            else if (questionType == "exists") {
                inSituQuestions.push(["Is there at least one available " + ingredient + "? Make your best guess.", "multiple choice", ["Definite YES", "Likely YES", "No idea", "Likely NO", "Definite NO"]])
            }
        }
        // teammate location
        else if (category == "SA1 playerloc") {
            questionType = randomFromList(["teammate", "player"])
            if (questionType == "teammate") {
                inSituQuestions.push(["Where is your <b style='color:blue'>TEAMMATE</b>? Make your best guess.", "grid"])
            }
            // GOLD STANDARD QUESTION!
            else if (questionType == "player") {
                inSituQuestions.push(["Where are <b style='color:#009966'>YOU</b>?", "grid"])
            }
        }
        // pot state
        else if (category == "SA1 potstate") {
            pot = randomFromList(["leftmost", "rightmost"])
            questionType = randomFromList(["ingredients", "cooking"])
            if (questionType == "ingredients") {
                inSituQuestions.push(["How full is the " + pot + " pot? Make your best guess.", "multiple choice", ["Empty", "1-2 ingredients", "3 ingredients (full/cooking)", "No idea"]])
            }
            else if (questionType == "cooking") {
                inSituQuestions.push(["What is the " + pot + " pot's status? Make your best guess.", "multiple choice", ["Finished cooking", "Cooking", "1-2 ingredients", "Empty", "No idea"]])
            }
        }
        // player state
        else if (category == "SA2 playerstate") {
            questionType = randomFromList(["you", "teammate"])
            if (questionType == "you") {
                inSituQuestions.push(["What are <b style='color:#009966'>YOU</b> doing now?", "multiple choice", ["Getting ingredient for pot", "Getting dish for soup", "Bringing soup to station", "Idling, all soups complete"]])
            }
            else if (questionType == "teammate") {
                inSituQuestions.push(["What is your <b style='color:blue'>TEAMMATE</b> doing now? Make your best guess.", "multiple choice", ["Getting ingredient for pot", "Getting dish for soup", "Bringing soup to station", "Idling, all soups complete", "No idea"]])
            }
        }
        // number of dishes remaining
        else if (category == "SA2 numremaining") {
            questionType = randomFromList(["cancook", /*"willcomplete"*/])  // ignoring the S3 questions
            if (questionType == "cancook") {
                inSituQuestions.push(["How many more soups can be made/delivered, including soups in-progress? Make your best guess.", "multiple choice", ["No soups", "1-2 soups", "3-4 soups", "5+ soups", "No idea"]])
            }
            else if (questionType == "willcomplete") {
                inSituQuestions.push(["Do you think your team will complete all the dishes in time?", "multiple choice", ["YES or already complete", "Probably YES", "Not sure", "Probably NO", "Definite NO"]])
            }
        }
        // player plan
        else if (category == "SA3 playerplan") {
            inSituQuestions.push(["What will <b style='color:#009966'>YOU</b> be doing ~10 seconds from now?", "multiple choice", ["Getting ingredient for pot", "Getting dish for soup", "Bringing soup to station", "Exploring kitchen", "Idling, all soups complete", "Not sure yet"]])
        }
        // teammate plan
        else if (category == "SA3 teammateplan") {
            inSituQuestions.push(["What will your <b style='color:blue'>TEAMMATE</b> be doing ~10 seconds from now? Make your best guess.", "multiple choice", ["Getting ingredient for pot", "Getting dish for soup", "Bringing soup to station", "Idling", "No idea"]])
        }
    }

}

function checkIngredient() {

}

// records the button response press
function recordInSituResponse(question, response) {
    // log the answer
    currentInSituQuestion = question
    currentInSituResponse = response
    log({"type": "in situ selection", "question": question, "response": response})
}

// shows the question, questionType can be "multiple choice" or "quadrant" or "side"
selectedInSituQuestion = null
responseToElement = {}
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
            responseToElement[element] = q
            q.onclick = () => {
                recordInSituResponse(text, element)
                responseToElement[element].style.backgroundColor = "#ee90ee"
                if (selectedInSituQuestion != null) {
                    responseToElement[selectedInSituQuestion].style.backgroundColor = ""
                }
                selectedInSituQuestion = element
            }
            document.getElementById("insitu-questions-questions-container").appendChild(q)
        })
    }
    if (questionType == "grid") {
        // create the top button row
        topRow = document.createElement("div")
        topRow.setAttribute("class", "insitu-questions-grid-row")
        // create a center row
        centerRow = document.createElement("div")
        centerRow.setAttribute("class", "insitu-questions-grid-row")
        // create the bottom button row
        bottomRow = document.createElement("div")
        bottomRow.setAttribute("class", "insitu-questions-grid-row")
        // create the buttons
        quartants = ["Top Left", "Top Right", "Bottom Left", "Bottom Right"]
        for (let i=0; i<quartants.length; i++) {
            // create the grid item
            q = document.createElement("div")
            q.setAttribute("class", "insitu-questions-question insitu-questions-grid-item")
            q.innerHTML = quartants[i]
            responseToElement[quartants[i]] = q
            q.onclick = () => {
                recordInSituResponse(text, quartants[i])
                responseToElement[quartants[i]].style.backgroundColor = "#ee90ee"
                if (selectedInSituQuestion != null) {
                    responseToElement[selectedInSituQuestion].style.backgroundColor = ""
                }
                selectedInSituQuestion = quartants[i]
            }
            // add the grid item to the correct row
            (i < 2 ? topRow : bottomRow).appendChild(q)
        }
        // add the rows
        document.getElementById("insitu-questions-questions-container").appendChild(topRow)
        document.getElementById("insitu-questions-questions-container").appendChild(centerRow)
        document.getElementById("insitu-questions-questions-container").appendChild(bottomRow)

        // add a "in the center" option
        centerButton = document.createElement("div")
        centerButton.setAttribute("class", "insitu-questions-question insitu-questions-grid-item")
        centerButton.innerHTML = "Center or In-Between"
        responseToElement[centerButton.innerHTML] = centerButton
        centerButton.onclick = () => {
            recordInSituResponse(text, "center")
            responseToElement[centerButton.innerHTML].style.backgroundColor = "#ee90ee"
            if (selectedInSituQuestion != null) {
                responseToElement[selectedInSituQuestion].style.backgroundColor = ""
            }
            selectedInSituQuestion = centerButton.innerHTML
        }
        centerRow.appendChild(centerButton)

        // add a "no idea" option
        noIdeaButton = document.createElement("div")
        noIdeaButton.setAttribute("class", "insitu-questions-question")
        noIdeaButton.innerHTML = "No idea"
        responseToElement[noIdeaButton.innerHTML] = noIdeaButton
        noIdeaButton.onclick = () => {
            recordInSituResponse(text, "no idea")
            responseToElement[noIdeaButton.innerHTML].style.backgroundColor = "#ee90ee"
            if (selectedInSituQuestion != null) {
                responseToElement[selectedInSituQuestion].style.backgroundColor = ""
            }
            selectedInSituQuestion = noIdeaButton.innerHTML
        }
        document.getElementById("insitu-questions-questions-container").appendChild(noIdeaButton)
    }
}

// resets the highlighting for when a question is clicked
function setQuestionHighlighting(question) {
    document.getElementById("insitu-questions-questions-container").childNodes.forEach(element => {
        console.log("Highlight element", element, "and q", question)
        if (element.innerHTML == question) {
            element.style.backgroundColor = "#ee90ee"
        }
        else {
            element.style.backgroundColor = "lightblue"
        }
    })
}