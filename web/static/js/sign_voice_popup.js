document.addEventListener("DOMContentLoaded", async () => {
    // --- Elements ---
    const button = document.querySelector("#videoPopup .video-content .video-option:nth-child(1)");
    const popup = document.getElementById("signVoicePopup");
    const closeButton = document.getElementById("closeSignVoice");
    const video = document.getElementById("signVideo");
    const predictedText = document.getElementById("predText");
    const errorDisplay = document.getElementById("signVoiceError");
    const statusDisplay = document.getElementById("signVoiceStatus");

    if (!button || !popup || !closeButton || !video || !predictedText) return;

    // --- Make popup draggable via header ---
    dragElement(popup);

    /**
     * Allow the sign-recognition popup to be moved by its header.
     * @param {HTMLElement} element - Popup to make draggable.
     */
    function dragElement(element) {
        const header = element.querySelector(".sign-voice-header");
        let pos1 = 0;
        let pos2 = 0;
        let pos3 = 0;
        let pos4 = 0;

        if (header) {
            header.onmousedown = dragMouseDown;
        }

        /** Begin tracking the pointer. */
        function dragMouseDown(event) {
            event.preventDefault();
            // starting cursor position
            pos3 = event.clientX;
            pos4 = event.clientY;
            document.onmouseup = closeDrag;
            document.onmousemove = elementDrag;
        }

        /** Move the popup by the pointer distance. */
        function elementDrag(event) {
            event.preventDefault();
            // calculate distance moved
            pos1 = pos3 - event.clientX;
            pos2 = pos4 - event.clientY;
            pos3 = event.clientX;
            pos4 = event.clientY;
            // move element
            element.style.top = `${element.offsetTop - pos2}px`;
            element.style.left = `${element.offsetLeft - pos1}px`;
        }

        /** End the current drag operation. */
        function closeDrag() {
            document.onmouseup = null;
            document.onmousemove = null;
        }
    }

    /////////////////////////////////////////////
    // --- Overlay for predicted letter ---
    const overlay = document.createElement("div");
    overlay.className = "pred-overlay";
    video.parentElement.appendChild(overlay);

    // --- Container below textarea ---
    const container = document.createElement("div");
    container.className = "pred-container";
    predictedText.parentElement.appendChild(container);

    // --- Button row ---
    const buttonRow = document.createElement("div");
    buttonRow.className = "btn-row";
    container.appendChild(buttonRow);

    // --- Buttons ---
    /**
     * Create and append one action button below the prediction box.
     * @param {string} text - Button label.
     * @param {Function} onClick - Click handler.
     * @returns {HTMLButtonElement} Newly created button.
     */
    const createButton = (text, onClick) => {
        const newButton = document.createElement("button");
        newButton.type = "button";
        newButton.textContent = text;
        newButton.className = "pred-btn";
        newButton.addEventListener("click", onClick);
        buttonRow.appendChild(newButton);
        return newButton;
    };

    /** Request an MP3 file for the current prediction text. */
    async function requestVoiceBlob() {
        const text = predictedText.value.trim();
        if (!text) throw new Error("There is no text to convert.");

        const response = await fetch("/generate-voice", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text }),
        });

        if (!response.ok) {
            const data = await response.json().catch(() => ({}));
            throw new Error(data.error || "The voice file could not be generated.");
        }

        return response.blob();
    }

    createButton("Play Voice", async () => {
        try {
            const blob = await requestVoiceBlob();
            const audioUrl = URL.createObjectURL(blob);
            const audio = new Audio(audioUrl);
            await audio.play();
            audio.onended = () => {
                URL.revokeObjectURL(audioUrl); // clean up
            };
        } catch (error) {
            console.error(error);
            alert(error.message);
        }
    });

    createButton("Save Voice", async () => {
        try {
            const blob = await requestVoiceBlob();
            const audioUrl = window.URL.createObjectURL(blob);
            const downloadLink = document.createElement("a");
            downloadLink.href = audioUrl;
            downloadLink.download = "voice.mp3";
            document.body.appendChild(downloadLink);
            downloadLink.click();
            downloadLink.remove();
            window.URL.revokeObjectURL(audioUrl);
        } catch (error) {
            console.error(error);
            alert(error.message);
        }
    });

    const clearButton = createButton("Clear", () => {
        predictedText.value = "";
        recentLetter.textContent = "Latest prediction: none";
    });
    clearButton.setAttribute("aria-label", "Clear predicted text");

    // --- Recent Letter ---
    const recentLetter = document.createElement("div");
    recentLetter.className = "recent-letter";
    recentLetter.textContent = "Latest prediction: none";
    container.appendChild(recentLetter);

    // --- Hand Detection Status ---
    const handStatus = document.createElement("div");
    handStatus.className = "hand-status";
    container.appendChild(handStatus);

    // --- Prediction classes (lowercase) ---
    const CLASSES = [
        "a", "b", "c", "d", "e", "f", "g", "h", "i", "j",
        "k", "l", "m", "n", "o", "p", "q", "r", "s", "t",
        "u", "v", "w", "x", "y", "z", "del", "nothing", "space",
    ];

    let model = null;
    let camera = null;
    let currentLetter = "";

    /** Load the TensorFlow.js sign-recognition model once. */
    async function loadModel() {
        if (model) return true;

        try {
            if (statusDisplay) statusDisplay.textContent = "Loading the recognition model...";
            model = await tf.loadLayersModel("/static/models/CNN_Model/model.json");
            if (statusDisplay) statusDisplay.textContent = "Model ready.";
            return true;
        } catch (error) {
            console.error("Failed to load model", error);
            if (errorDisplay) errorDisplay.textContent = "The sign-recognition model could not be loaded.";
            return false;
        }
    }

    // --- MediaPipe Hands ---
    const hands = new Hands({
        locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/hands/${file}`,
    });
    hands.setOptions({
        maxNumHands: 1,
        modelComplexity: 1,
        minDetectionConfidence: 0.7,
        minTrackingConfidence: 0.7,
    });

    hands.onResults(async (results) => {
        if (!results.multiHandLandmarks || results.multiHandLandmarks.length === 0) {
            overlay.textContent = "";
            handStatus.textContent = "No hand detected";
            handStatus.style.color = "#aa0000";
            currentLetter = "";
            return;
        }

        if (!model) return;

        handStatus.textContent = "Hand detected";
        handStatus.style.color = "#007700";

        const landmarks = results.multiHandLandmarks[0];
        const inputData = landmarks.flatMap((landmark) => [landmark.x, landmark.y, landmark.z]);
        const inputTensor = tf.tensor2d([inputData]);
        const prediction = model.predict(inputTensor);
        const indexTensor = prediction.argMax(-1);
        const predictionIndex = (await indexTensor.data())[0];
        const letter = CLASSES[predictionIndex];

        inputTensor.dispose();
        prediction.dispose();
        indexTensor.dispose();

        if (letter !== "nothing") {
            currentLetter = letter;
            overlay.textContent = letter;
        } else {
            overlay.textContent = "";
            currentLetter = "";
        }
    });

    // --- Camera control ---
    /** Start the camera and send each frame to MediaPipe Hands. */
    function startCamera() {
        if (!camera) {
            camera = new Camera(video, {
                onFrame: async () => {
                    await hands.send({ image: video });
                },
                width: 640,
                height: 480,
            });
        }
        camera.start();
    }

    /** Stop every active camera track and reset the camera helper. */
    function stopCamera() {
        if (camera?.stop) camera.stop();
        if (video.srcObject) {
            video.srcObject.getTracks().forEach((track) => track.stop());
            video.srcObject = null;
        }
        camera = null;
    }

    // --- Enter key registers predicted letter, allows manual typing ---
    predictedText.removeAttribute("readonly");
    predictedText.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" || !currentLetter) return;

        event.preventDefault();
        if (currentLetter === "space") predictedText.value += " ";
        else if (currentLetter === "del") predictedText.value = predictedText.value.slice(0, -1);
        else predictedText.value += currentLetter;

        recentLetter.textContent = `Latest prediction: ${currentLetter}`;
        currentLetter = "";
        overlay.textContent = "";
    });

    // --- Open/Close popup ---
    button.addEventListener("click", async () => {
        popup.style.display = "block";
        bringToFront(popup);
        if (errorDisplay) errorDisplay.textContent = "";

        const modelLoaded = await loadModel();
        if (modelLoaded) startCamera();
    });

    closeButton.addEventListener("click", () => {
        popup.style.display = "none";
        stopCamera();
        overlay.textContent = "";
        recentLetter.textContent = "Latest prediction: none";
        handStatus.textContent = "";
        if (statusDisplay) statusDisplay.textContent = "";
    });
});
