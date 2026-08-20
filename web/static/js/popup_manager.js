window.highestZ = 1000;

/**
 * Move a popup above the other open windows.
 * @param {HTMLElement} popup - Popup element that should receive focus.
 */
window.bringToFront = function (popup) {
    if (!popup) return;
    window.highestZ += 1;
    popup.style.zIndex = window.highestZ;
};

document.addEventListener("DOMContentLoaded", () => {
    const popups = document.querySelectorAll(".popup-window");

    popups.forEach((popup) => {
        const header = popup.querySelector("[id$='Header']");
        if (!header) return;

        header.addEventListener("mousedown", () => {
            bringToFront(popup);
        });
    });
});

// for start regonition button
/**
 * Open the recognition tools for logged-in users or show the login popup.
 */
function startRecognition() {
    const isLoggedIn = document.body.dataset.loggedin === "true";

    if (!isLoggedIn) {
        // Trigger login popup
        const loginTrigger = document.getElementById("loginTrigger");
        loginTrigger?.click();
        return;
    }

    // Trigger video popup
    const videoTrigger = document.getElementById("videoIcon");
    videoTrigger?.click();
}
