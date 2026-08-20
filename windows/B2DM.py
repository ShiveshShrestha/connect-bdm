"""Record speech, clean it, convert it to text, and save the result."""
from __future__ import annotations

import threading
import time
from pathlib import Path

import numpy as np
import pyttsx3
import scipy.io.wavfile as wav
import sounddevice as sd
import speech_recognition as sr
from scipy.fft import fft, ifft

BASE_DIR = Path(__file__).resolve().parent
TEMP_DIR = BASE_DIR / ".runtime"
INBOX_DIR = BASE_DIR / "DeafMuteMan" / "Inbox"

SAMPLE_RATE = 16000
CHANNELS = 1
FRAME_SIZE = 1024
OVERLAP = 512

_recording: list[np.ndarray] = []
_stop_event = threading.Event()
_speech_lock = threading.Lock()


def speak(text: str) -> None:
    """Speak a short message without overlapping another speech job."""
    with _speech_lock:
        engine = pyttsx3.init()
        engine.say(text)
        engine.runAndWait()
        engine.stop()


def pre_emphasis(signal: np.ndarray, alpha: float = 0.97) -> np.ndarray:
    """Boost quiet high-frequency speech before removing noise."""
    if signal.size == 0:
        return signal
    return np.append(signal[0], signal[1:] - alpha * signal[:-1])


def normalize_audio(signal: np.ndarray) -> np.ndarray:
    """Scale audio safely while leaving silence untouched."""
    if signal.size == 0:
        return signal
    return signal / (np.max(np.abs(signal)) + 1e-10)


def adaptive_spectral_subtraction(
    signal: np.ndarray,
    frame_size: int = FRAME_SIZE,
    overlap: int = OVERLAP,
) -> np.ndarray:
    """Reduce steady background noise in overlapping audio frames."""
    if len(signal) < frame_size:
        return normalize_audio(signal)

    hop = frame_size - overlap
    output = np.zeros(len(signal), dtype=np.float64)
    noise_sample = signal[: min(SAMPLE_RATE // 2, len(signal))]
    noise_magnitude = np.abs(fft(noise_sample, n=frame_size))

    for start in range(0, len(signal) - frame_size + 1, hop):
        frame = signal[start : start + frame_size]
        transformed = fft(frame)
        magnitude = np.abs(transformed)
        phase = np.angle(transformed)
        noise_magnitude = 0.95 * noise_magnitude + 0.05 * np.minimum(noise_magnitude, magnitude)
        cleaned_magnitude = np.maximum(magnitude - noise_magnitude, 0)
        cleaned = np.real(ifft(cleaned_magnitude * np.exp(1j * phase)))
        output[start : start + frame_size] += cleaned

    return normalize_audio(output)


def _audio_callback(indata, _frames, _time_info, status) -> None:
    """Collect microphone blocks until recording is stopped."""
    if status:
        print(status)
    if _stop_event.is_set():
        raise sd.CallbackStop()
    _recording.append(indata.copy())


def stop_recording() -> None:
    """Tell the active microphone stream to stop."""
    _stop_event.set()


def start_recording() -> str:
    """Record until stopped, then return the recognised text."""
    _recording.clear()
    _stop_event.clear()
    speak("Listening started. Press K when you have finished speaking.")

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, callback=_audio_callback):
        _stop_event.wait()

    if not _recording:
        raise RuntimeError("Nothing was recorded. Please try again and speak after listening starts.")

    return process_audio()


def process_audio() -> str:
    """Clean the recording, write temporary WAV files, and recognise the speech."""
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    audio_data = np.concatenate(_recording, axis=0).flatten().astype(np.float64)
    processed = adaptive_spectral_subtraction(pre_emphasis(audio_data))

    input_path = TEMP_DIR / "input.wav"
    processed_path = TEMP_DIR / "processed.wav"
    wav.write(str(input_path), SAMPLE_RATE, (normalize_audio(audio_data) * 32767).astype(np.int16))
    wav.write(str(processed_path), SAMPLE_RATE, (normalize_audio(processed) * 32767).astype(np.int16))

    recognizer = sr.Recognizer()
    with sr.AudioFile(str(processed_path)) as source:
        audio = recognizer.record(source)

    try:
        return recognizer.recognize_google(audio)
    except sr.UnknownValueError:
        return "Speech was not clear enough to recognise."
    except sr.RequestError as exc:
        raise RuntimeError(f"Speech recognition could not connect: {exc}") from exc


def save_message(text: str) -> Path:
    """Save the finished text message in the text inbox."""
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
    path = INBOX_DIR / f"message_{timestamp}.txt"
    path.write_text(text, encoding="utf-8")
    return path
