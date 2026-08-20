document.addEventListener("DOMContentLoaded", function () {
    // ================= POPUP ELEMENTS =================
    const interpretButton = document.getElementById("interpretTextBtn");
    const popup = document.getElementById("interpretPopup");
    const closePopup = document.getElementById("closeInterpretPopup");

    const imageElement = document.getElementById("interpretImage");
    const textDisplay = document.getElementById("textDisplay");
    const currentWordDisplay = document.getElementById("currentWord");
    const fileInput = document.getElementById("textFileInput");
    const speedSlider = document.getElementById("speedSlider");

    const startButton = document.getElementById("startBtn");
    const playButton = document.getElementById("playBtn");
    const pauseButton = document.getElementById("pauseBtn");
    const nextButton = document.getElementById("nextBtn");
    const previousButton = document.getElementById("prevBtn");

    if (!popup || !imageElement) return;

    // ================= POPUP CONTROL =================
    interpretButton?.addEventListener("click", () => {
        popup.style.display = "block";
        bringToFront(popup);
    });

    closePopup?.addEventListener("click", () => {
        popup.style.display = "none";
        pause();
    });

    // ================= DATA =================
    let textData = "";
    let currentIndex = 0;
    let timer = null;
    let playing = false;

    // ================= WORD UTILITIES =================
    /** Return the word immediately before the current character. */
    function getPreviousWord() {
        if (currentIndex === 0) return "";
        const textUpToSpace = textData.slice(0, currentIndex);
        const words = textUpToSpace.trim().split(/\s+/);
        return words.length ? words[words.length - 1] : "";
    }

    /** Return the character currently selected in the uploaded text. */
    function getCurrentChar() {
        return textData[currentIndex] || "";
    }

    // ================= PRELOAD LETTERS =================
    const letters = "abcdefghijklmnopqrstuvwxyz";
    const letterImages = {};
    for (const character of letters) {
        const image = new Image();
        image.src = `/static/letters/${character}.png`;
        letterImages[character] = image;
    }

    const spaceImage = new Image();
    spaceImage.src = "/static/letters/space.png";

    const wordCache = {};

    // ================= IMAGE DISPLAY =================
    /** Display the sign image for the selected character or the previous word. */
    function displayChar() {
        if (!textData || currentIndex >= textData.length) {
            imageElement.src = spaceImage.src;
            if (currentWordDisplay) currentWordDisplay.textContent = "";
            return;
        }

        const character = getCurrentChar();
        const lowerCharacter = character.toLowerCase();

        if (character === " ") {
            const word = getPreviousWord();
            if (currentWordDisplay) currentWordDisplay.textContent = word ? `Word: ${word}` : "";

            if (word) {
                wordCache[word] ||= `/interpret/generate_word_image?word=${encodeURIComponent(word)}`;
                imageElement.src = wordCache[word];
            } else {
                imageElement.src = spaceImage.src;
            }
        } else if (/[a-z]/.test(lowerCharacter)) {
            imageElement.src = letterImages[lowerCharacter]?.src || spaceImage.src;
            if (currentWordDisplay) currentWordDisplay.textContent = `Letter: ${lowerCharacter.toUpperCase()}`;
        } else {
            imageElement.src = spaceImage.src;
            if (currentWordDisplay) currentWordDisplay.textContent = "Unsupported character";
        }
    }

    /** Display the current character and schedule the next one during playback. */
    function advanceChar() {
        displayChar();

        if (!playing) return;
        if (currentIndex >= textData.length - 1) {
            pause();
            return;
        }

        currentIndex += 1;
        const speed = Number.parseInt(speedSlider?.value || "800", 10);
        timer = window.setTimeout(advanceChar, speed);
    }

    // ================= CONTROLS =================
    /** Begin automatic character playback. */
    function play() {
        if (!textData || playing) return;
        if (currentIndex >= textData.length) currentIndex = 0;
        playing = true;
        advanceChar();
    }

    /** Pause playback and clear the active timer. */
    function pause() {
        playing = false;
        if (timer) {
            window.clearTimeout(timer);
            timer = null;
        }
    }

    /** Move to the next character in the uploaded text. */
    function nextChar() {
        pause();
        if (currentIndex < textData.length - 1) currentIndex += 1;
        displayChar();
    }

    /** Move to the previous character in the uploaded text. */
    function prevChar() {
        pause();
        if (currentIndex > 0) currentIndex -= 1;
        displayChar();
    }

    /** Return playback to the first character. */
    function restart() {
        pause();
        currentIndex = 0;
        displayChar();
    }

    // ================= FILE INPUT =================
    fileInput?.addEventListener("change", function () {
        const file = this.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = function (event) {
            textData = String(event.target.result || "").trim();
            if (textData) textData += " ";
            currentIndex = 0;
            if (textDisplay) textDisplay.innerText = textData || "The selected file is empty.";
            displayChar();
        };
        reader.readAsText(file);
    });

    // ================= BUTTON EVENTS =================
    startButton?.addEventListener("click", restart);
    playButton?.addEventListener("click", play);
    pauseButton?.addEventListener("click", pause);
    nextButton?.addEventListener("click", nextChar);
    previousButton?.addEventListener("click", prevChar);

    // ================= MAKE POPUP DRAGGABLE (Reference Style) =================
    dragElement(popup);

    /**
     * Allow the interpreter popup to be moved by its header.
     * @param {HTMLElement} element - Popup to make draggable.
     */
    function dragElement(element) {
        const header = popup.querySelector(".interpret-header");
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

        /** Move the popup using the pointer distance. */
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
});
