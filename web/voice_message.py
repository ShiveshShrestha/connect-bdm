import os
import shutil
import tempfile
from pathlib import Path

import ffmpeg
import numpy as np
import speech_recognition as sr
from flask import Blueprint, flash, jsonify, redirect, request, session, url_for
from scipy.fft import fft, ifft
from scipy.io import wavfile

# ---------------- Blueprint ----------------
voice_bp = Blueprint("voice", __name__, template_folder="templates")

# ---------------- Folders ----------------
BASE_DIR = Path(__file__).resolve().parent
INBOX_FOLDER = BASE_DIR / "DeafMuteMan" / "Inbox"
INBOX_FOLDER.mkdir(parents=True, exist_ok=True)


# ---------------- DSP FUNCTIONS ----------------
def pre_emphasis(signal, alpha=0.97):
    """Emphasize rapid changes in an audio signal before noise reduction."""
    signal = np.asarray(signal, dtype=float)
    if signal.size < 2:
        return signal.copy()
    return np.append(signal[0], signal[1:] - alpha * signal[:-1])


def normalize_audio(signal):
    """Scale an audio signal so its highest absolute sample is close to one."""
    signal = np.asarray(signal, dtype=float)
    if signal.size == 0:
        return signal.copy()
    return signal / (np.max(np.abs(signal)) + 1e-10)


def adaptive_spectral_subtraction(signal, frame_size=1024, overlap=512):
    """Reduce steady background noise using frame-based spectral subtraction."""
    signal = np.asarray(signal, dtype=float)
    if signal.size == 0:
        return signal.copy()

    hop = frame_size - overlap
    if hop <= 0:
        raise ValueError("Overlap must be smaller than the frame size.")

    output = np.zeros(len(signal), dtype=float)
    noise_estimate = signal[: min(len(signal), 16000 // 2)]
    noise_fft = fft(noise_estimate, n=frame_size)
    noise_magnitude = np.abs(noise_fft)

    for start in range(0, len(signal), hop):
        frame = signal[start : start + frame_size]
        original_length = len(frame)
        if original_length == 0:
            break
        if original_length < frame_size:
            frame = np.pad(frame, (0, frame_size - original_length))

        frame_fft = fft(frame)
        magnitude = np.abs(frame_fft)
        phase = np.angle(frame_fft)

        noise_magnitude = 0.95 * noise_magnitude + 0.05 * magnitude.min()
        reduced_magnitude = np.maximum(magnitude - noise_magnitude, 0)
        processed_frame = np.real(ifft(reduced_magnitude * np.exp(1j * phase)))

        end = min(start + original_length, len(output))
        output[start:end] += processed_frame[: end - start]

    return normalize_audio(output)


def get_ffmpeg_command():
    """Return an available FFmpeg executable path for the current computer."""
    configured_path = os.getenv("FFMPEG_PATH")
    if configured_path:
        return configured_path

    installed_command = shutil.which("ffmpeg")
    if installed_command:
        return installed_command

    # ---------------- FFmpeg Path ----------------
    return r"C:\Program Files\ffmpeg\bin\ffmpeg.exe"


def convert_webm_to_wav(webm_path, wav_path):
    """Convert a browser-recorded WebM file to mono 16 kHz PCM WAV audio."""
    ffmpeg.input(str(webm_path)).output(
        str(wav_path),
        ar=16000,
        ac=1,
        acodec="pcm_s16le",
    ).run(cmd=get_ffmpeg_command(), overwrite_output=True, quiet=True)


def prepare_audio_for_recognition(wav_path, processed_path):
    """Load, clean, normalize, and save a WAV file for speech recognition."""
    sample_rate, audio_data = wavfile.read(wav_path)

    if audio_data.ndim > 1:
        audio_data = audio_data.mean(axis=1)

    if np.issubdtype(audio_data.dtype, np.integer):
        scale = max(abs(np.iinfo(audio_data.dtype).min), np.iinfo(audio_data.dtype).max)
        audio_data = audio_data.astype(float) / scale
    else:
        audio_data = audio_data.astype(float)

    audio_data = pre_emphasis(audio_data)
    audio_data = adaptive_spectral_subtraction(audio_data)
    audio_data = normalize_audio(audio_data)

    wavfile.write(processed_path, sample_rate, (audio_data * 32767).astype(np.int16))


# ---------------- ROUTES ----------------
@voice_bp.route("/")
def home():
    """Return visitors to the main page because voice tools open in a popup."""
    if "username" not in session:
        flash("Please log in before using voice communication.")
    return redirect(url_for("landingpage"))


@voice_bp.route("/upload_audio", methods=["POST"])
def upload_audio():
    """Process an uploaded recording and return the recognized speech as text."""
    if "username" not in session:
        return jsonify({"error": "Please log in before recording a message."}), 401

    audio_file = request.files.get("audio")
    if not audio_file:
        return jsonify({"error": "No audio recording was received."}), 400

    try:
        with tempfile.TemporaryDirectory(prefix="connect_bdm_") as temp_directory:
            temp_path = Path(temp_directory)
            webm_path = temp_path / "input.webm"
            wav_path = temp_path / "input.wav"
            processed_path = temp_path / "processed.wav"

            audio_file.save(webm_path)
            convert_webm_to_wav(webm_path, wav_path)
            prepare_audio_for_recognition(wav_path, processed_path)

            recognizer = sr.Recognizer()
            with sr.AudioFile(str(processed_path)) as source:
                recorded_audio = recognizer.record(source)

            try:
                text = recognizer.recognize_google(recorded_audio)
            except sr.UnknownValueError:
                text = "I could not understand that recording. Please try again."
            except sr.RequestError as error:
                return jsonify({"error": f"Speech recognition is unavailable: {error}"}), 503

        return jsonify({"text": text})
    except (ffmpeg.Error, OSError, ValueError) as error:
        return jsonify({"error": f"The recording could not be processed: {error}"}), 500


@voice_bp.route("/save_message", methods=["POST"])
def save_message():
    """Save the latest recognized message to the project's inbox text file."""
    if "username" not in session:
        return jsonify({"error": "Please log in before saving a message."}), 401

    data = request.get_json(silent=True) or {}
    text = str(data.get("text", "")).strip()
    if not text:
        return jsonify({"error": "There is no recognized text to save."}), 400

    file_path = INBOX_FOLDER / "recognized_text.txt"
    file_path.write_text(text, encoding="utf-8")

    return jsonify({"status": "saved"})
