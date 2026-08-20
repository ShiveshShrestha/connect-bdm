"""Display a text message one sign image at a time."""
from __future__ import annotations

import argparse
import os
import sys
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageDraw, ImageFont, ImageTk

from ui_common import configure_ttk, fit_window, make_brand, maximize_window, theme_values

BASE_DIR = Path(__file__).resolve().parent
IMAGE_DIR = BASE_DIR / "Interpretation"
INBOX_DIR = BASE_DIR / "DeafMuteMan" / "Inbox"
DEFAULT_DELAY = 800

if sys.platform.startswith("win"):
    WORD_FONT = "segoeui.ttf"
elif sys.platform.startswith("darwin"):
    WORD_FONT = "/System/Library/Fonts/Supplemental/Arial.ttf"
else:
    WORD_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


class InterpretTextApp:
    """Window for stepping through a message with sign images."""

    def __init__(self, root: tk.Tk, theme_name: str = "light") -> None:
        """Prepare the message state, build the window, and set Ctrl+H."""
        self.root = root
        self.theme_name = theme_name if theme_name in {"light", "dark"} else "light"
        self.root.title("Connect B-DM - Text to signs")
        fit_window(self.root, 1160, 760, 800, 560)
        self.root.after(80, lambda: maximize_window(self.root))

        signal_value = os.environ.get("CONNECT_BDM_HOME_SIGNAL", "").strip()
        self.home_signal_path = Path(signal_value) if signal_value else None

        self.text_data = ""
        self.current_index = 0
        self.is_playing = False
        self.after_id: str | None = None
        self.resize_after_id: str | None = None
        self.current_pil_image: Image.Image | None = None
        self.status_var = tk.StringVar(value="No message loaded")

        self.configure_window()
        self.build_gui()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.bind_all("<Control-h>", self.return_home)
        self.root.bind_all("<Control-H>", self.return_home)

    @property
    def colors(self) -> dict[str, str]:
        """Get the colours for the current theme."""
        return theme_values(self.theme_name)

    def configure_window(self) -> None:
        """Apply the selected theme and shared button styles."""
        self.root.configure(bg=self.colors["bg"])
        configure_ttk(self.root, self.theme_name)

    def build_gui(self) -> None:
        """Build the header, sign preview, controls, and message view."""
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
        )
        paned.pack(fill="both", expand=True, padx=18, pady=18)

        left = self.make_panel(paned)
        right = self.make_panel(paned)
        paned.add(left, minsize=390, stretch="always")
        paned.add(right, minsize=330, stretch="always")

        self.build_sign_panel(left)
        self.build_text_panel(right)
        if self.text_data:
            self.show_current_char()

    def build_header(self) -> None:
        """Build the header with the logo, title, file name, and theme switch."""
        colors = self.colors
        header = tk.Frame(
            self.root,
            bg=colors["surface"],
            highlightbackground=colors["border"],
            highlightthickness=1,
        )
        header.pack(fill="x")

        brand = make_brand(header, colors, "Read text through ASL alphabet images")
        brand.pack(side="left", padx=22, pady=13)

        actions = tk.Frame(header, bg=colors["surface"])
        actions.pack(side="right", padx=18, pady=12)
        tk.Label(
            actions,
            textvariable=self.status_var,
            font=("Segoe UI", 9),
            bg=colors["surface"],
            fg=colors["muted"],
        ).pack(side="left", padx=(0, 10))
        ttk.Button(
            actions,
            text="Use dark theme" if self.theme_name == "light" else "Use light theme",
            style="Secondary.TButton",
            command=self.toggle_theme,
        ).pack(side="left")

    def make_panel(self, parent: tk.Widget) -> tk.Frame:
        """Create one bordered panel for the window."""
        colors = self.colors
        return tk.Frame(
            parent,
            bg=colors["surface"],
            highlightbackground=colors["border"],
            highlightthickness=1,
        )

    def build_sign_panel(self, parent: tk.Widget) -> None:
        """Build the sign preview, file controls, playback controls, and speed slider."""
        colors = self.colors
        toolbar = tk.Frame(parent, bg=colors["surface"])
        toolbar.pack(fill="x", padx=16, pady=(16, 8))
        toolbar.grid_columnconfigure(0, weight=1)
        toolbar.grid_columnconfigure(1, weight=1)
        ttk.Button(
            toolbar,
            text="Open a text file",
            style="Primary.TButton",
            command=self.load_text,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 5), pady=3)
        ttk.Button(
            toolbar,
            text="Open newest saved message",
            style="Secondary.TButton",
            command=self.load_latest_message,
        ).grid(row=0, column=1, sticky="ew", padx=(5, 0), pady=3)

        self.image_label = tk.Label(
            parent,
            bg="#ffffff",
            fg="#111111",
            text="Open a message to get started",
            font=("Segoe UI", 16),
            relief="flat",
        )
        self.image_label.pack(fill="both", expand=True, padx=16, pady=8)
        self.image_label.bind("<Configure>", self.schedule_image_render)

        self.word_label = tk.Label(
            parent,
            text="",
            font=("Segoe UI", 22, "bold"),
            bg=colors["surface"],
            fg=colors["text"],
        )
        self.word_label.pack(pady=(2, 8))

        controls = tk.Frame(parent, bg=colors["surface"])
        controls.pack(fill="x", padx=16, pady=(0, 8))
        for column in range(3):
            controls.grid_columnconfigure(column, weight=1)
        ttk.Button(controls, text="Start again", style="Secondary.TButton", command=self.restart).grid(
            row=0, column=0, sticky="ew", padx=(0, 4), pady=3
        )
        ttk.Button(controls, text="Previous", style="Secondary.TButton", command=self.previous_char).grid(
            row=0, column=1, sticky="ew", padx=4, pady=3
        )
        ttk.Button(controls, text="Next", style="Secondary.TButton", command=self.next_char).grid(
            row=0, column=2, sticky="ew", padx=(4, 0), pady=3
        )
        ttk.Button(controls, text="Play", style="Primary.TButton", command=self.play).grid(
            row=1, column=0, sticky="ew", padx=(0, 4), pady=3
        )
        ttk.Button(controls, text="Pause", style="Secondary.TButton", command=self.pause).grid(
            row=1, column=1, sticky="ew", padx=4, pady=3
        )
        ttk.Button(controls, text="Close window", style="Secondary.TButton", command=self.close).grid(
            row=1, column=2, sticky="ew", padx=(4, 0), pady=3
        )

        speed_frame = tk.Frame(parent, bg=colors["surface"])
        speed_frame.pack(fill="x", padx=20, pady=(0, 14))
        tk.Label(
            speed_frame,
            text="Time between signs (milliseconds)",
            font=("Segoe UI", 9),
            bg=colors["surface"],
            fg=colors["muted"],
        ).pack(anchor="w")
        self.speed_slider = tk.Scale(
            speed_frame,
            from_=200,
            to=2000,
            orient="horizontal",
            bg=colors["surface"],
            fg=colors["text"],
            troughcolor=colors["surface_alt"],
            highlightthickness=0,
            activebackground=colors["accent"],
        )
        self.speed_slider.set(DEFAULT_DELAY)
        self.speed_slider.pack(fill="x")

    def build_text_panel(self, parent: tk.Widget) -> None:
        """Show the full message and highlight the current character."""
        colors = self.colors
        tk.Label(
            parent,
            text="Message",
            font=("Segoe UI", 11, "bold"),
            bg=colors["surface"],
            fg=colors["text"],
        ).pack(anchor="w", padx=16, pady=(16, 8))

        text_container = tk.Frame(parent, bg=colors["surface"])
        text_container.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        text_container.grid_rowconfigure(0, weight=1)
        text_container.grid_columnconfigure(0, weight=1)

        self.text_display = tk.Text(
            text_container,
            wrap="word",
            font=("Segoe UI", 22),
            state="disabled",
            bg=colors["surface_alt"],
            fg=colors["text"],
            insertbackground=colors["text"],
            relief="flat",
            padx=14,
            pady=12,
        )
        scrollbar = ttk.Scrollbar(text_container, orient="vertical", command=self.text_display.yview)
        self.text_display.configure(yscrollcommand=scrollbar.set)
        self.text_display.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.text_display.tag_configure(
            "current",
            background=colors["accent"],
            foreground=colors["accent_text"],
        )

    def toggle_theme(self) -> None:
        """Change the theme without losing the message or playback speed."""
        delay = self.speed_slider.get() if hasattr(self, "speed_slider") else DEFAULT_DELAY
        self.theme_name = "dark" if self.theme_name == "light" else "light"
        self.configure_window()
        self.build_gui()
        self.speed_slider.set(delay)

    def load_text(self) -> None:
        """Choose a text file and load its message."""
        path = filedialog.askopenfilename(
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if path:
            self.load_path(Path(path))

    def load_latest_message(self) -> None:
        """Open the newest message saved by voice to text."""
        files = sorted(INBOX_DIR.glob("*.txt"), key=lambda item: item.stat().st_mtime, reverse=True)
        if not files:
            messagebox.showwarning("No saved messages", "No saved text messages were found in DeafMuteMan/Inbox.")
            return
        self.load_path(files[0])

    def load_path(self, path: Path) -> None:
        """Read a message file and return to its first character."""
        try:
            text = path.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeError) as exc:
            messagebox.showerror("File could not open", str(exc))
            return
        if not text:
            messagebox.showwarning("Empty file", "That file is empty.")
            return

        self.text_data = text + " "
        self.status_var.set(path.name)
        self.restart()

    def update_text_display(self) -> None:
        """Refresh the message and its current-character highlight."""
        self.text_display.configure(state="normal")
        self.text_display.delete("1.0", "end")
        self.text_display.insert("end", self.text_data)
        if self.text_data:
            index = f"1.0+{self.current_index}c"
            self.text_display.tag_add("current", index, f"{index}+1c")
            self.text_display.see(index)
        self.text_display.configure(state="disabled")

    def get_image_for_char(self, char: str) -> Image.Image | None:
        """Find the sign image for a character or create a simple text card."""
        if char == " ":
            return self.create_word_image(self.previous_word())
        if not char.isalpha():
            return self.create_word_image(char)

        base_name = char.lower()
        for extension in (".png", ".jpg", ".jpeg"):
            path = IMAGE_DIR / f"{base_name}{extension}"
            if path.exists():
                try:
                    return Image.open(path).convert("RGB")
                except OSError:
                    return None
        return None

    def previous_word(self) -> str:
        """Get the word just before the current space."""
        words = self.text_data[: self.current_index].strip().split()
        return words[-1] if words else ""

    def current_word(self) -> str:
        """Get the word that contains the current character."""
        words = self.text_data[: self.current_index + 1].strip().split()
        return words[-1] if words else ""

    def create_word_image(self, text: str) -> Image.Image:
        """Create a plain card for spaces, word breaks, or punctuation."""
        image = Image.new("RGB", (600, 600), color="white")
        drawer = ImageDraw.Draw(image)
        try:
            font = ImageFont.truetype(WORD_FONT, 64)
        except OSError:
            font = ImageFont.load_default()

        label = text or "SPACE"
        box = drawer.textbbox((0, 0), label, font=font)
        width = box[2] - box[0]
        height = box[3] - box[1]
        drawer.text(((600 - width) / 2, (600 - height) / 2), label, fill="black", font=font)
        return image

    def show_current_char(self) -> None:
        """Show the sign image for the current character."""
        if not self.text_data or self.current_index >= len(self.text_data):
            self.pause()
            return

        char = self.text_data[self.current_index]
        self.word_label.configure(text=self.current_word())
        self.current_pil_image = self.get_image_for_char(char)
        self.render_current_image(char)
        self.update_text_display()

    def schedule_image_render(self, _event=None) -> None:
        """Wait for resizing to finish before drawing again."""
        if self.resize_after_id:
            try:
                self.root.after_cancel(self.resize_after_id)
            except tk.TclError:
                pass
        self.resize_after_id = self.root.after(80, self.render_current_image)

    def render_current_image(self, fallback_char: str | None = None) -> None:
        """Fit the current sign image inside the preview."""
        self.resize_after_id = None
        if not hasattr(self, "image_label") or not self.image_label.winfo_exists():
            return
        if self.current_pil_image is None:
            text = "Open a message to get started" if not self.text_data else f"No image found for {fallback_char or ''}"
            self.image_label.configure(image="", text=text)
            return

        width = self.image_label.winfo_width()
        height = self.image_label.winfo_height()
        if width < 100:
            width = 420
        if height < 100:
            height = 420

        image = self.current_pil_image.copy()
        image.thumbnail((max(180, width - 12), max(180, height - 12)), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(image)
        self.image_label.configure(image=photo, text="")
        self.image_label.image = photo

    def restart(self) -> None:
        """Stop playback and return to the start of the message."""
        if not self.text_data:
            return
        self.pause()
        self.current_index = 0
        self.show_current_char()

    def play(self) -> None:
        """Play the message at the selected speed."""
        if self.text_data and not self.is_playing:
            self.is_playing = True
            self.auto_next()

    def pause(self) -> None:
        """Pause playback at the current character."""
        self.is_playing = False
        if self.after_id:
            try:
                self.root.after_cancel(self.after_id)
            except tk.TclError:
                pass
            self.after_id = None

    def auto_next(self) -> None:
        """Move to the next character and continue playback when needed."""
        if not self.is_playing:
            return
        if self.current_index < len(self.text_data) - 1:
            self.current_index += 1
            self.show_current_char()
            self.after_id = self.root.after(self.speed_slider.get(), self.auto_next)
        else:
            self.pause()

    def next_char(self) -> None:
        """Move forward by one character."""
        if self.current_index < len(self.text_data) - 1:
            self.current_index += 1
            self.show_current_char()
        else:
            self.pause()

    def previous_char(self) -> None:
        """Move back by one character."""
        if self.current_index > 0:
            self.current_index -= 1
            self.show_current_char()

    def return_home(self, _event=None):
        """Ask the main app to return Home and close extra windows."""
        if self.home_signal_path is not None:
            try:
                self.home_signal_path.parent.mkdir(parents=True, exist_ok=True)
                self.home_signal_path.write_text(str(time.time()), encoding="utf-8")
            except OSError:
                pass
        self.close()
        return "break"

    def close(self) -> None:
        """Cancel pending work and close the window."""
        self.pause()
        if self.resize_after_id:
            try:
                self.root.after_cancel(self.resize_after_id)
            except tk.TclError:
                pass
        try:
            self.root.destroy()
        except tk.TclError:
            pass


def parse_args() -> argparse.Namespace:
    """Read the theme selected by the main app."""
    parser = argparse.ArgumentParser(description="Open Connect B-DM text-to-sign view.")
    parser.add_argument("--theme", choices=("light", "dark"), default="light")
    return parser.parse_args()


def main() -> None:
    """Open the text-to-sign window and run it until it closes."""
    args = parse_args()
    root = tk.Tk()
    InterpretTextApp(root, args.theme)
    root.mainloop()


if __name__ == "__main__":
    main()
