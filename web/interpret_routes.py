# interpret_routes.py
import io

from flask import Blueprint, jsonify, request, send_file
from PIL import Image, ImageDraw, ImageFont

interpret_bp = Blueprint("interpret", __name__)

# -------------------- CONFIG --------------------
IMAGE_SIZE = (380, 380)
TEXT_FONT_SIZE = 40
MAX_WORD_LENGTH = 60


# -------------------- UTILITIES --------------------
def load_font(size=TEXT_FONT_SIZE):
    """Load Arial when available and fall back to Pillow's default font."""
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def generate_text_image(text: str) -> io.BytesIO:
    """Create an in-memory PNG containing a word centered on a white background."""
    image = Image.new("RGB", IMAGE_SIZE, "white")
    draw = ImageDraw.Draw(image)
    font = load_font(TEXT_FONT_SIZE)

    bounding_box = draw.textbbox((0, 0), text, font=font)
    text_width = bounding_box[2] - bounding_box[0]
    text_height = bounding_box[3] - bounding_box[1]
    text_position = (
        (IMAGE_SIZE[0] - text_width) / 2,
        (IMAGE_SIZE[1] - text_height) / 2,
    )

    draw.text(text_position, text, fill="black", font=font)

    image_buffer = io.BytesIO()
    image.save(image_buffer, format="PNG")
    image_buffer.seek(0)
    return image_buffer


# -------------------- ROUTES --------------------
@interpret_bp.route("/generate_word_image")
def generate_word_image():
    """Return a generated PNG for the word supplied in the query string."""
    word = request.args.get("word", "").strip()

    if not word:
        return jsonify({"error": "No word was provided."}), 400

    if len(word) > MAX_WORD_LENGTH:
        return jsonify({"error": "The word is too long to display."}), 400

    image_buffer = generate_text_image(word)
    return send_file(image_buffer, mimetype="image/png")
