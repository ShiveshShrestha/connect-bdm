let loginType = "user";

document.addEventListener("DOMContentLoaded", () => {
    const userButton = document.getElementById("userMode");
    const adminButton = document.getElementById("adminModeBtn");

    userButton?.addEventListener("click", () => {
        loginType = "user";
        userButton.classList.add("active");
        adminButton?.classList.remove("active");
    });

    adminButton?.addEventListener("click", () => {
        loginType = "admin";
        adminButton.classList.add("active");
        userButton?.classList.remove("active");
    });

    const userIcon = document.querySelector(".fa-user")?.parentElement;
    const loginBox = document.getElementById("loginBox");
    const closeLoginButton = document.getElementById("closeLogin");

    // Show login box on click
    userIcon?.addEventListener("click", (event) => {
        event.preventDefault();
        loginBox.style.display = "block";
        bringToFront(loginBox);
    });

    // Hide login box on close
    closeLoginButton?.addEventListener("click", () => {
        loginBox.style.display = "none";
    });

    // Drag functionality
    if (loginBox) dragElement(loginBox);

    /**
     * Allow the login window to be repositioned by dragging its header.
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

        /** Record the initial mouse position. */
        function dragMouseDown(event) {
            const currentEvent = event || window.event;
            currentEvent.preventDefault();
            pos3 = currentEvent.clientX;
            pos4 = currentEvent.clientY;
            document.onmouseup = closeDragElement;
            document.onmousemove = elementDrag;
        }

        /** Move the login box along with the pointer. */
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

        /** Stop moving the login box. */
        function closeDragElement() {
            document.onmouseup = null;
            document.onmousemove = null;
        }
    }

    // Password Toggle
    const togglePassword = document.getElementById("togglePassword");
    togglePassword?.addEventListener("click", () => {
        const passwordField = document.getElementById("passwordField");
        if (!passwordField) return;
        passwordField.type = passwordField.type === "password" ? "text" : "password";
    });
});

// Login Handling
const loginForm = document.getElementById("login-form");
const loginError = document.getElementById("loginError");

loginForm?.addEventListener("submit", async (event) => {
    event.preventDefault();

    const username = document.getElementById("logusername")?.value.trim() || "";
    const password = document.getElementById("passwordField")?.value || "";

    if (loginError) loginError.textContent = "";

    try {
        const response = await fetch("/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                username,
                password,
                login_type: loginType,
            }),
        });

        const data = await response.json();
        if (data.success) {
            location.reload(); // reload page to update navbar
            return;
        }

        if (loginError) loginError.textContent = data.message || "Login was not successful.";
    } catch (error) {
        if (loginError) loginError.textContent = "The server could not be reached. Please try again.";
        console.error("Login request failed:", error);
    }
});
