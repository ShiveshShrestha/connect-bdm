let sortAscending = true; // Track ID sorting
const adminBox = document.getElementById("adminUsersBox");

/**
 * Open the administrator's user list and refresh its table.
 */
function openAdminUsersPopup() {
    if (!adminBox) return;

    adminBox.style.display = "block";
    bringToFront(adminBox);
    loadUsers();
    dragElement(adminBox);
}

const adminHeader = document.getElementById("adminUsersBoxHeader");
adminHeader?.addEventListener("click", () => {
    bringToFront(adminBox);
});

const closeAdminButton = document.getElementById("closeAdminUsers");
closeAdminButton?.addEventListener("click", () => {
    if (adminBox) adminBox.style.display = "none";
});

/**
 * Fetch registered users and rebuild the administrator table.
 */
async function loadUsers() {
    const tableBody = document.getElementById("usersTableBody");
    if (!tableBody) return;

    try {
        const response = await fetch("/get_users");
        if (!response.ok) throw new Error("Could not load users.");

        const users = await response.json();

        // Sort users by ID
        users.sort((first, second) => (
            sortAscending ? first.id - second.id : second.id - first.id
        ));

        tableBody.innerHTML = "";
        users.forEach((user) => {
            const row = document.createElement("tr");
            row.innerHTML = `
                <td>${user.id}</td>
                <td>${user.username}</td>
                <td>
                    <button class="delete-user" data-id="${user.id}">Remove</button>
                </td>
            `;
            tableBody.appendChild(row);
        });

        attachDeleteEvents();
    } catch (error) {
        console.error("Error loading users:", error);
    }
}

/**
 * Attach the delete request to each user row currently displayed.
 */
function attachDeleteEvents() {
    document.querySelectorAll(".delete-user").forEach((button) => {
        button.addEventListener("click", async function () {
            const userId = this.dataset.id;
            if (!confirm("Remove this user account?")) return;

            try {
                const response = await fetch(`/delete_user/${userId}`, { method: "DELETE" });
                const data = await response.json();
                alert(data.message);

                if (response.ok) await loadUsers();
            } catch (error) {
                console.error("Error deleting user:", error);
            }
        });
    });
}

// ===== Drag Functionality =====
/**
 * Allow a popup to be repositioned by dragging its header.
 * @param {HTMLElement} element - Popup that should become draggable.
 */
function dragElement(element) {
    if (!element || element.dataset.dragReady === "true") return;

    const header = document.getElementById(`${element.id}Header`);
    let pos1 = 0;
    let pos2 = 0;
    let pos3 = 0;
    let pos4 = 0;

    element.dataset.dragReady = "true";
    if (header) header.onmousedown = dragMouseDown;
    else element.onmousedown = dragMouseDown;

    /** Start tracking the pointer position. */
    function dragMouseDown(event) {
        const currentEvent = event || window.event;
        currentEvent.preventDefault();
        pos3 = currentEvent.clientX;
        pos4 = currentEvent.clientY;
        document.onmouseup = closeDragElement;
        document.onmousemove = elementDrag;
    }

    /** Move the popup by the same distance as the pointer. */
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

    /** Stop listening for pointer movement. */
    function closeDragElement() {
        document.onmouseup = null;
        document.onmousemove = null;
    }
}

const adminModeButton = document.getElementById("adminMode");
adminModeButton?.addEventListener("click", openAdminUsersPopup);
