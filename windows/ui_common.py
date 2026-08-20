"""Shared Tkinter helpers for the Connect B-DM windows. Basically its like helper functions here."""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import ttk

from PIL import Image, ImageTk

BASE_DIR = Path(__file__).resolve().parent
LOGO_PATH = BASE_DIR / "logo.png"

THEMES = {
    "light": {
        "bg": "#f4f9fc",
        "surface": "#ffffff",
        "surface_alt": "#eaf5fb",
        "text": "#10243a",
        "muted": "#587087",
        "border": "#c5e2f2",
        "accent": "#2a8ed5",
        "accent_hover": "#0d60bc",
        "accent_text": "#ffffff",
        "success": "#16794b",
        "danger": "#b42318",
        "camera": "#10243a",
    },
    "dark": {
        "bg": "#0b0b0c",
        "surface": "#171719",
        "surface_alt": "#242427",
        "text": "#f5f5f5",
        "muted": "#aaaaaf",
        "border": "#343438",
        "accent": "#f5f5f5",
        "accent_hover": "#ffffff",
        "accent_text": "#111111",
        "success": "#55c991",
        "danger": "#ff7b72",
        "camera": "#000000",
    },
}


def theme_values(name: str) -> dict[str, str]:
    """Get a colour set and fall back to the light theme when needed."""
    return THEMES.get(name, THEMES["light"])


def configure_ttk(root: tk.Misc, theme_name: str) -> None:
    """Apply the shared button, option, checkbox, and scrollbar styles."""
    colors = theme_values(theme_name)
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure(
        "Primary.TButton",
        font=("Segoe UI", 10, "bold"),
        padding=(15, 10),
        background=colors["accent"],
        foreground=colors["accent_text"],
        bordercolor=colors["accent"],
        focusthickness=1,
        focuscolor=colors["border"],
    )
    style.map(
        "Primary.TButton",
        background=[("active", colors["accent_hover"]), ("disabled", colors["border"])],
        foreground=[("active", colors["accent_text"]), ("disabled", colors["muted"])],
    )
    style.configure(
        "Secondary.TButton",
        font=("Segoe UI", 10),
        padding=(13, 9),
        background=colors["surface_alt"],
        foreground=colors["text"],
        bordercolor=colors["border"],
    )
    style.map(
        "Secondary.TButton",
        background=[("active", colors["border"])],
        foreground=[("active", colors["text"])],
    )
    style.configure(
        "Model.TRadiobutton",
        font=("Segoe UI", 11, "bold"),
        background=colors["surface_alt"],
        foreground=colors["text"],
    )
    style.map(
        "Model.TRadiobutton",
        background=[("active", colors["surface_alt"])],
        foreground=[("active", colors["text"])],
    )
    style.configure(
        "App.TCheckbutton",
        font=("Segoe UI", 10),
        background=colors["surface"],
        foreground=colors["text"],
    )
    style.map(
        "App.TCheckbutton",
        background=[("active", colors["surface"])],
        foreground=[("active", colors["text"])],
    )
    style.configure(
        "Vertical.TScrollbar",
        background=colors["surface_alt"],
        troughcolor=colors["bg"],
        bordercolor=colors["border"],
        arrowcolor=colors["text"],
    )


def fit_window(
    root: tk.Tk,
    desired_width: int,
    desired_height: int,
    minimum_width: int = 720,
    minimum_height: int = 520,
) -> None:
    """Fit a window on screen and place it near the centre."""
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    width = min(desired_width, max(640, screen_width - 70))
    height = min(desired_height, max(480, screen_height - 100))
    x = max(0, (screen_width - width) // 2)
    y = max(0, (screen_height - height) // 3)
    root.geometry(f"{width}x{height}+{x}+{y}")
    root.minsize(min(minimum_width, screen_width), min(minimum_height, screen_height))


def maximize_window(root: tk.Tk) -> None:
    """Maximise the window when the operating system allows it."""
    try:
        root.state("zoomed")
    except tk.TclError:
        try:
            root.attributes("-zoomed", True)
        except tk.TclError:
            pass


def make_brand(
    parent: tk.Widget,
    colors: dict[str, str],
    subtitle: str,
    title: str = "Connect B-DM",
    logo_size: int = 46,
) -> tk.Frame:
    """Build the title area with a logo slot before the project name."""
    brand = tk.Frame(parent, bg=colors["surface"])

    logo_slot = tk.Frame(
        brand,
        width=logo_size,
        height=logo_size,
        bg=colors["surface"],
    )
    logo_slot.pack(side="left", padx=(0, 12))
    logo_slot.pack_propagate(False)

    if LOGO_PATH.exists():
        try:
            image = Image.open(LOGO_PATH).convert("RGBA")
            image.thumbnail((logo_size, logo_size), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(image)
            logo_label = tk.Label(logo_slot, image=photo, bg=colors["surface"], bd=0)
            logo_label.image = photo
            logo_label.pack(expand=True)
        except OSError:
            pass

    text_area = tk.Frame(brand, bg=colors["surface"])
    text_area.pack(side="left")
    tk.Label(
        text_area,
        text=title,
        font=("Segoe UI", 20, "bold"),
        bg=colors["surface"],
        fg=colors["text"],
    ).pack(anchor="w")
    tk.Label(
        text_area,
        text=subtitle,
        font=("Segoe UI", 9),
        bg=colors["surface"],
        fg=colors["muted"],
    ).pack(anchor="w")
    return brand


class ScrollableFrame(tk.Frame):
    """A frame inside a canvas that lets long pages scroll."""

    def __init__(self, parent: tk.Widget, bg: str, **kwargs) -> None:
        """Create the canvas, page frame, and scrollbar."""
        super().__init__(parent, bg=bg, **kwargs)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self.window_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")

        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.inner.bind("<Configure>", self._update_scroll_region)
        self.canvas.bind("<Configure>", self._resize_inner)
        self.canvas.bind("<Enter>", self._enable_mousewheel)

    def _update_scroll_region(self, _event=None) -> None:
        """Update the scroll area after the page size changes."""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _resize_inner(self, event) -> None:
        """Keep the inner page the same width as the canvas."""
        self.canvas.itemconfigure(self.window_id, width=event.width)

    def _enable_mousewheel(self, _event=None) -> None:
        """Use the mouse wheel on this canvas while the pointer is over it."""
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", self._on_linux_scroll_up)
        self.canvas.bind_all("<Button-5>", self._on_linux_scroll_down)

    def _on_mousewheel(self, event) -> None:
        """Handle normal mouse-wheel scrolling."""
        step = -1 if event.delta > 0 else 1
        self.canvas.yview_scroll(step, "units")

    def _on_linux_scroll_up(self, _event) -> None:
        """Handle upward scrolling on Linux."""
        self.canvas.yview_scroll(-1, "units")

    def _on_linux_scroll_down(self, _event) -> None:
        """Handle downward scrolling on Linux."""
        self.canvas.yview_scroll(1, "units")

    def activate_scroll(self) -> None:
        """Make this page respond to the mouse wheel."""
        self._enable_mousewheel()

    def scroll_to_top(self) -> None:
        """Scroll the page back to the top."""
        self.canvas.yview_moveto(0)
