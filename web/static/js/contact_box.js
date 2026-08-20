document.addEventListener("DOMContentLoaded", () => {
    const commentLink = document.querySelector(".fa-comments")?.parentElement;
    const contactBox = document.getElementById("contactBox");
    const closeButton = document.getElementById("closeContact");

    if (!commentLink || !contactBox || !closeButton) return;

    commentLink.addEventListener("click", () => {
        contactBox.style.display = "block";
        bringToFront(contactBox); // show box
    });

    closeButton.addEventListener("click", () => {
        contactBox.style.display = "none"; // hide box
    });

    // Drag functionality
    dragElement(contactBox);

    /**
     * Allow the contact popup to be moved by its header.
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

        /** Record the pointer position when dragging starts. */
        function dragMouseDown(event) {
            const currentEvent = event || window.event;
            currentEvent.preventDefault();
            pos3 = currentEvent.clientX;
            pos4 = currentEvent.clientY;
            document.onmouseup = closeDragElement;
            document.onmousemove = elementDrag;
        }

        /** Reposition the popup while the pointer moves. */
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

        /** Remove document-level dragging handlers. */
        function closeDragElement() {
            document.onmouseup = null;
            document.onmousemove = null;
        }
    }
});
