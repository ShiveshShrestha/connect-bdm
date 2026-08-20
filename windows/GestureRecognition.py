"""Read hand signs from the camera with the CNN or KNN model."""
from __future__ import annotations

import argparse
import os
import time
import tkinter as tk
from collections import Counter, deque
from pathlib import Path
from tkinter import messagebox, ttk

from model_utils import create_predictor
from ui_common import (
    ScrollableFrame,
    configure_ttk,
    fit_window,
    make_brand,
    maximize_window,
    theme_values,
)

BASE_DIR = Path(__file__).resolve().parent
VOICE_SAVE_DIR = BASE_DIR / "BlindMan" / "Inbox"
SMOOTHING_WINDOW = 8
MIN_HAND_SIZE = 0.12
AUTO_ADD_HOLD_SECONDS = 1.5


class GestureRecognitionApp:
    """Camera window for building a message from hand signs."""

    def __init__(self, root: tk.Tk, model_name: str, theme_name: str = "light") -> None:
        """Load the chosen model, build the window, and open the camera."""
        self.root = root
        self.model_key = model_name.lower()
        self.model_name = model_name.upper()
        self.theme_name = theme_name if theme_name in {"light", "dark"} else "light"

        self.root.title(f"Connect B-DM - Sign recognition ({self.model_name})")
        fit_window(self.root, 1180, 760, 820, 560)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(80, lambda: maximize_window(self.root))

        signal_value = os.environ.get("CONNECT_BDM_HOME_SIGNAL", "").strip()
        self.home_signal_path = Path(signal_value) if signal_value else None
        self.cap = None
        self.hands = None
        self.after_id: str | None = None

        if not self.load_runtime_dependencies():
            return

        VOICE_SAVE_DIR.mkdir(parents=True, exist_ok=True)
        try:
            self.predictor = create_predictor(self.model_key)
        except Exception as exc:
            messagebox.showerror(
                "Model could not open",
                f"The {self.model_name} model could not be loaded.\n\n{exc}",
            )
            self.root.destroy()
            return

        self.prediction_queue: deque[tuple[str, float]] = deque(maxlen=SMOOTHING_WINDOW)
        self.current_prediction: str | None = None
        self.current_confidence = 0.0
        self.last_add_time = 0.0
        self.auto_candidate: str | None = None
        self.auto_candidate_started = 0.0

        self.confidence_threshold = tk.DoubleVar(value=0.85 if self.model_key == "cnn" else 0.80)
        self.auto_add = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="Hold one hand clearly in front of the camera.")
        self.prediction_var = tk.StringVar(value="—")
        self.confidence_var = tk.StringVar(value="0% confidence")
        self.countdown_var = tk.StringVar(value="Auto-add is off")

        self.tts = self.pyttsx3.init()
        self.configure_window()
        self.build_gui()
        self.bind_shortcuts()
        self.start_camera()

    @property
    def colors(self) -> dict[str, str]:
        """Get the colours for the current theme."""
        return theme_values(self.theme_name)

    def load_runtime_dependencies(self) -> bool:
        """Load the camera and image libraries when this window starts."""
        try:
            import cv2
            import mediapipe as mp
            import numpy as np
            import pyttsx3
            from PIL import Image, ImageTk
        except Exception as exc:
            messagebox.showerror(
                "Gesture setup problem",
                "The camera tools could not be started.\n\n"
                f"{exc}\n\n"
                "Open this project folder in Anaconda Prompt and run:\n"
                "python -m pip install --upgrade --force-reinstall -r requirements.txt",
            )
            self.root.destroy()
            return False

        self.cv2 = cv2
        self.mp = mp
        self.np = np
        self.pyttsx3 = pyttsx3
        self.Image = Image
        self.ImageTk = ImageTk
        return True

    def configure_window(self) -> None:
        """Apply the selected theme and shared widget styles."""
        self.root.configure(bg=self.colors["bg"])
        configure_ttk(self.root, self.theme_name)

    def bind_shortcuts(self) -> None:
        """Set Alt, Ctrl+H, and Esc as the window shortcuts."""
        self.root.bind_all("<KeyPress-Alt_L>", self.add_current_prediction)
        self.root.bind_all("<KeyPress-Alt_R>", self.add_current_prediction)
        self.root.bind("<Escape>", lambda _event: self.close())
        self.root.bind_all("<Control-h>", self.return_home)
        self.root.bind_all("<Control-H>", self.return_home)

    def start_camera(self) -> None:
        """Open the first webcam and start reading its frames."""
        try:
            self.mp_hands = self.mp.solutions.hands
            self.hands = self.mp_hands.Hands(
                static_image_mode=False,
                max_num_hands=1,
                min_detection_confidence=0.65,
                min_tracking_confidence=0.65,
            )
            self.drawer = self.mp.solutions.drawing_utils

            backend = self.cv2.CAP_DSHOW if os.name == "nt" else 0
            self.cap = self.cv2.VideoCapture(0, backend)
            if not self.cap.isOpened() and os.name == "nt":
                self.cap.release()
                self.cap = self.cv2.VideoCapture(0)
            if not self.cap.isOpened():
                raise RuntimeError("The webcam did not open. Close other camera apps and try again.")

            self.cap.set(self.cv2.CAP_PROP_FRAME_WIDTH, 800)
            self.cap.set(self.cv2.CAP_PROP_FRAME_HEIGHT, 600)
            self.update_frame()
        except Exception as exc:
            messagebox.showerror("Camera problem", str(exc))
            self.close()

    def build_gui(self) -> None:
        """Build the header, camera preview, message box, and settings."""
        for child in self.root.winfo_children():
            child.destroy()

        self.build_header()
        colors = self.colors
        paned = tk.PanedWindow(
            self.root,
            orient="horizontal",
            bg=colors["bg"],
            bd=0,
            sashwidth=7,
            sashrelief="flat",
            showhandle=False,
        )
        paned.pack(fill="both", expand=True, padx=18, pady=18)

        camera_card = self.build_camera_card(paned)
        controls_scroll = ScrollableFrame(paned, bg=colors["bg"])
        controls_scroll.activate_scroll()
        self.build_control_panel(controls_scroll.inner)

        paned.add(camera_card, minsize=430, stretch="always")
        paned.add(controls_scroll, minsize=320, stretch="never", width=390)

    def build_header(self) -> None:
        """Build the header with the logo, title, model, and theme switch."""
        colors = self.colors
        header = tk.Frame(
            self.root,
            bg=colors["surface"],
            highlightbackground=colors["border"],
            highlightthickness=1,
        )
        header.pack(fill="x")

        brand = make_brand(header, colors, "Live sign recognition")
        brand.pack(side="left", padx=22, pady=13)

        actions = tk.Frame(header, bg=colors["surface"])
        actions.pack(side="right", padx=18, pady=12)
        tk.Label(
            actions,
            text=f"{self.model_name} model",
            font=("Segoe UI", 10, "bold"),
            bg=colors["accent"],
            fg=colors["accent_text"],
            padx=10,
            pady=7,
        ).pack(side="left", padx=(0, 8))
        ttk.Button(
            actions,
            text="Use dark theme" if self.theme_name == "light" else "Use light theme",
            style="Secondary.TButton",
            command=self.toggle_theme,
        ).pack(side="left")

    def build_camera_card(self, parent: tk.Widget) -> tk.Frame:
        """Create the camera preview area."""
        colors = self.colors
        card = self.make_card(parent)
        tk.Label(
            card,
            text="Camera",
            font=("Segoe UI", 11, "bold"),
            bg=colors["surface"],
            fg=colors["text"],
        ).pack(anchor="w", padx=16, pady=(14, 8))
        self.video_label = tk.Label(
            card,
            bg=colors["camera"],
            fg=colors["muted"],
            text="Opening camera...",
            font=("Segoe UI", 12),
        )
        self.video_label.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        return card

    def build_control_panel(self, parent: tk.Widget) -> None:
        """Add the prediction, message, settings, and help cards on the right."""
        parent.grid_columnconfigure(0, weight=1)
        self.build_prediction_card(parent)
        self.build_message_card(parent)
        self.build_settings_card(parent)
        self.build_status_card(parent)

    def build_prediction_card(self, parent: tk.Widget) -> None:
        """Show the current letter, confidence, and auto-add countdown."""
        colors = self.colors
        card = self.make_card(parent)
        card.pack(fill="x", pady=(0, 12))
        tk.Label(
            card,
            text="Detected sign",
            font=("Segoe UI", 11, "bold"),
            bg=colors["surface"],
            fg=colors["text"],
        ).pack(anchor="w", padx=18, pady=(16, 3))
        tk.Label(
            card,
            textvariable=self.prediction_var,
            font=("Segoe UI", 48, "bold"),
            bg=colors["surface"],
            fg=colors["text"],
        ).pack()
        tk.Label(
            card,
            textvariable=self.confidence_var,
            font=("Segoe UI", 11, "bold"),
            bg=colors["surface"],
            fg=colors["success"],
        ).pack(pady=(0, 4))
        tk.Label(
            card,
            textvariable=self.countdown_var,
            font=("Segoe UI", 13, "bold"),
            bg=colors["surface"],
            fg=colors["text"],
        ).pack(pady=(0, 15))

    def build_message_card(self, parent: tk.Widget) -> None:
        """Create the message box and its add, edit, and save buttons."""
        colors = self.colors
        card = self.make_card(parent)
        card.pack(fill="x", pady=(0, 12))
        tk.Label(
            card,
            text="Your message",
            font=("Segoe UI", 11, "bold"),
            bg=colors["surface"],
            fg=colors["text"],
        ).pack(anchor="w", padx=18, pady=(16, 8))

        self.text_box = tk.Text(
            card,
            height=8,
            wrap="word",
            font=("Segoe UI", 14),
            bg=colors["surface_alt"],
            fg=colors["text"],
            insertbackground=colors["text"],
            relief="flat",
            padx=11,
            pady=9,
        )
        self.text_box.pack(fill="x", padx=18)

        first_row = tk.Frame(card, bg=colors["surface"])
        first_row.pack(fill="x", padx=18, pady=(12, 5))
        for column in range(3):
            first_row.grid_columnconfigure(column, weight=1)
        ttk.Button(
            first_row,
            text="Add sign (Alt)",
            style="Primary.TButton",
            command=self.add_current_prediction,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 4), pady=3)
        ttk.Button(
            first_row,
            text="Add space",
            style="Secondary.TButton",
            command=lambda: self.insert_text(" "),
        ).grid(row=0, column=1, sticky="ew", padx=4, pady=3)
        ttk.Button(
            first_row,
            text="Delete last",
            style="Secondary.TButton",
            command=self.delete_last,
        ).grid(row=0, column=2, sticky="ew", padx=(4, 0), pady=3)

        second_row = tk.Frame(card, bg=colors["surface"])
        second_row.pack(fill="x", padx=18, pady=(0, 12))
        for column in range(3):
            second_row.grid_columnconfigure(column, weight=1)
        ttk.Button(
            second_row,
            text="Save as audio",
            style="Secondary.TButton",
            command=self.save_voice,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 4), pady=3)
        ttk.Button(
            second_row,
            text="Clear message",
            style="Secondary.TButton",
            command=self.clear_text,
        ).grid(row=0, column=1, sticky="ew", padx=4, pady=3)
        ttk.Button(
            second_row,
            text="Close window",
            style="Secondary.TButton",
            command=self.close,
        ).grid(row=0, column=2, sticky="ew", padx=(4, 0), pady=3)

    def build_settings_card(self, parent: tk.Widget) -> None:
        """Add the optional automatic sign entry and confidence control."""
        colors = self.colors
        card = self.make_card(parent)
        card.pack(fill="x", pady=(0, 12))
        tk.Label(
            card,
            text="Recognition settings",
            font=("Segoe UI", 11, "bold"),
            bg=colors["surface"],
            fg=colors["text"],
        ).pack(anchor="w", padx=18, pady=(16, 8))
        ttk.Checkbutton(
            card,
            text="Add signs automatically when held steady",
            variable=self.auto_add,
            style="App.TCheckbutton",
            command=self.auto_add_toggled,
        ).pack(anchor="w", padx=18, pady=(0, 10))

        threshold_row = tk.Frame(card, bg=colors["surface"])
        threshold_row.pack(fill="x", padx=18, pady=(0, 12))
        tk.Label(
            threshold_row,
            text="Minimum confidence",
            font=("Segoe UI", 9),
            bg=colors["surface"],
            fg=colors["muted"],
        ).pack(anchor="w")
        tk.Scale(
            threshold_row,
            from_=0.50,
            to=1.00,
            resolution=0.05,
            orient="horizontal",
            variable=self.confidence_threshold,
            bg=colors["surface"],
            fg=colors["text"],
            troughcolor=colors["surface_alt"],
            highlightthickness=0,
            activebackground=colors["accent"],
        ).pack(fill="x")

    def build_status_card(self, parent: tk.Widget) -> None:
        """Show a live hint and the three gesture-window shortcuts."""
        colors = self.colors
        card = self.make_card(parent)
        card.pack(fill="x", pady=(0, 18))
        tk.Label(
            card,
            textvariable=self.status_var,
            font=("Segoe UI", 10),
            bg=colors["surface"],
            fg=colors["text"],
            wraplength=330,
            justify="left",
        ).pack(anchor="w", padx=18, pady=(15, 8))
        tk.Label(
            card,
            text="Alt adds the sign • Ctrl+H goes Home • Esc closes this window",
            font=("Segoe UI", 9),
            bg=colors["surface"],
            fg=colors["muted"],
            wraplength=330,
            justify="left",
        ).pack(anchor="w", padx=18, pady=(0, 15))

    def make_card(self, parent: tk.Widget) -> tk.Frame:
        """Return a simple bordered panel that matches the active theme."""
        colors = self.colors
        return tk.Frame(
            parent,
            bg=colors["surface"],
            highlightbackground=colors["border"],
            highlightthickness=1,
        )

    def toggle_theme(self) -> None:
        """Switch themes and keep the message already typed by the user."""
        current_text = self.text_box.get("1.0", "end-1c") if hasattr(self, "text_box") else ""
        self.theme_name = "dark" if self.theme_name == "light" else "light"
        self.configure_window()
        self.build_gui()
        if current_text:
            self.text_box.insert("1.0", current_text)

    def landmarks_to_array(self, hand_landmarks):
        """Flatten MediaPipe's 21 x/y/z hand points into the model's 63 values."""
        return self.np.asarray(
            [value for landmark in hand_landmarks.landmark for value in (landmark.x, landmark.y, landmark.z)],
            dtype=self.np.float32,
        )

    def update_frame(self) -> None:
        """Read one camera frame, predict a sign, update the GUI, and schedule the next frame."""
        if not self.cap or not self.cap.isOpened() or not self.root.winfo_exists():
            return

        ok, frame = self.cap.read()
        if not ok:
            self.status_var.set("The camera missed a frame. Trying again...")
            self.after_id = self.root.after(120, self.update_frame)
            return

        frame = self.cv2.flip(frame, 1)
        rgb = self.cv2.cvtColor(frame, self.cv2.COLOR_BGR2RGB)
        results = self.hands.process(rgb)
        frame_prediction: tuple[str, float] | None = None

        if results.multi_hand_landmarks:
            hand = results.multi_hand_landmarks[0]
            self.drawer.draw_landmarks(frame, hand, self.mp_hands.HAND_CONNECTIONS)
            xs = [landmark.x for landmark in hand.landmark]
            ys = [landmark.y for landmark in hand.landmark]
            hand_size = max(max(xs) - min(xs), max(ys) - min(ys))

            if hand_size >= MIN_HAND_SIZE:
                prediction = self.predictor.predict(self.landmarks_to_array(hand))
                frame_prediction = (prediction.label, prediction.confidence)
                self.prediction_queue.append(frame_prediction)
            else:
                self.reset_prediction("Move your hand a little closer to the camera.")
        else:
            self.reset_prediction("Hold one hand clearly in front of the camera.")

        self.stabilize_prediction(frame_prediction)
        self.draw_overlay(frame)
        self.show_frame(frame)
        self.after_id = self.root.after(30, self.update_frame)

    def reset_prediction(self, message: str) -> None:
        """Clear the current result when no useful hand sign is visible."""
        self.prediction_queue.clear()
        self.current_prediction = None
        self.current_confidence = 0.0
        self.auto_candidate = None
        self.prediction_var.set("—")
        self.confidence_var.set("0% confidence")
        self.countdown_var.set("Waiting for a steady sign" if self.auto_add.get() else "Auto-add is off")
        self.status_var.set(message)

    def stabilize_prediction(self, frame_prediction: tuple[str, float] | None) -> None:
        """Use several recent frames so one shaky prediction does not become a letter."""
        if frame_prediction is None:
            self.auto_candidate = None
            self.countdown_var.set("Waiting for a steady sign" if self.auto_add.get() else "Auto-add is off")
            return
        if len(self.prediction_queue) < max(4, SMOOTHING_WINDOW // 2):
            self.auto_candidate = None
            self.countdown_var.set("Checking the sign..." if self.auto_add.get() else "Auto-add is off")
            return

        labels = [label for label, _confidence in self.prediction_queue]
        best_label, vote_count = Counter(labels).most_common(1)[0]
        matching_confidence = [
            confidence for label, confidence in self.prediction_queue if label == best_label
        ]
        confidence = float(sum(matching_confidence) / len(matching_confidence))
        vote_ratio = vote_count / len(self.prediction_queue)

        self.current_prediction = best_label
        self.current_confidence = confidence
        self.prediction_var.set(best_label.upper())
        self.confidence_var.set(f"{confidence * 100:.1f}% confidence")

        if confidence >= self.confidence_threshold.get() and vote_ratio >= 0.60:
            self.status_var.set("Sign is steady. Press Alt to add it.")
            self.handle_auto_add(best_label)
        else:
            self.status_var.set("Hold the sign still for a moment.")
            self.auto_candidate = None
            self.countdown_var.set("Waiting for a steady sign" if self.auto_add.get() else "Auto-add is off")

    def auto_add_toggled(self) -> None:
        """Reset the countdown when automatic adding is turned on or off."""
        self.auto_candidate = None
        self.auto_candidate_started = 0.0
        self.countdown_var.set("Waiting for a steady sign" if self.auto_add.get() else "Auto-add is off")

    def handle_auto_add(self, label: str) -> None:
        """Count down while a sign stays steady, then add it."""
        if not self.auto_add.get():
            self.auto_candidate = None
            self.countdown_var.set("Auto-add is off")
            return

        now = time.time()
        if self.auto_candidate != label:
            self.auto_candidate = label
            self.auto_candidate_started = now

        remaining = max(0.0, AUTO_ADD_HOLD_SECONDS - (now - self.auto_candidate_started))
        if remaining > 0:
            self.countdown_var.set(f"Adding {label.upper()} in {remaining:.1f}s")
            self.status_var.set(f"Keep {label.upper()} still for {remaining:.1f} more seconds.")
            return

        if now - self.last_add_time >= 1.2:
            self.add_current_prediction(require_threshold=True)
            self.auto_candidate_started = now
            self.countdown_var.set(f"Added {label.upper()}. Keep holding to add it again.")

    def draw_overlay(self, frame) -> None:
        """Draw the prediction and countdown on the camera frame."""
        if not self.current_prediction:
            return

        result_text = (
            f"{self.model_name}: {self.current_prediction.upper()}  "
            f"{self.current_confidence * 100:.1f}%"
        )
        overlay_bottom = 94 if self.auto_add.get() else 58
        self.cv2.rectangle(frame, (12, 12), (570, overlay_bottom), (15, 15, 15), -1)
        self.cv2.putText(
            frame,
            result_text,
            (24, 45),
            self.cv2.FONT_HERSHEY_SIMPLEX,
            0.82,
            (245, 245, 245),
            2,
        )
        if self.auto_add.get():
            self.cv2.putText(
                frame,
                self.countdown_var.get(),
                (24, 79),
                self.cv2.FONT_HERSHEY_SIMPLEX,
                0.72,
                (245, 245, 245),
                2,
            )

    def show_frame(self, frame) -> None:
        """Fit the latest camera frame inside the preview."""
        if not hasattr(self, "video_label") or not self.video_label.winfo_exists():
            return

        rgb = self.cv2.cvtColor(frame, self.cv2.COLOR_BGR2RGB)
        image = self.Image.fromarray(rgb)
        width = self.video_label.winfo_width()
        height = self.video_label.winfo_height()
        if width < 100:
            width = 720
        if height < 100:
            height = 540
        image.thumbnail((max(240, width - 8), max(180, height - 8)), self.Image.Resampling.LANCZOS)
        photo = self.ImageTk.PhotoImage(image)
        self.video_label.configure(image=photo, text="")
        self.video_label.image = photo

    def add_current_prediction(self, _event=None, require_threshold: bool = False):
        """Add the current sign from Alt, the button, or automatic mode."""
        if not self.current_prediction:
            self.status_var.set("No sign is ready to add yet.")
            return "break"
        if require_threshold and self.current_confidence < self.confidence_threshold.get():
            self.status_var.set("The sign is not clear enough for automatic adding.")
            return "break"

        now = time.time()
        if now - self.last_add_time < 0.35:
            return "break"
        self.last_add_time = now

        label = self.current_prediction.lower()
        if label == "space":
            self.insert_text(" ")
        elif label == "del":
            self.delete_last()
        elif label != "nothing":
            self.insert_text(label.upper())
        self.status_var.set(f"Added {label.upper()}.")
        return "break"

    def insert_text(self, value: str) -> None:
        """Insert a letter or space at the cursor."""
        self.text_box.insert("insert", value)
        self.text_box.focus_set()

    def delete_last(self) -> None:
        """Remove the last character from the message."""
        content = self.text_box.get("1.0", "end-1c")
        if content:
            self.text_box.delete("1.0", "end")
            self.text_box.insert("1.0", content[:-1])

    def clear_text(self) -> None:
        """Clear the message box and update the status."""
        self.text_box.delete("1.0", "end")
        self.status_var.set("Message cleared.")

    def save_voice(self) -> None:
        """Save the finished message as a WAV file in the audio inbox."""
        message = self.text_box.get("1.0", "end-1c").strip()
        if not message:
            messagebox.showwarning("Nothing to save", "Add or type a message first.")
            return

        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        file_path = VOICE_SAVE_DIR / f"voice_{timestamp}.wav"
        try:
            self.tts.save_to_file(message, str(file_path))
            self.tts.runAndWait()
            messagebox.showinfo("Audio saved", f"Your audio was saved here:\n{file_path}")
        except Exception as exc:
            messagebox.showerror("Audio could not be saved", str(exc))

    def return_home(self, _event=None):
        """Ask the main app to close extra windows and return Home."""
        if self.home_signal_path is not None:
            try:
                self.home_signal_path.parent.mkdir(parents=True, exist_ok=True)
                self.home_signal_path.write_text(str(time.time()), encoding="utf-8")
            except OSError:
                pass
        self.close()
        return "break"

    def close(self) -> None:
        """Stop the camera and close the window cleanly."""
        if self.after_id and self.root.winfo_exists():
            try:
                self.root.after_cancel(self.after_id)
            except tk.TclError:
                pass
            self.after_id = None
        if self.cap is not None and self.cap.isOpened():
            self.cap.release()
        if self.hands is not None:
            try:
                self.hands.close()
            except Exception:
                pass
        if hasattr(self, "cv2"):
            self.cv2.destroyAllWindows()
        try:
            self.root.destroy()
        except tk.TclError:
            pass


def parse_args() -> argparse.Namespace:
    """Read the chosen model and theme from the launcher command."""
    parser = argparse.ArgumentParser(description="Open Connect B-DM sign recognition.")
    parser.add_argument("--model", choices=("cnn", "knn"), default="cnn")
    parser.add_argument("--theme", choices=("light", "dark"), default="light")
    return parser.parse_args()


def main() -> None:
    """Create the gesture window and keep it open until the user closes it."""
    args = parse_args()
    root = tk.Tk()
    GestureRecognitionApp(root, args.model, args.theme)
    try:
        root.mainloop()
    except tk.TclError:
        pass


if __name__ == "__main__":
    main()
