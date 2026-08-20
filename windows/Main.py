"""Start Connect B-DM and manage its main pages and shortcuts."""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Callable

from ui_common import ScrollableFrame, configure_ttk, fit_window, make_brand, theme_values

BASE_DIR = Path(__file__).resolve().parent


class ConnectBDMApp(tk.Tk):
    """Main window for the voice, sign, and text tools."""

    def __init__(self) -> None:
        """Set up the main window and keep track of any tools it opens."""
        super().__init__()
        self.title("Connect B-DM")
        fit_window(self, 1060, 720, 760, 540)

        self.theme_name = "light"
        self.current_page = "home"
        self.selected_model = tk.StringVar(value="cnn")
        self.frames: dict[str, Page] = {}
        self.child_processes: list[subprocess.Popen] = []

        runtime_dir = BASE_DIR / ".runtime"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        self.home_signal_path = runtime_dir / f"home_request_{os.getpid()}.signal"
        self.home_signal_path.unlink(missing_ok=True)

        self.build_window()
        self.bind_shortcuts()
        self.protocol("WM_DELETE_WINDOW", self.close_app)
        self.after(200, self.poll_home_signal)

    @property
    def colors(self) -> dict[str, str]:
        """Get the colours for the active theme."""
        return theme_values(self.theme_name)

    def build_window(self) -> None:
        """Draw the header and main pages again after a theme change."""
        for child in self.winfo_children():
            child.destroy()

        colors = self.colors
        self.configure(bg=colors["bg"])
        configure_ttk(self, self.theme_name)
        self.build_header()

        content = tk.Frame(self, bg=colors["bg"])
        content.pack(fill="both", expand=True)
        content.grid_rowconfigure(0, weight=1)
        content.grid_columnconfigure(0, weight=1)

        self.frames = {
            "home": HomePage(content, self),
            "blind": VoicePage(content, self),
            "deaf": GesturePage(content, self),
        }
        for frame in self.frames.values():
            frame.grid(row=0, column=0, sticky="nsew")

        self.show_page(self.current_page)

    def build_header(self) -> None:
        """Build the top bar with the logo, title, theme switch, and navigation."""
        colors = self.colors
        header = tk.Frame(
            self,
            bg=colors["surface"],
            highlightbackground=colors["border"],
            highlightthickness=1,
        )
        header.pack(fill="x")

        top_row = tk.Frame(header, bg=colors["surface"])
        top_row.pack(fill="x")
        brand = make_brand(top_row, colors, "Voice, text, and sign tools in one place.")
        brand.pack(side="left", padx=22, pady=(12, 8))

        ttk.Button(
            top_row,
            text="Use dark theme" if self.theme_name == "light" else "Use light theme",
            style="Secondary.TButton",
            command=self.toggle_theme,
        ).pack(side="right", padx=18, pady=15)

        navigation = tk.Frame(header, bg=colors["surface"])
        navigation.pack(fill="x", padx=18, pady=(0, 12))
        for column in range(3):
            navigation.grid_columnconfigure(column, weight=1)

        self.make_nav_button(navigation, "Home", "home").grid(
            row=0, column=0, sticky="ew", padx=(0, 4)
        )
        self.make_nav_button(navigation, "Voice to text", "blind").grid(
            row=0, column=1, sticky="ew", padx=4
        )
        self.make_nav_button(navigation, "Sign to voice", "deaf").grid(
            row=0, column=2, sticky="ew", padx=(4, 0)
        )

    def make_nav_button(self, parent: tk.Widget, text: str, page: str) -> ttk.Button:
        """Make a navigation button for one page."""
        return ttk.Button(
            parent,
            text=text,
            style="Secondary.TButton",
            command=lambda: self.show_page(page),
        )

    def bind_shortcuts(self) -> None:
        """Set the keyboard shortcuts used across the main window."""
        self.bind_all("<KeyPress-j>", self.start_voice_hotkey)
        self.bind_all("<KeyPress-J>", self.start_voice_hotkey)
        self.bind_all("<KeyPress-k>", self.stop_voice_hotkey)
        self.bind_all("<KeyPress-K>", self.stop_voice_hotkey)
        self.bind_all("<Control-s>", self.save_voice_hotkey)
        self.bind_all("<Control-S>", self.save_voice_hotkey)
        self.bind_all("<Control-h>", self.return_home)
        self.bind_all("<Control-H>", self.return_home)

    def voice_page(self) -> VoicePage | None:
        """Get the voice page when it is available."""
        page = self.frames.get("blind")
        return page if isinstance(page, VoicePage) else None

    def start_voice_hotkey(self, _event=None):
        """Use J to open the voice page and start listening."""
        if self.current_page not in {"home", "blind"}:
            return None
        if self.current_page == "home":
            self.show_page("blind")
        page = self.voice_page()
        if page is not None:
            self.after(60, page.start_listening)
        return "break"

    def stop_voice_hotkey(self, _event=None):
        """Use K to stop the current recording."""
        page = self.voice_page()
        if page is None or not page.is_listening():
            return None
        page.stop_listening()
        return "break"

    def save_voice_hotkey(self, _event=None):
        """Save the current voice message with Ctrl+S."""
        page = self.voice_page()
        if page is None or self.current_page != "blind":
            return None
        page.save_current_text()
        return "break"

    def return_home(self, _event=None):
        """Stop any open task and return to the Home page."""
        page = self.voice_page()
        if page is not None:
            page.stop_for_home()

        self.close_child_windows()
        self.show_page("home")
        try:
            self.deiconify()
            self.lift()
            self.focus_force()
        except tk.TclError:
            pass
        return "break"

    def close_child_windows(self) -> None:
        """Close the extra windows opened from the main app."""
        for process in self.child_processes:
            if process.poll() is not None:
                continue
            try:
                process.terminate()
            except OSError:
                try:
                    process.kill()
                except OSError:
                    pass
        self.child_processes.clear()

    def poll_home_signal(self) -> None:
        """Check whether another project window asked to return Home."""
        try:
            if self.home_signal_path.exists():
                self.home_signal_path.unlink(missing_ok=True)
                self.return_home()
        except OSError:
            pass

        try:
            self.after(200, self.poll_home_signal)
        except tk.TclError:
            pass

    def close_app(self) -> None:
        """Close every project window and exit cleanly."""
        page = self.voice_page()
        if page is not None:
            page.stop_for_home()
        self.close_child_windows()
        try:
            self.home_signal_path.unlink(missing_ok=True)
        except OSError:
            pass
        self.destroy()

    def toggle_theme(self) -> None:
        """Change the theme without losing the current voice text."""
        old_voice_page = self.voice_page()
        if old_voice_page is not None and old_voice_page.is_listening():
            messagebox.showinfo("Recording in progress", "Press K to stop listening before changing the theme.")
            return

        saved_text = old_voice_page.get_text() if old_voice_page is not None else ""
        self.theme_name = "dark" if self.theme_name == "light" else "light"
        self.build_window()

        new_voice_page = self.voice_page()
        if saved_text and new_voice_page is not None:
            new_voice_page.set_text(saved_text)
            new_voice_page.status_var.set("Your text is still here.")

    def show_page(self, name: str) -> None:
        """Show one page and scroll it back to the top."""
        if name not in self.frames:
            return
        self.current_page = name
        frame = self.frames[name]
        frame.tkraise()
        frame.activate_scroll()
        frame.scroll_to_top()

    def launch_script(self, script_name: str, *arguments: str) -> None:
        """Open another project window and keep its process reference."""
        script_path = BASE_DIR / script_name
        if not script_path.exists():
            messagebox.showerror("File not found", f"{script_path.name} is missing from the project folder.")
            return

        try:
            environment = os.environ.copy()
            environment["CONNECT_BDM_HOME_SIGNAL"] = str(self.home_signal_path)
            process = subprocess.Popen(
                [sys.executable, str(script_path), *arguments],
                cwd=str(BASE_DIR),
                env=environment,
            )
            self.child_processes = [item for item in self.child_processes if item.poll() is None]
            self.child_processes.append(process)
        except OSError as exc:
            messagebox.showerror("Could not open window", str(exc))


class Page(ScrollableFrame):
    """Shared base for the scrollable pages in the main window."""

    def __init__(self, parent: tk.Widget, app: ConnectBDMApp) -> None:
        """Create the scrollable page and keep a link to the main app."""
        self.app = app
        super().__init__(parent, bg=app.colors["bg"])
        self.body = self.inner

    def heading(self, title: str, subtitle: str) -> None:
        """Add the page title and its short help text."""
        colors = self.app.colors
        tk.Label(
            self.body,
            text=title,
            font=("Segoe UI", 27, "bold"),
            bg=colors["bg"],
            fg=colors["text"],
        ).pack(anchor="w", padx=34, pady=(30, 4))
        tk.Label(
            self.body,
            text=subtitle,
            font=("Segoe UI", 11),
            bg=colors["bg"],
            fg=colors["muted"],
            wraplength=800,
            justify="left",
        ).pack(anchor="w", padx=34, pady=(0, 22))

    def card(self, parent: tk.Widget | None = None) -> tk.Frame:
        """Make a bordered card for related controls."""
        colors = self.app.colors
        return tk.Frame(
            parent or self.body,
            bg=colors["surface"],
            highlightbackground=colors["border"],
            highlightthickness=1,
        )


class HomePage(Page):
    """Home page for choosing voice or sign communication."""

    def __init__(self, parent: tk.Widget, app: ConnectBDMApp) -> None:
        """Add the voice and sign choices with their shortcuts."""
        super().__init__(parent, app)
        self.heading(
            "How would you like to send your message?",
            "Choose voice or sign. Press Ctrl+H at any time to return home.",
        )
        self.add_mode_card(
            "VOICE",
            "Voice to text",
            "Speak into the microphone and turn your words into text.",
            "Open voice tools",
            lambda: app.show_page("blind"),
        )
        self.add_mode_card(
            "SIGN",
            "Sign to voice",
            "Build a message with hand signs, then save it as audio.",
            "Open sign tools",
            lambda: app.show_page("deaf"),
        )
        tk.Label(
            self.body,
            text="Shortcuts: J starts • K stops • Ctrl+S saves • Ctrl+H returns Home",
            font=("Segoe UI", 9),
            bg=app.colors["bg"],
            fg=app.colors["muted"],
            wraplength=850,
            justify="left",
        ).pack(anchor="w", padx=34, pady=(2, 28))

    def add_mode_card(
        self,
        badge: str,
        title: str,
        description: str,
        button_text: str,
        command: Callable[[], None],
    ) -> None:
        """Add one choice card to the Home page."""
        colors = self.app.colors
        card = self.card()
        card.pack(fill="x", padx=34, pady=(0, 14))

        top = tk.Frame(card, bg=colors["surface"])
        top.pack(fill="x", padx=20, pady=(20, 8))
        tk.Label(
            top,
            text=badge,
            font=("Segoe UI", 10, "bold"),
            bg=colors["accent"],
            fg=colors["accent_text"],
            padx=12,
            pady=8,
        ).pack(side="left")
        tk.Label(
            top,
            text=title,
            font=("Segoe UI", 19, "bold"),
            bg=colors["surface"],
            fg=colors["text"],
        ).pack(side="left", padx=14)
        tk.Label(
            card,
            text=description,
            font=("Segoe UI", 11),
            bg=colors["surface"],
            fg=colors["muted"],
            wraplength=780,
            justify="left",
        ).pack(anchor="w", padx=20, pady=(0, 15))
        ttk.Button(card, text=button_text, style="Primary.TButton", command=command).pack(
            anchor="w", padx=20, pady=(0, 20)
        )


class GesturePage(Page):
    """Page for choosing a model and opening sign tools."""

    def __init__(self, parent: tk.Widget, app: ConnectBDMApp) -> None:
        """Add the model choices and sign-tool buttons."""
        super().__init__(parent, app)
        colors = app.colors
        self.heading(
            "Sign to voice",
            "Choose a model, open the camera, and hold one hand clearly in view.",
        )

        model_card = self.card()
        model_card.pack(fill="x", padx=34, pady=(0, 14))
        tk.Label(
            model_card,
            text="Choose a model",
            font=("Segoe UI", 11, "bold"),
            bg=colors["surface"],
            fg=colors["text"],
        ).pack(anchor="w", padx=22, pady=(18, 10))

        self.add_model_option(
            model_card,
            "CNN",
            "cnn",
            "Uses the trained neural network supplied with this project.",
        )
        self.add_model_option(
            model_card,
            "KNN",
            "knn",
            "Compares the current hand landmarks with saved training examples.",
        )

        tools = self.card()
        tools.pack(fill="x", padx=34, pady=(0, 30))
        tk.Label(
            tools,
            text="Open a tool",
            font=("Segoe UI", 11, "bold"),
            bg=colors["surface"],
            fg=colors["text"],
        ).pack(anchor="w", padx=22, pady=(18, 12))

        actions = tk.Frame(tools, bg=colors["surface"])
        actions.pack(fill="x", padx=22, pady=(0, 22))
        actions.grid_columnconfigure(0, weight=1)
        actions.grid_columnconfigure(1, weight=1)
        ttk.Button(
            actions,
            text="Open camera",
            style="Primary.TButton",
            command=self.launch_recognition,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 6), pady=4)
        ttk.Button(
            actions,
            text="Show text as signs",
            style="Secondary.TButton",
            command=lambda: app.launch_script("InterpretText.py", "--theme", app.theme_name),
        ).grid(row=0, column=1, sticky="ew", padx=(6, 0), pady=4)

    def add_model_option(self, parent: tk.Widget, name: str, value: str, description: str) -> None:
        """Add one model choice with a short explanation."""
        colors = self.app.colors
        frame = tk.Frame(
            parent,
            bg=colors["surface_alt"],
            highlightbackground=colors["border"],
            highlightthickness=1,
        )
        frame.pack(fill="x", padx=22, pady=(0, 10))
        ttk.Radiobutton(
            frame,
            text=name,
            value=value,
            variable=self.app.selected_model,
            style="Model.TRadiobutton",
        ).pack(anchor="w", padx=14, pady=(12, 2))
        tk.Label(
            frame,
            text=description,
            font=("Segoe UI", 9),
            bg=colors["surface_alt"],
            fg=colors["muted"],
            wraplength=720,
            justify="left",
        ).pack(anchor="w", padx=14, pady=(0, 12))

    def launch_recognition(self) -> None:
        """Open sign recognition with the selected model."""
        self.app.launch_script(
            "GestureRecognition.py",
            "--model",
            self.app.selected_model.get(),
            "--theme",
            self.app.theme_name,
        )


class VoicePage(Page):
    """Voice page for recording, reviewing, and saving speech as text."""

    def __init__(self, parent: tk.Widget, app: ConnectBDMApp) -> None:
        """Build the recording page and initialise its state."""
        super().__init__(parent, app)
        self.recording_thread: threading.Thread | None = None
        self.cancelled_for_home = False
        self.audio_module = None
        self.status_var = tk.StringVar(value="Ready. Press J to start listening.")
        self.button_var = tk.StringVar(value="Start listening")
        colors = app.colors

        self.heading(
            "Voice to text",
            "Press J to start listening, then press K when you have finished.",
        )

        card = self.card()
        card.pack(fill="x", padx=34, pady=(0, 30))
        tk.Label(
            card,
            text="Voice recording",
            font=("Segoe UI", 11, "bold"),
            bg=colors["surface"],
            fg=colors["text"],
        ).pack(anchor="w", padx=22, pady=(20, 8))
        tk.Label(
            card,
            textvariable=self.status_var,
            font=("Segoe UI", 17, "bold"),
            bg=colors["surface"],
            fg=colors["text"],
            wraplength=760,
            justify="left",
        ).pack(anchor="w", padx=22, pady=(0, 12))

        self.result_box = tk.Text(
            card,
            height=12,
            wrap="word",
            font=("Segoe UI", 13),
            bg=colors["surface_alt"],
            fg=colors["text"],
            insertbackground=colors["text"],
            relief="flat",
            padx=14,
            pady=12,
        )
        self.result_box.pack(fill="x", padx=22, pady=(0, 16))
        self.bind_text_shortcuts()

        tk.Label(
            card,
            text="J: start • K: stop • Ctrl+S: save • Ctrl+H: Home",
            font=("Segoe UI", 9),
            bg=colors["surface"],
            fg=colors["muted"],
        ).pack(anchor="w", padx=22, pady=(0, 10))

        buttons = tk.Frame(card, bg=colors["surface"])
        buttons.pack(fill="x", padx=22, pady=(0, 22))
        for column in range(3):
            buttons.grid_columnconfigure(column, weight=1)

        self.record_button = ttk.Button(
            buttons,
            textvariable=self.button_var,
            style="Primary.TButton",
            command=self.toggle_recording,
        )
        self.record_button.grid(row=0, column=0, sticky="ew", padx=(0, 5), pady=4)
        ttk.Button(
            buttons,
            text="Save text",
            style="Secondary.TButton",
            command=self.save_current_text,
        ).grid(row=0, column=1, sticky="ew", padx=5, pady=4)
        ttk.Button(
            buttons,
            text="Clear",
            style="Secondary.TButton",
            command=self.clear,
        ).grid(row=0, column=2, sticky="ew", padx=(5, 0), pady=4)

    def bind_text_shortcuts(self) -> None:
        """Keep the voice shortcuts active inside the text box."""
        self.result_box.bind("<KeyPress-j>", self.app.start_voice_hotkey)
        self.result_box.bind("<KeyPress-J>", self.app.start_voice_hotkey)
        self.result_box.bind("<KeyPress-k>", self.app.stop_voice_hotkey)
        self.result_box.bind("<KeyPress-K>", self.app.stop_voice_hotkey)
        self.result_box.bind("<Control-s>", self.app.save_voice_hotkey)
        self.result_box.bind("<Control-S>", self.app.save_voice_hotkey)

    def get_audio_module(self):
        """Load the audio helper only when recording is first used."""
        if self.audio_module is not None:
            return self.audio_module
        try:
            import B2DM
        except Exception as exc:
            messagebox.showerror(
                "Voice setup problem",
                "The microphone tools could not start.\n\n"
                f"{exc}\n\n"
                "Open this project folder in Anaconda Prompt and run:\n"
                "python -m pip install --upgrade --force-reinstall -r requirements.txt",
            )
            return None
        self.audio_module = B2DM
        return self.audio_module

    def is_listening(self) -> bool:
        """Check whether recording is still running."""
        return bool(self.recording_thread and self.recording_thread.is_alive())

    def toggle_recording(self) -> None:
        """Start or stop recording from the main voice button."""
        if self.is_listening():
            self.stop_listening()
        else:
            self.start_listening()

    def start_listening(self) -> None:
        """Start recording from J or the on-screen button."""
        if self.is_listening():
            self.status_var.set("Listening is already active. Press K when you have finished.")
            return
        if self.get_audio_module() is None:
            return

        self.cancelled_for_home = False
        self.result_box.delete("1.0", "end")
        self.status_var.set("Listening... Press K when you have finished speaking.")
        self.button_var.set("Stop listening")
        self.recording_thread = threading.Thread(target=self.record_worker, daemon=True)
        self.recording_thread.start()

    def stop_listening(self) -> None:
        """Stop recording and let the worker process the audio."""
        if not self.is_listening():
            return
        self.status_var.set("Recording stopped. Converting your speech to text...")
        self.button_var.set("Please wait")
        self.record_button.state(["disabled"])
        if self.audio_module is not None:
            self.audio_module.stop_recording()

    def record_worker(self) -> None:
        """Handle recording and speech recognition away from the GUI thread."""
        try:
            text = self.audio_module.start_recording()
            self.after(0, lambda: self.record_complete(text, None))
        except Exception as exc:
            self.after(0, lambda exc=exc: self.record_complete("", exc))

    def record_complete(self, text: str, error: Exception | None) -> None:
        """Show the recognised text or report the recording error."""
        self.recording_thread = None
        self.record_button.state(["!disabled"])
        self.button_var.set("Start listening")

        if self.cancelled_for_home:
            self.cancelled_for_home = False
            self.status_var.set("Ready. Press J to start listening.")
            return
        if error:
            self.status_var.set("Something went wrong while processing the recording.")
            messagebox.showerror("Voice error", str(error))
            return

        self.set_text(text)
        self.status_var.set("Your text is ready. Press Ctrl+S to save it.")
        spoken_message = f"Your text is: {text}. Press Control S to save the file."
        threading.Thread(target=self.audio_module.speak, args=(spoken_message,), daemon=True).start()

    def get_text(self) -> str:
        """Read the text currently shown in the result box."""
        return self.result_box.get("1.0", "end-1c").strip()

    def set_text(self, text: str) -> None:
        """Replace the result box with the given message."""
        self.result_box.delete("1.0", "end")
        self.result_box.insert("1.0", text)

    def save_current_text(self) -> None:
        """Save the current text and speak a short confirmation."""
        text = self.get_text()
        if not text:
            messagebox.showwarning("Nothing to save", "Record or type a message first.")
            return
        audio = self.get_audio_module()
        if audio is None:
            return

        path = audio.save_message(text)
        self.status_var.set(f"Saved as {path.name}")
        threading.Thread(target=audio.speak, args=("Your message has been saved.",), daemon=True).start()
        messagebox.showinfo("File saved", f"Your message was saved here:\n{path}")

    def stop_for_home(self) -> None:
        """Stop recording before Ctrl+H returns Home."""
        if not self.is_listening():
            return
        self.cancelled_for_home = True
        if self.audio_module is not None:
            self.audio_module.stop_recording()
        self.status_var.set("Returning home...")

    def clear(self) -> None:
        """Clear the text and reset the voice page."""
        self.result_box.delete("1.0", "end")
        self.status_var.set("Ready. Press J to start listening.")


if __name__ == "__main__":
    ConnectBDMApp().mainloop()
