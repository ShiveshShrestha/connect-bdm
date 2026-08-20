import io
import os

import mysql.connector
from flask import Flask, jsonify, redirect, render_template, request, send_file, session, url_for
from gtts import gTTS

from interpret_routes import interpret_bp
from voice_message import voice_bp


app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "connect-bdm-local-key")

# Blueprint registration
app.register_blueprint(interpret_bp, url_prefix="/interpret")
app.register_blueprint(voice_bp, url_prefix="/voice")


# ---------------------- MySQL Config ----------------------
db_config = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "flask_db"),
}


# ---------------------- Helper function ----------------------
def get_db_connection():
    """Open and return a new connection to the project's MySQL database."""
    return mysql.connector.connect(**db_config)


def get_request_data():
    """Return the current JSON request body as a dictionary."""
    return request.get_json(silent=True) or {}


def get_username_by_id(user_id):
    """Look up a user's username by database ID and return it when found."""
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("SELECT username FROM users WHERE id=%s", (user_id,))
        result = cursor.fetchone()
        return result[0] if result else None
    finally:
        cursor.close()
        connection.close()


# ---------------------- Routes ----------------------
@app.route("/landing")
def landingpage():
    """Render the main Connect B-DM landing page."""
    return render_template("landingpage.html")


@app.route("/")
def home():
    """Redirect the root URL to the landing page."""
    return redirect(url_for("landingpage"))


# ---------------------- Login ----------------------------
@app.route("/login", methods=["POST"])
def login():
    """Validate user or administrator credentials and start a login session."""
    data = get_request_data()
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))
    login_type = data.get("login_type", "user")

    if not username or not password:
        return jsonify({"success": False, "message": "Enter both your name and password."}), 400

    table_name = "admin_info" if login_type == "admin" else "users"
    role = "admin" if login_type == "admin" else "user"

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(
            f"SELECT username FROM {table_name} WHERE username=%s AND password=%s",
            (username, password),
        )
        user = cursor.fetchone() #store first row returned by sql query to user  here.
    finally:
        cursor.close()
        connection.close()

    if not user:
        account_name = "administrator" if role == "admin" else "user"
        return jsonify({"success": False, "message": f"The {account_name} name or password is incorrect."})

    session["username"] = user["username"]
    session["role"] = role  # IMPORTANT
    return jsonify({"success": True})


# ---------------------- Login out  ----------------------------
@app.route("/logout")
def logout():
    """Clear the active session and return the visitor to the landing page."""
    session.clear()
    return redirect(url_for("landingpage"))


# ---------------------- Registration --------------------------
@app.route("/check-username", methods=["POST"])
def check_username():
    """Check whether a requested username is already present in the users table."""
    data = get_request_data()
    username = str(data.get("username", "")).strip()

    if not username:
        return jsonify({"exists": False, "message": "Enter a name first."}), 400

    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("SELECT id FROM users WHERE username=%s", (username,))
        exists = cursor.fetchone() is not None
    finally:
        cursor.close()
        connection.close()

    return jsonify({"exists": exists})


@app.route("/register", methods=["POST"])
def register():
    """Create a new user account after checking that the username is available."""
    data = get_request_data()
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))

    if not username or not password:
        return jsonify({"success": False, "message": "A name and password are required."}), 400

    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        # Check if username exists
        cursor.execute("SELECT id FROM users WHERE username=%s", (username,))
        if cursor.fetchone():
            return jsonify({"success": False, "message": "That name is already registered."})

        # Insert new user
        cursor.execute(
            "INSERT INTO users (username, password) VALUES (%s, %s)",
            (username, password),
        )
        connection.commit()
    finally:
        cursor.close()
        connection.close()

    return jsonify({"success": True})


@app.route("/generate-voice", methods=["POST"])
def generate_voice():
    """Convert submitted text to an MP3 stream using Google Text-to-Speech."""
    data = get_request_data()
    text = str(data.get("text", "")).strip()

    if not text:
        return jsonify({"error": "There is no text to read."}), 400

    tts = gTTS(text=text, lang="en")
    audio_buffer = io.BytesIO()
    tts.write_to_fp(audio_buffer)
    audio_buffer.seek(0)

    return send_file(
        audio_buffer,
        mimetype="audio/mpeg",
        as_attachment=False,  # important: for streaming
        download_name="voice.mp3",
    )


@app.route("/admin/users")
def admin_users():
    """Render the user-management view for an authenticated administrator."""
    if session.get("role") != "admin":
        return "Unauthorized", 403

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("SELECT id, username FROM users ORDER BY id")
        users = cursor.fetchall()
    finally:
        cursor.close()
        connection.close()

    return render_template("admin_users.html", users=users)


@app.route("/get_users")
def get_users():
    """Return registered users as JSON for the administrator popup."""
    if session.get("role") != "admin":
        return jsonify([]), 403

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("SELECT id, username FROM users ORDER BY id")
        users = cursor.fetchall()
    finally:
        cursor.close()
        connection.close()

    return jsonify(users)


@app.route("/delete_user/<int:user_id>", methods=["DELETE"])
def delete_user(user_id):
    """Delete a user account while preventing an administrator from deleting themselves."""
    if session.get("role") != "admin":
        return jsonify({"message": "Unauthorized"}), 403

    if session.get("username") == get_username_by_id(user_id):
        return jsonify({"message": "You cannot delete your own account."}), 403

    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("DELETE FROM users WHERE id=%s", (user_id,))
        connection.commit()
        deleted = cursor.rowcount > 0
    finally:
        cursor.close()
        connection.close()

    if not deleted:
        return jsonify({"message": "The selected user was not found."}), 404

    return jsonify({"message": "User removed successfully."})


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "true").lower() == "true")
