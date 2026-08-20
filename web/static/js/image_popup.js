document.addEventListener("DOMContentLoaded", () => {
    const imageButton = document.getElementById("imageTrigger");
    const imagePopup = document.getElementById("imagePopup");
    const closeImageButton = document.getElementById("closeImagePopup");

    if (!imageButton || !imagePopup || !closeImageButton) return;

    imageButton.addEventListener("click", () => {
        imagePopup.style.display = "block";
        bringToFront(imagePopup);
    });

    closeImageButton.addEventListener("click", () => {
        imagePopup.style.display = "none";
    });

    // Enable dragging
    dragElement(imagePopup);

    /**
     * Allow the image viewer to be moved by its header.
     * @param {HTMLElement} element - Popup to make draggable.
     */
    function dragElement(element) {
        const header = document.getElementById(`${element.id}Header`);
        let pos1 = 0;
        let pos2 = 0;
        let pos3 = 0;
        let pos4 = 0;

        if (header) header.onmousedown = dragMouseDown;
        else element.onmousedown = dragMouseDown;

        /** Record the pointer position when dragging begins. */
        function dragMouseDown(event) {
            const currentEvent = event || window.event;
            currentEvent.preventDefault();
            pos3 = currentEvent.clientX;
            pos4 = currentEvent.clientY;
            document.onmouseup = closeDragElement;
            document.onmousemove = elementDrag;
        }

        /** Move the popup while the pointer is held down. */
        function elementDrag(event) {
            const currentEvent = event || window.event;
            currentEvent.preventDefault();
            pos1 = pos3 - currentEvent.clientX;
            pos2 = pos4 - currentEvent.clientY;
            pos3 = currentEvent.clientX;
            pos4 = currentEvent.clientY;
            element.style.top = `${element.offsetTop - pos2}px`;
            element.style.left = `${element.offsetLeft - pos1}px`;
        }

        /** Stop the active drag operation. */
        function closeDragElement() {
            document.onmouseup = null;
            document.onmousemove = null;
        }
    }
});
