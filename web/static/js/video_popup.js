document.addEventListener("DOMContentLoaded", () => {
    const videoIcon = document.getElementById("videoIcon");
    const videoPopup = document.getElementById("videoPopup");
    const closeButton = document.getElementById("closeVideoPopup");
    const loggedIn = document.body.dataset.loggedin === "true";

    if (!videoPopup) return;

    videoIcon?.addEventListener("click", () => {
        if (!loggedIn) {
            document.getElementById("loginTrigger")?.click();
            return;
        }

        videoPopup.style.display = "block";
        bringToFront(videoPopup);
    });

    closeButton?.addEventListener("click", () => {
        videoPopup.style.display = "none";
    });

    // Drag feature like login box
    dragElement(videoPopup);

    /**
     * Allow the video tools window to be moved by its header.
     * @param {HTMLElement} element - Popup to make draggable.
     */
    function dragElement(element) {
        const header = document.getElementById(`${element.id}Header`);
        let pos1 = 0;
        let pos2 = 0;
        let pos3 = 0;
        let pos4 = 0;

        if (header) header.onmousedown = dragMouseDown;

        /** Record the pointer position at the start of a drag. */
        function dragMouseDown(event) {
            event.preventDefault();
            pos3 = event.clientX;
            pos4 = event.clientY;
            document.onmouseup = closeDrag;
            document.onmousemove = elementDrag;
        }

        /** Move the video popup with the pointer. */
        function elementDrag(event) {
            event.preventDefault();
            pos1 = pos3 - event.clientX;
            pos2 = pos4 - event.clientY;
            pos3 = event.clientX;
            pos4 = event.clientY;
            element.style.top = `${element.offsetTop - pos2}px`;
            element.style.left = `${element.offsetLeft - pos1}px`;
        }

        /** Stop the active drag operation. */
        function closeDrag() {
            document.onmouseup = null;
            document.onmousemove = null;
        }
    }
});
