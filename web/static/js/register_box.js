document.addEventListener("DOMContentLoaded", () => {
    // Elements
    const registerLinks = document.querySelectorAll("a.register-link"); // multiple links possible
    const registerBox = document.getElementById("registerBox");
    const closeRegisterButton = document.getElementById("closeRegister");
    const registerForm = document.getElementById("register-form");
    const registerMessage = document.getElementById("registerMessage");

    if (!registerBox || !registerForm || !registerMessage) return;

    // --- Open register box ---
    registerLinks.forEach((link) => {
        link.addEventListener("click", (event) => {
            event.preventDefault();
            registerBox.style.display = "block";
            bringToFront(registerBox);
        });
    });

    // --- Close register box ---
    closeRegisterButton?.addEventListener("click", () => {
        registerBox.style.display = "none";
    });

    // --- Drag functionality ---
    dragElement(registerBox);

    /**
     * Allow the registration window to be moved by its header.
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

        /** Record the initial pointer position. */
        function dragMouseDown(event) {
            const currentEvent = event || window.event;
            currentEvent.preventDefault();
            pos3 = currentEvent.clientX;
            pos4 = currentEvent.clientY;
            document.onmouseup = closeDragElement;
            document.onmousemove = elementDrag;
        }

        /** Move the registration box with the pointer. */
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

        /** End the current drag operation. */
        function closeDragElement() {
            document.onmouseup = null;
            document.onmousemove = null;
        }
    }

    // --- Password toggle ---
    const togglePassword = document.getElementById("rtogglePassword");
    const toggleConfirmPassword = document.getElementById("toggleConfirmPassword");

    togglePassword?.addEventListener("click", () => {
        const field = document.getElementById("passwordFieldRegister");
        if (field) field.type = field.type === "password" ? "text" : "password";
    });

    toggleConfirmPassword?.addEventListener("click", () => {
        const field = document.getElementById("confirmPasswordField");
        if (field) field.type = field.type === "password" ? "text" : "password";
    });

    // --- Registration Form Validation ---
    registerForm.addEventListener("submit", async (event) => {
        event.preventDefault();

        const name = registerForm.elements.name.value.trim();
        const password = registerForm.elements.password.value;
        const confirmPassword = registerForm.elements.confirm_password.value;

        registerMessage.textContent = "";

        // Password match check
        if (password !== confirmPassword) {
            registerMessage.style.color = "red";
            registerMessage.textContent = "The two passwords do not match.";
            return;
        }

        try {
            // Check if username exists
            const checkResponse = await fetch("/check-username", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ username: name }),
            });
            const checkResult = await checkResponse.json();

            if (checkResult.exists) {
                registerMessage.style.color = "red";
                registerMessage.textContent = "That name is already registered.";
                return;
            }

            // Submit registration
            const registerResponse = await fetch("/register", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ username: name, password }),
            });
            const result = await registerResponse.json();

            if (result.success) {
                registerMessage.style.color = "green";
                registerMessage.textContent = "Your account has been created.";
                registerForm.reset();
            } else {
                registerMessage.style.color = "red";
                registerMessage.textContent = result.message || "Registration was not successful.";
            }
        } catch (error) {
            registerMessage.style.color = "red";
            registerMessage.textContent = "The server could not be reached. Please try again.";
            console.error("Registration request failed:", error);
        }
    });
});
