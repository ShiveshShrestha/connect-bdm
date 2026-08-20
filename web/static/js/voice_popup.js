document.addEventListener("DOMContentLoaded", function () {
    const voiceButton = document.getElementById("voiceCommBtn");
    const popup = document.getElementById("voicePopup");
    const closeButton = document.getElementById("closeVoicePopup");
    const status = document.getElementById("voiceStatus");
    const result = document.getElementById("voiceResult");

    if (!popup || !status || !result) return;

    let mediaRecorder = null;
    let stream = null;
    let audioChunks = [];
    let recording = false;
    let recognizedText = "";
    let popupOpen = false;

    dragElement(popup);

    /**
     * Allow the voice popup to be moved by its header.
     * @param {HTMLElement} element - Popup to make draggable.
     */
    function dragElement(element) {
        const header = element.querySelector(".voice-header");
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

        /** Stop tracking pointer movement. */
        function closeDrag() {
            document.onmouseup = null;
            document.onmousemove = null;
        }
    }

    /* ================= SPEECH FUNCTION ================= */
    /**
     * Read a message aloud while the voice popup remains open.
     * @param {string} text - Message to speak.
     * @param {?Function} callback - Optional function to run when speech ends.
     */
    function speak(text, callback = null) {
        // stop speaking immediately if popup is closed
        if (!popupOpen || !text) return;

        window.speechSynthesis.cancel(); // stop any previous speech

        const speech = new SpeechSynthesisUtterance(text);
        speech.lang = "en-US";
        speech.rate = 1;
        speech.pitch = 1;

        if (callback) {
            speech.onend = () => {
                if (popupOpen) callback(); // only run callback if popup is open
            };
        }

        window.speechSynthesis.speak(speech);
    }

    /* ================= RESET PROGRAM ================= */
    /** Reset the current message and explain the keyboard controls. */
    function restartProgram() {
        stopMicrophone();
        recognizedText = "";
        audioChunks = [];
        result.innerText = "";
        status.innerText = "Press Enter to start recording.";

        speak("Voice communication is ready. Press Enter to start recording, then press Enter again to stop.");
    }

    /* ================= OPEN POPUP ================= */
    voiceButton?.addEventListener("click", () => {
        popup.style.display = "block";
        bringToFront(popup);
        popupOpen = true;
        restartProgram();
    });

    closeButton?.addEventListener("click", () => {
        popup.style.display = "none";
        popupOpen = false;

        // stop microphone and recorder
        shutdownMicrophone();

        // stop all speech immediately
        window.speechSynthesis.cancel();

        // reset UI and state
        recognizedText = "";
        audioChunks = [];
        status.innerText = "Voice communication closed.";
        result.innerText = "";
    });

    /* ================= START RECORDING ================= */
    /** Ask for microphone access and begin recording a WebM audio clip. */
    async function startRecording() {
        try {
            stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(stream);
            audioChunks = [];

            mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) audioChunks.push(event.data);
            };
            mediaRecorder.onstop = processAudio;
            mediaRecorder.start();

            recording = true;
            status.innerText = "Recording... Press Enter when you are finished.";
            speak("Recording started");
        } catch (error) {
            status.innerText = "Microphone access was not allowed.";
            console.error("Microphone access failed:", error);
        }
    }

    /* ================= STOP RECORDING ================= */
    /** Stop the active recorder and release the microphone stream. */
    function stopRecording() {
        if (mediaRecorder && recording) {
            mediaRecorder.stop();
            recording = false;
            status.innerText = "Processing the recording...";
            speak("Recording stopped");
        }

        // release microphone
        if (stream) {
            stream.getTracks().forEach((track) => track.stop());
            stream = null;
        }
    }

    /* ================= TURN OFF MICROPHONE ================= */
    /** Release the microphone without sending the recording for recognition. */
    function stopMicrophone() {
        if (stream) {
            stream.getTracks().forEach((track) => track.stop());
            stream = null;
        }

        recording = false;
    }

    /* ================= PROCESS AUDIO ================= */
    /** Upload the completed recording and show the recognized text. */
    async function processAudio() {
        if (!popupOpen || audioChunks.length === 0) return;

        const blob = new Blob(audioChunks, { type: "audio/webm" });
        const formData = new FormData();
        formData.append("audio", blob, "recording.webm");

        try {
            const response = await fetch("/voice/upload_audio", {
                method: "POST",
                body: formData,
            });
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || "The recording could not be processed.");
            }

            if (data.text) {
                recognizedText = data.text;
                result.innerText = recognizedText;
                status.innerText = "Speech converted to text.";

                speak(`The converted text is ${recognizedText}`, () => {
                    speak("Press J to discard it, K to save it, or F to start again.");
                });
            } else {
                status.innerText = "No speech was recognized. Press F to try again.";
            }
        } catch (error) {
            status.innerText = error.message || "The server could not process the recording.";
            console.error("Audio processing failed:", error);
        }
    }

    /* ================= SAVE MESSAGE ================= */
    /** Save the recognized message in the project's inbox file. */
    async function saveMessage() {
        if (!recognizedText) return;

        try {
            const response = await fetch("/voice/save_message", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({ text: recognizedText }),
            });
            const data = await response.json();

            if (!response.ok) throw new Error(data.error || "The message could not be saved.");
            status.innerText = "Message saved.";
            speak("Message saved");
        } catch (error) {
            status.innerText = error.message;
            speak("The message could not be saved");
        }
    }

    /* ================= DISCARD MESSAGE ================= */
    /** Clear the current recognized message without saving it. */
    function discardMessage() {
        recognizedText = "";
        result.innerText = "";
        status.innerText = "Message discarded. Press F to start again.";
        speak("Message discarded");
    }

    /* ================= KEYBOARD CONTROLS ================= */
    document.addEventListener("keydown", function (event) {
        if (popup.style.display !== "block") return;

        /* ENTER KEY */
        if (event.key === "Enter") {
            event.preventDefault();
            if (!recording && !recognizedText) startRecording();
            else if (recording) stopRecording();
        }

        /* J KEY → DISCARD */
        if (event.key.toLowerCase() === "j" && recognizedText) {
            discardMessage();
        }

        /* K KEY → SAVE */
        if (event.key.toLowerCase() === "k" && recognizedText) {
            saveMessage();
        }

        /* F KEY → RESTART */
        if (event.key.toLowerCase() === "f") {
            restartProgram();
        }
    });

    /** Stop recording, release the stream, and clear temporary voice state. */
    function shutdownMicrophone() {
        // stop recorder if active
        if (mediaRecorder && recording) {
            mediaRecorder.onstop = null;
            mediaRecorder.stop();
        }

        // stop microphone stream completely
        if (stream) {
            stream.getTracks().forEach((track) => {
                track.stop();
            });
            stream = null;
        }

        // reset variables
        mediaRecorder = null;
        recording = false;
        audioChunks = [];
        recognizedText = "";
    }
});
