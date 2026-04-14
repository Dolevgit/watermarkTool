from __future__ import annotations

import json
import logging
import os
import sys
import traceback
import faulthandler
from datetime import date as current_date
from pathlib import Path
import tkinter as tk
import webbrowser
from tkinter import colorchooser, filedialog, messagebox, ttk

from PIL import Image, ImageOps, ImageTk

from renderer import render_watermark
from tkinterdnd2 import COPY, DND_FILES, TkinterDnD


APP_TITLE = "Watermark Tool"
APP_VERSION = "1.1"
AUTHOR_GITHUB_URL = "https://github.com/Dolevgit"
PROJECT_GITHUB_URL = "https://github.com/Dolevgit/watermarkToolDesktop"
DEFAULT_WINDOW_GEOMETRY = "1120x740"
MIN_WINDOW_WIDTH = 600
MIN_WINDOW_HEIGHT = 390
SIDE_PANEL_MIN_WIDTH = 50
SIDE_PANEL_MAX_WIDTH = 250
SETTINGS_DATE_TOKEN = "{date}"
DEFAULT_SETTINGS = {
    "text": "Build with Codex",
    "text_mode": "normal",
    "split_text": None,
    "font_size": 36,
    "angle": 45,
    "color": "#000000",
    "border_color": "",
    "opacity": 0.3,
    "repeat": True,
    "space_left": 0,
    "space_right": 0,
    "space_top": 0,
    "space_bottom": 0,
    "isDebug": False,
    "window_geometry": DEFAULT_WINDOW_GEOMETRY,
}
IMAGE_FILE_TYPES = [
    ("Images", "*.png;*.jpg;*.jpeg;*.bmp;*.gif;*.webp;*.tif;*.tiff"),
    ("PNG", "*.png"),
    ("JPEG", "*.jpg;*.jpeg"),
    ("Bitmap", "*.bmp"),
    ("All files", "*.*"),
]
SAVE_FILE_TYPES = [
    ("PNG", "*.png"),
    ("JPEG", "*.jpg"),
    ("Bitmap", "*.bmp"),
]


def get_app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def get_resource_dir() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


def get_icon_path() -> Path:
    resource_dir = get_resource_dir()
    return resource_dir / "AppIcons" / "app.ico"


def get_settings_path() -> Path:
    app_dir = get_app_dir()
    local_path = app_dir / "settings.json"
    if local_path.exists() or os.access(app_dir, os.W_OK):
        return local_path

    appdata = Path(os.environ.get("APPDATA", app_dir))
    fallback_dir = appdata / "WatermarkTool"
    fallback_dir.mkdir(parents=True, exist_ok=True)
    return fallback_dir / "settings.json"


def get_log_path() -> Path:
    return get_settings_path().with_name("watermark-tool.log")


def replace_bare_settings_tokens(raw_text: str) -> str:
    parts: list[str] = []
    in_string = False
    escaping = False
    index = 0

    while index < len(raw_text):
        char = raw_text[index]

        if in_string:
            parts.append(char)
            if escaping:
                escaping = False
            elif char == "\\":
                escaping = True
            elif char == '"':
                in_string = False
            index += 1
            continue

        if char == '"':
            in_string = True
            parts.append(char)
            index += 1
            continue

        if raw_text.startswith("date", index):
            previous_char = raw_text[index - 1] if index > 0 else ""
            next_char = raw_text[index + 4] if index + 4 < len(raw_text) else ""
            if not (previous_char.isalnum() or previous_char == "_") and not (next_char.isalnum() or next_char == "_"):
                parts.append(f'"{SETTINGS_DATE_TOKEN}"')
                index += 4
                continue

        parts.append(char)
        index += 1

    return "".join(parts)


def dump_settings_text(settings: dict) -> str:
    return f"{json.dumps(settings, indent=2)}\n"


def is_settings_date_token(value: object) -> bool:
    return value == SETTINGS_DATE_TOKEN or value == "__WATERMARK_DATE_TOKEN__"


def split_text_into_rows(text: str) -> list[list[str]]:
    top_text, bottom_text = (text.split("\n", 1) + [""])[:2] if "\n" in text else [text, ""]
    return [[top_text], [bottom_text]]


def migrate_legacy_split_rows(split_rows: object, fallback_text: str) -> list[list[str]] | None:
    if not isinstance(split_rows, list):
        return None

    migrated_rows: list[list[str]] = []
    for row in split_rows[:2]:
        if not isinstance(row, dict):
            continue
        left_text = str(row.get("left", ""))
        right_text = str(row.get("right", ""))
        if bool(row.get("split", False)):
            migrated_rows.append([left_text, right_text])
        else:
            migrated_rows.append([left_text])

    if not migrated_rows:
        return split_text_into_rows(fallback_text)

    while len(migrated_rows) < 2:
        migrated_rows.append([""])
    return migrated_rows


def load_startup_settings() -> dict:
    settings_path = get_settings_path()
    if not settings_path.exists():
        with settings_path.open("w", encoding="utf-8") as handle:
            handle.write(dump_settings_text(DEFAULT_SETTINGS))
        return DEFAULT_SETTINGS.copy()

    try:
        with settings_path.open("r", encoding="utf-8") as handle:
            loaded = json.loads(replace_bare_settings_tokens(handle.read()))
    except (json.JSONDecodeError, OSError):
        return DEFAULT_SETTINGS.copy()

    legacy_split_text = migrate_legacy_split_rows(loaded.get("split_rows"), str(loaded.get("text", "")))
    if "split_text" not in loaded and legacy_split_text is not None:
        loaded["split_text"] = legacy_split_text

    merged = DEFAULT_SETTINGS.copy()
    merged.update({key: loaded[key] for key in DEFAULT_SETTINGS if key in loaded})
    return merged


def configure_logging(is_debug: bool) -> Path | None:
    if not is_debug:
        logging.disable(logging.CRITICAL)
        return None

    log_path = get_log_path()
    logging.basicConfig(
        filename=log_path,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        encoding="utf-8",
    )
    logging.info("Application startup")
    return log_path


def enable_fault_logging(log_path: Path | None) -> None:
    if log_path is None:
        return
    handle = log_path.open("a", encoding="utf-8")
    faulthandler.enable(handle, all_threads=True)


def install_exception_logging(log_path: Path | None) -> None:
    def excepthook(exc_type, exc_value, exc_traceback) -> None:
        if log_path is not None:
            logging.critical(
                "Unhandled exception",
                exc_info=(exc_type, exc_value, exc_traceback),
            )

    sys.excepthook = excepthook

    if os.name == "nt":
        def win_excepthook(exc_type, exc_value, exc_traceback) -> None:
            excepthook(exc_type, exc_value, exc_traceback)
            message = "The app hit an unexpected error."
            if log_path is not None:
                message += f"\nLog file:\n{log_path}"
            messagebox.showerror(
                APP_TITLE,
                message,
            )

        sys.excepthook = win_excepthook


class WatermarkApp:
    def __init__(self, root: TkinterDnD.Tk, startup_settings: dict) -> None:
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry(str(startup_settings.get("window_geometry", DEFAULT_WINDOW_GEOMETRY)))
        self.root.minsize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)
        self.app_icon: tk.PhotoImage | None = None
        self.save_geometry_after_id: str | None = None

        self.settings_path = get_settings_path()
        self.log_path = get_log_path()
        self.settings = startup_settings.copy()
        self.is_debug = bool(self.settings.get("isDebug", False))
        self.root.report_callback_exception = self.report_callback_exception

        self.source_image: Image.Image | None = None
        self.rendered_image: Image.Image | None = None
        self.current_image_path: Path | None = None
        self.preview_photo: ImageTk.PhotoImage | None = None
        self.render_after_id: str | None = None
        self.container: ttk.Frame | None = None
        self.preview_panel: ttk.Frame | None = None
        self.controls_panel: ttk.Frame | None = None
        self.text_input_container: ttk.Frame | None = None
        self.text_input: tk.Text | None = None
        self.text_mode_button: ttk.Button | None = None
        self.split_row_frames: list[ttk.Frame] = []
        self.split_row_toggle_buttons: list[ttk.Button] = []
        self.split_row_content_frames: list[ttk.Frame] = []
        self.split_row_single_inputs: list[tk.Text] = []
        self.split_row_left_inputs: list[tk.Text] = []
        self.split_row_right_inputs: list[tk.Text] = []
        self.split_row_states: list[bool] = []
        self.split_row_single_is_date: list[bool] = []
        self.split_row_left_is_date: list[bool] = []
        self.split_row_right_is_date: list[bool] = []
        self.updating_text_widgets = False
        self.text_input_background = "#ffffff"

        self.text_mode_var = tk.StringVar(value=self.settings["text_mode"])
        self.font_size_var = tk.IntVar(value=self.settings["font_size"])
        self.angle_var = tk.IntVar(value=self.settings["angle"])
        self.opacity_percent_var = tk.IntVar(value=int(round(self.settings["opacity"] * 100)))
        self.color_var = tk.StringVar(value=self.settings["color"])
        self.border_color_var = tk.StringVar(value=self.settings["border_color"])
        self.repeat_var = tk.BooleanVar(value=self.settings["repeat"])
        self.space_left_var = tk.StringVar(value=str(self.settings["space_left"]))
        self.space_right_var = tk.StringVar(value=str(self.settings["space_right"]))
        self.space_top_var = tk.StringVar(value=str(self.settings["space_top"]))
        self.space_bottom_var = tk.StringVar(value=str(self.settings["space_bottom"]))

        self.font_size_label_var = tk.StringVar()
        self.angle_label_var = tk.StringVar()
        self.opacity_label_var = tk.StringVar()
        status = f"Settings: {self.settings_path}"
        if self.is_debug:
            status += f" | Log: {self.log_path}"
        self.status_var = tk.StringVar(value=status)
        self.file_var = tk.StringVar(value="Drop an image here or use Open Image.")

        self.configure_window_icon()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.build_ui()
        self.attach_traces()
        self.refresh_control_labels()
        self.update_color_buttons()
        self.setup_drag_and_drop()

    def configure_window_icon(self) -> None:
        icon_path = get_icon_path()

        if icon_path.exists():
            try:
                self.root.iconbitmap(default=str(icon_path))
            except tk.TclError:
                logging.exception("Failed to load window .ico icon: %s", icon_path)
            try:
                self.app_icon = ImageTk.PhotoImage(Image.open(icon_path))
                self.root.iconphoto(True, self.app_icon)
            except (tk.TclError, OSError):
                logging.exception("Failed to load window icon image: %s", icon_path)

    def build_ui(self) -> None:
        self.container = ttk.Frame(self.root, padding=14)
        self.container.pack(fill="both", expand=True)

        self.container.columnconfigure(0, weight=1)
        self.container.columnconfigure(1, weight=0, minsize=SIDE_PANEL_MIN_WIDTH)
        self.container.rowconfigure(0, weight=1)

        self.preview_panel = ttk.Frame(self.container, padding=(0, 0, 14, 0))
        self.preview_panel.grid(row=0, column=0, sticky="nsew")
        self.preview_panel.rowconfigure(1, weight=1)
        self.preview_panel.columnconfigure(0, weight=1)

        self.controls_panel = ttk.Frame(self.container, padding=18)
        self.controls_panel.grid(row=0, column=1, sticky="nsew")
        self.controls_panel.grid_propagate(False)
        self.controls_panel.columnconfigure(0, weight=1, minsize=20)

        ttk.Label(self.preview_panel, textvariable=self.file_var).grid(row=0, column=0, sticky="w", pady=(0, 8))

        self.preview_label = ttk.Label(
            self.preview_panel,
            text="No image loaded",
            anchor="center",
            relief="solid",
            padding=10,
            background="#f5f5f5",
        )
        self.preview_label.grid(row=1, column=0, sticky="nsew")
        self.preview_label.bind("<Configure>", self.on_preview_resize)

        preview_actions = ttk.Frame(self.preview_panel, padding=(0, 10, 0, 0))
        preview_actions.grid(row=2, column=0, sticky="ew")
        preview_actions.columnconfigure(0, weight=1)
        preview_actions.columnconfigure(1, weight=1)

        ttk.Button(preview_actions, text="Open Image", command=self.open_image).grid(
            row=0, column=0, sticky="ew", padx=(0, 6)
        )
        ttk.Button(preview_actions, text="Save As...", command=self.save_image).grid(
            row=0, column=1, sticky="ew", padx=(6, 0)
        )

        text_header = ttk.Frame(self.controls_panel)
        text_header.grid(row=0, column=0, sticky="ew")
        text_header.columnconfigure(0, weight=1)
        ttk.Label(text_header, text="Watermark Text").grid(row=0, column=0, sticky="w")
        self.text_mode_button = ttk.Button(text_header, text="", command=self.toggle_text_mode, width=12)
        self.text_mode_button.grid(row=0, column=1, sticky="e")

        self.text_input_container = ttk.Frame(self.controls_panel)
        self.text_input_container.grid(row=1, column=0, sticky="ew", pady=(4, 14))
        self.text_input_container.columnconfigure(0, weight=1)

        self.text_input = tk.Text(
            self.text_input_container,
            height=4,
            width=1,
            wrap="word",
            relief="solid",
            bd=1,
            undo=True,
            autoseparators=True,
            maxundo=-1,
        )
        self.set_text_widget_value(self.text_input, self.settings["text"])
        self.text_input_background = self.text_input.cget("bg")
        self.build_split_row_widgets()
        self.load_split_rows_from_settings()
        self.update_text_mode_ui(initializing=True)

        ttk.Label(self.controls_panel, textvariable=self.font_size_label_var).grid(row=2, column=0, sticky="w")
        ttk.Scale(
            self.controls_panel,
            from_=12,
            to=160,
            orient="horizontal",
            variable=self.font_size_var,
        ).grid(row=3, column=0, sticky="ew", pady=(4, 14))

        ttk.Label(self.controls_panel, textvariable=self.angle_label_var).grid(row=4, column=0, sticky="w")
        ttk.Scale(
            self.controls_panel,
            from_=-90,
            to=90,
            orient="horizontal",
            variable=self.angle_var,
        ).grid(row=5, column=0, sticky="ew", pady=(4, 14))

        ttk.Label(self.controls_panel, text="Color").grid(row=6, column=0, sticky="w")
        self.color_button = tk.Button(
            self.controls_panel,
            text="Choose Color",
            command=self.choose_color,
            relief="ridge",
            bd=1,
        )
        self.color_button.grid(row=7, column=0, sticky="ew", pady=(4, 14))

        ttk.Label(self.controls_panel, text="Border Color").grid(row=8, column=0, sticky="w")
        border_actions = ttk.Frame(self.controls_panel)
        border_actions.grid(row=9, column=0, sticky="ew", pady=(4, 14))
        border_actions.columnconfigure(0, weight=1)
        border_actions.columnconfigure(1, weight=0)
        self.border_color_button = tk.Button(
            border_actions,
            text="Choose Border Color",
            command=self.choose_border_color,
            relief="ridge",
            bd=1,
        )
        self.border_color_button.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.clear_border_button = ttk.Button(
            border_actions,
            text="Clear",
            command=self.clear_border_color,
        )
        self.clear_border_button.grid(row=0, column=1)

        ttk.Label(self.controls_panel, textvariable=self.opacity_label_var).grid(row=10, column=0, sticky="w")
        ttk.Scale(
            self.controls_panel,
            from_=5,
            to=100,
            orient="horizontal",
            variable=self.opacity_percent_var,
        ).grid(row=11, column=0, sticky="ew", pady=(4, 14))

        spacing_frame = ttk.Frame(self.controls_panel, padding=(0, 0, 0, 6))
        spacing_frame.grid(row=12, column=0, sticky="ew", pady=(0, 12))
        spacing_frame.columnconfigure(0, weight=1)
        spacing_frame.columnconfigure(1, weight=1)
        spacing_frame.columnconfigure(2, weight=1)

        ttk.Label(spacing_frame, text="Top Space").grid(row=0, column=1)
        ttk.Entry(spacing_frame, textvariable=self.space_top_var, width=5, justify="center").grid(
            row=1, column=1, pady=(4, 8)
        )

        ttk.Separator(spacing_frame, orient="horizontal").grid(row=2, column=0, columnspan=3, sticky="ew", pady=(0, 8))

        left_frame = ttk.Frame(spacing_frame)
        left_frame.grid(row=3, column=0, sticky="n")
        ttk.Label(left_frame, text="Left Space").grid(row=0, column=0)
        ttk.Entry(left_frame, textvariable=self.space_left_var, width=5, justify="center").grid(row=1, column=0, pady=(4, 0))

        center_frame = ttk.Frame(spacing_frame, padding=(10, 4))
        center_frame.grid(row=3, column=1, sticky="nsew")
        center_frame.columnconfigure(0, weight=1)
        ttk.Label(center_frame, text="Watermark Text", justify="center").grid(row=0, column=0)

        right_frame = ttk.Frame(spacing_frame)
        right_frame.grid(row=3, column=2, sticky="n")
        ttk.Label(right_frame, text="Right Space").grid(row=0, column=0)
        ttk.Entry(right_frame, textvariable=self.space_right_var, width=5, justify="center").grid(row=1, column=0, pady=(4, 0))

        ttk.Separator(spacing_frame, orient="horizontal").grid(row=4, column=0, columnspan=3, sticky="ew", pady=(8, 8))

        ttk.Label(spacing_frame, text="Bottom Space").grid(row=5, column=1)
        ttk.Entry(spacing_frame, textvariable=self.space_bottom_var, width=5, justify="center").grid(
            row=6, column=1, pady=(4, 0)
        )
        spacing_frame.update_idletasks()
        spacing_frame.grid_propagate(False)
        spacing_frame.configure(width=1, height=spacing_frame.winfo_reqheight())

        ttk.Checkbutton(self.controls_panel, text="Repeat Across Image", variable=self.repeat_var).grid(
            row=13, column=0, sticky="w", pady=(0, 18)
        )

        footer_links = ttk.Frame(self.controls_panel)
        footer_links.grid(row=14, column=0, sticky="ew")
        self.add_footer_text(footer_links, "Built with Codex", 0, 0)
        self.add_footer_text(footer_links, " | ", 1, 0)
        self.add_footer_text(footer_links, f"version {APP_VERSION}", 2, 0)
        
        
        self.add_footer_link(footer_links, "Project on GitHub", PROJECT_GITHUB_URL, 0, 1)
        self.add_footer_text(footer_links, " | ", 1, 1)
        self.add_footer_link(footer_links, "@Dolevgit", AUTHOR_GITHUB_URL, 2, 1)
        footer_links.update_idletasks()
        footer_links.grid_propagate(False)
        footer_links.configure(width=1, height=footer_links.winfo_reqheight())

        ttk.Separator(self.root, orient="horizontal").pack(fill="x", side="bottom")
        footer = tk.Frame(self.root, bd=1, relief="sunken", background="#f0f0f0")
        footer.pack(fill="x", side="bottom")
        footer.columnconfigure(0, weight=1)
        tk.Label(
            footer,
            textvariable=self.status_var,
            anchor="w",
            padx=6,
            pady=2,
            background="#f0f0f0",
        ).grid(row=0, column=0, sticky="ew")
        self.root.after_idle(self.update_main_panel_weights)

    def attach_traces(self) -> None:
        self.root.bind("<Configure>", self.on_window_configure)
        for variable in (
            self.font_size_var,
            self.angle_var,
            self.opacity_percent_var,
            self.color_var,
            self.border_color_var,
            self.repeat_var,
            self.space_left_var,
            self.space_right_var,
            self.space_top_var,
            self.space_bottom_var,
        ):
            variable.trace_add("write", self.on_settings_changed)
        split_widgets = self.split_row_single_inputs + self.split_row_left_inputs + self.split_row_right_inputs
        for widget in [self.text_input, *split_widgets]:
            widget.bind("<<Modified>>", self.on_text_modified)
            widget.bind("<Control-z>", self.undo_text_edit)
            widget.bind("<Control-y>", self.redo_text_edit)
            widget.bind("<Control-Z>", self.undo_text_edit)
            widget.bind("<Control-Y>", self.redo_text_edit)
        for row_index, widget in enumerate(self.split_row_single_inputs):
            widget.bind("<Button-1>", self.select_all_split_text)
            widget.bind("<Button-3>", lambda event, idx=row_index: self.toggle_split_cell_date(event, idx, "single"))
            widget.bind("<KeyPress>", lambda event, idx=row_index: self.block_date_cell_edit(event, idx, "single"))
            widget.bind("<Return>", lambda event: "break")
            widget.bind("<KP_Enter>", lambda event: "break")
        for row_index, widget in enumerate(self.split_row_left_inputs):
            widget.bind("<Button-1>", self.select_all_split_text)
            widget.bind("<Button-3>", lambda event, idx=row_index: self.toggle_split_cell_date(event, idx, "left"))
            widget.bind("<KeyPress>", lambda event, idx=row_index: self.block_date_cell_edit(event, idx, "left"))
            widget.bind("<Return>", lambda event: "break")
            widget.bind("<KP_Enter>", lambda event: "break")
        for row_index, widget in enumerate(self.split_row_right_inputs):
            widget.bind("<Button-1>", self.select_all_split_text)
            widget.bind("<Button-3>", lambda event, idx=row_index: self.toggle_split_cell_date(event, idx, "right"))
            widget.bind("<KeyPress>", lambda event, idx=row_index: self.block_date_cell_edit(event, idx, "right"))
            widget.bind("<Return>", lambda event: "break")
            widget.bind("<KP_Enter>", lambda event: "break")

    def setup_drag_and_drop(self) -> None:
        logging.info("Installing drag and drop hook")
        self.preview_label.drop_target_register(DND_FILES)
        self.preview_label.dnd_bind("<<Drop>>", self.on_drop_event)

    def load_settings(self) -> dict:
        return load_startup_settings()

    def write_settings(self, settings: dict) -> None:
        with self.settings_path.open("w", encoding="utf-8") as handle:
            handle.write(dump_settings_text(settings))

    def get_current_settings(self) -> dict:
        return {
            "text": self.get_text_widget_value(self.text_input),
            "text_mode": self.text_mode_var.get(),
            "split_text": self.get_split_text_state(),
            "font_size": int(float(self.font_size_var.get())),
            "angle": int(float(self.angle_var.get())),
            "color": self.color_var.get(),
            "border_color": self.border_color_var.get().strip(),
            "opacity": round(max(0, min(100, int(float(self.opacity_percent_var.get())))) / 100, 2),
            "repeat": bool(self.repeat_var.get()),
            "space_left": self.parse_non_negative_int(self.space_left_var.get()),
            "space_right": self.parse_non_negative_int(self.space_right_var.get()),
            "space_top": self.parse_non_negative_int(self.space_top_var.get()),
            "space_bottom": self.parse_non_negative_int(self.space_bottom_var.get()),
            "isDebug": self.is_debug,
            "window_geometry": self.get_window_geometry(),
        }

    def get_window_geometry(self) -> str:
        self.root.update_idletasks()
        width = max(self.root.winfo_width(), MIN_WINDOW_WIDTH)
        height = max(self.root.winfo_height(), MIN_WINDOW_HEIGHT)
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        return f"{width}x{height}+{x}+{y}"

    def parse_non_negative_int(self, value: str) -> int:
        try:
            return max(0, int(value.strip() or "0"))
        except ValueError:
            return 0

    def on_text_modified(self, _event: tk.Event) -> None:
        if self.updating_text_widgets:
            return
        modified_widget = _event.widget
        if not isinstance(modified_widget, tk.Text) or not modified_widget.edit_modified():
            return
        if self.is_split_text_widget(modified_widget):
            self.normalize_split_widget_text(modified_widget)
        modified_widget.edit_modified(False)
        self.on_settings_changed()

    def undo_text_edit(self, event: tk.Event) -> str:
        widget = event.widget
        if not isinstance(widget, tk.Text):
            return "break"
        try:
            widget.edit_undo()
        except tk.TclError:
            pass
        return "break"

    def redo_text_edit(self, event: tk.Event) -> str:
        widget = event.widget
        if not isinstance(widget, tk.Text):
            return "break"
        try:
            widget.edit_redo()
        except tk.TclError:
            pass
        return "break"

    def get_text_widget_value(self, widget: tk.Text) -> str:
        return widget.get("1.0", "end-1c")

    def set_text_widget_value(self, widget: tk.Text, value: str) -> None:
        self.updating_text_widgets = True
        try:
            widget.delete("1.0", "end")
            widget.insert("1.0", value)
            widget.edit_modified(False)
        finally:
            self.updating_text_widgets = False

    def is_split_text_widget(self, widget: tk.Text) -> bool:
        return widget in (
            self.split_row_single_inputs
            + self.split_row_left_inputs
            + self.split_row_right_inputs
        )

    def normalize_split_widget_text(self, widget: tk.Text) -> None:
        text = self.get_text_widget_value(widget)
        single_line_text = " ".join(part for part in text.splitlines() if part)
        if single_line_text != text:
            self.set_text_widget_value(widget, single_line_text)

    def select_all_split_text(self, event: tk.Event) -> str:
        widget = event.widget
        if not isinstance(widget, tk.Text):
            return "break"
        if self.root.focus_get() is widget:
            widget.tag_remove("sel", "1.0", "end")
            widget.mark_set("insert", f"@{event.x},{event.y}")
            return "break"
        widget.focus_set()
        widget.tag_remove("sel", "1.0", "end")
        widget.tag_add("sel", "1.0", "end-1c")
        widget.mark_set("insert", "end-1c")
        return "break"

    def split_text_for_mode(self, text: str) -> tuple[str, str]:
        if "\n" not in text:
            return text, ""
        top_text, bottom_text = text.split("\n", 1)
        return top_text, bottom_text

    def get_today_date_text(self) -> str:
        return current_date.today().strftime("%d/%m/%Y")

    def set_split_cell_value(self, widget: tk.Text, value: str, is_date: bool) -> None:
        widget.configure(bg="#959595" if is_date else self.text_input_background)
        self.set_text_widget_value(widget, self.get_today_date_text() if is_date else value)

    def get_split_cell_render_value(self, widget: tk.Text, is_date: bool) -> str:
        if is_date:
            return self.get_today_date_text()
        return self.get_text_widget_value(widget)

    def get_split_cell_saved_value(self, widget: tk.Text, is_date: bool) -> str:
        if is_date:
            return SETTINGS_DATE_TOKEN
        return self.get_text_widget_value(widget)

    def get_split_cell_date_state(self, row_index: int, cell_name: str) -> bool:
        if cell_name == "single":
            return self.split_row_single_is_date[row_index]
        if cell_name == "left":
            return self.split_row_left_is_date[row_index]
        return self.split_row_right_is_date[row_index]

    def set_split_cell_date_state(self, row_index: int, cell_name: str, is_date: bool) -> None:
        if cell_name == "single":
            self.split_row_single_is_date[row_index] = is_date
        elif cell_name == "left":
            self.split_row_left_is_date[row_index] = is_date
        else:
            self.split_row_right_is_date[row_index] = is_date

    def get_split_cell_widget(self, row_index: int, cell_name: str) -> tk.Text:
        if cell_name == "single":
            return self.split_row_single_inputs[row_index]
        if cell_name == "left":
            return self.split_row_left_inputs[row_index]
        return self.split_row_right_inputs[row_index]

    def block_date_cell_edit(self, event: tk.Event, row_index: int, cell_name: str) -> str | None:
        if self.get_split_cell_date_state(row_index, cell_name):
            return "break"
        return None

    def toggle_split_cell_date(self, _event: tk.Event, row_index: int, cell_name: str) -> str:
        widget = self.get_split_cell_widget(row_index, cell_name)
        is_date = self.get_split_cell_date_state(row_index, cell_name)
        next_is_date = not is_date
        next_value = self.get_today_date_text() if is_date else ""
        self.set_split_cell_date_state(row_index, cell_name, next_is_date)
        self.set_split_cell_value(widget, next_value, next_is_date)
        self.on_settings_changed()
        return "break"

    def build_split_row_widgets(self) -> None:
        for row_index in range(2):
            row_frame = ttk.Frame(self.text_input_container)
            row_frame.columnconfigure(1, weight=1)

            toggle_button = ttk.Button(
                row_frame,
                text="+",
                width=2,
                command=lambda idx=row_index: self.toggle_split_row(idx),
            )
            toggle_button.grid(row=0, column=0, sticky="nw", padx=(0, 6))

            content_frame = ttk.Frame(row_frame)
            content_frame.grid(row=0, column=1, sticky="ew")
            content_frame.columnconfigure(0, weight=1)
            content_frame.columnconfigure(1, weight=1)

            single_input = tk.Text(
                content_frame,
                height=1,
                width=1,
                wrap="word",
                relief="solid",
                bd=1,
                undo=True,
                autoseparators=True,
                maxundo=-1,
            )
            left_input = tk.Text(
                content_frame,
                height=1,
                width=1,
                wrap="word",
                relief="solid",
                bd=1,
                undo=True,
                autoseparators=True,
                maxundo=-1,
            )
            right_input = tk.Text(
                content_frame,
                height=1,
                width=1,
                wrap="word",
                relief="solid",
                bd=1,
                undo=True,
                autoseparators=True,
                maxundo=-1,
            )

            self.split_row_frames.append(row_frame)
            self.split_row_toggle_buttons.append(toggle_button)
            self.split_row_content_frames.append(content_frame)
            self.split_row_single_inputs.append(single_input)
            self.split_row_left_inputs.append(left_input)
            self.split_row_right_inputs.append(right_input)
            self.split_row_states.append(False)
            self.split_row_single_is_date.append(False)
            self.split_row_left_is_date.append(False)
            self.split_row_right_is_date.append(False)

    def normalize_split_text(self, split_text: object, fallback_text: str) -> list[list[str]]:
        normalized: list[list[str]] = []

        if isinstance(split_text, list):
            for row in split_text[:2]:
                if isinstance(row, list):
                    cells = [
                        SETTINGS_DATE_TOKEN if is_settings_date_token(cell) else str(cell)
                        for cell in row[:2]
                    ]
                    normalized.append(cells or [""])
                elif isinstance(row, str):
                    normalized.append([SETTINGS_DATE_TOKEN if is_settings_date_token(row) else row])

        if normalized:
            while len(normalized) < 2:
                normalized.append([""])
            return normalized

        return split_text_into_rows(fallback_text)

    def load_split_rows_from_settings(self) -> None:
        split_text = self.normalize_split_text(self.settings.get("split_text"), self.settings["text"])
        for row_index, row in enumerate(split_text):
            left_value = row[0] if row else ""
            right_value = row[1] if len(row) > 1 else ""
            row_is_split = len(row) > 1
            self.split_row_states[row_index] = row_is_split
            self.split_row_single_is_date[row_index] = (not row_is_split) and left_value == SETTINGS_DATE_TOKEN
            self.split_row_left_is_date[row_index] = row_is_split and left_value == SETTINGS_DATE_TOKEN
            self.split_row_right_is_date[row_index] = row_is_split and right_value == SETTINGS_DATE_TOKEN
            self.set_split_cell_value(
                self.split_row_single_inputs[row_index],
                "" if left_value == SETTINGS_DATE_TOKEN else str(left_value),
                self.split_row_single_is_date[row_index],
            )
            self.set_split_cell_value(
                self.split_row_left_inputs[row_index],
                "" if left_value == SETTINGS_DATE_TOKEN else str(left_value),
                self.split_row_left_is_date[row_index],
            )
            self.set_split_cell_value(
                self.split_row_right_inputs[row_index],
                "" if right_value == SETTINGS_DATE_TOKEN else str(right_value),
                self.split_row_right_is_date[row_index],
            )
            self.refresh_split_row_ui(row_index)

    def get_split_row_line_text(self, row_index: int) -> str:
        if self.split_row_states[row_index]:
            left_text = self.get_split_cell_render_value(
                self.split_row_left_inputs[row_index],
                self.split_row_left_is_date[row_index],
            )
            right_text = self.get_split_cell_render_value(
                self.split_row_right_inputs[row_index],
                self.split_row_right_is_date[row_index],
            )
            if left_text and right_text:
                return f"{left_text} {right_text}"
            return left_text or right_text
        return self.get_split_cell_render_value(
            self.split_row_single_inputs[row_index],
            self.split_row_single_is_date[row_index],
        )

    def get_split_text_state(self) -> list[list[str]]:
        rows: list[list[str]] = []
        for row_index in range(2):
            if self.split_row_states[row_index]:
                rows.append(
                    [
                        self.get_split_cell_saved_value(
                            self.split_row_left_inputs[row_index],
                            self.split_row_left_is_date[row_index],
                        ),
                        self.get_split_cell_saved_value(
                            self.split_row_right_inputs[row_index],
                            self.split_row_right_is_date[row_index],
                        ),
                    ]
                )
            else:
                rows.append(
                    [
                        self.get_split_cell_saved_value(
                            self.split_row_single_inputs[row_index],
                            self.split_row_single_is_date[row_index],
                        )
                    ]
                )
        return rows

    def refresh_split_row_ui(self, row_index: int) -> None:
        content_frame = self.split_row_content_frames[row_index]
        single_input = self.split_row_single_inputs[row_index]
        left_input = self.split_row_left_inputs[row_index]
        right_input = self.split_row_right_inputs[row_index]

        single_input.grid_forget()
        left_input.grid_forget()
        right_input.grid_forget()

        if self.split_row_states[row_index]:
            left_input.grid(row=0, column=0, sticky="ew", padx=(0, 4))
            right_input.grid(row=0, column=1, sticky="ew", padx=(4, 0))
            self.split_row_toggle_buttons[row_index].configure(text="-")
        else:
            single_input.grid(row=0, column=0, columnspan=2, sticky="ew")
            self.split_row_toggle_buttons[row_index].configure(text="+")

    def toggle_split_row(self, row_index: int) -> None:
        if self.split_row_states[row_index]:
            combined_text = self.get_split_row_line_text(row_index)
            self.split_row_states[row_index] = False
            self.split_row_single_is_date[row_index] = False
            self.set_split_cell_value(self.split_row_single_inputs[row_index], combined_text, False)
        else:
            single_is_date = self.split_row_single_is_date[row_index]
            single_text = self.get_text_widget_value(self.split_row_single_inputs[row_index])
            self.split_row_states[row_index] = True
            self.split_row_single_is_date[row_index] = False
            self.split_row_left_is_date[row_index] = single_is_date
            self.split_row_right_is_date[row_index] = False
            self.set_split_cell_value(self.split_row_left_inputs[row_index], single_text, single_is_date)
            self.set_split_cell_value(self.split_row_right_inputs[row_index], "", False)

        self.refresh_split_row_ui(row_index)
        self.on_settings_changed()

    def get_current_watermark_text(self) -> str:
        if self.text_mode_var.get() == "split":
            return self.get_split_mode_text()
        return self.get_text_widget_value(self.text_input)

    def get_split_mode_text(self) -> str:
        top_text = self.get_split_row_line_text(0)
        bottom_text = self.get_split_row_line_text(1)
        if top_text and bottom_text:
            return f"{top_text}\n{bottom_text}"
        return top_text or bottom_text

    def get_render_settings(self, settings: dict | None = None) -> dict:
        render_settings = (settings or self.settings).copy()
        if render_settings.get("text_mode") == "split":
            render_settings["text"] = self.get_split_mode_text()
        else:
            render_settings["text"] = self.get_text_widget_value(self.text_input)
        return render_settings

    def update_text_mode_ui(self, initializing: bool = False) -> None:
        is_split_mode = self.text_mode_var.get() == "split"
        if is_split_mode:
            self.text_input.grid_forget()
            for row_index, row_frame in enumerate(self.split_row_frames):
                pady = (0, 6) if row_index == 0 else (0, 0)
                row_frame.grid(row=row_index, column=0, sticky="ew", pady=pady)
            self.text_mode_button.configure(text="Normal")
        else:
            for row_frame in self.split_row_frames:
                row_frame.grid_forget()
            self.text_input.grid(row=0, column=0, sticky="ew")
            self.text_mode_button.configure(text="Split")

        if not initializing:
            self.on_settings_changed()

    def toggle_text_mode(self) -> None:
        new_mode = "split" if self.text_mode_var.get() == "normal" else "normal"
        self.text_mode_var.set(new_mode)
        self.update_text_mode_ui()
        if self.source_image is not None:
            if self.render_after_id is not None:
                self.root.after_cancel(self.render_after_id)
                self.render_after_id = None
            self.render_now()

    def on_settings_changed(self, *_args) -> None:
        self.settings = self.get_current_settings()
        self.refresh_control_labels()
        self.update_color_buttons()

        try:
            self.write_settings(self.settings)
        except OSError as exc:
            self.status_var.set(f"Could not save settings: {exc}")
        else:
            self.status_var.set(f"Settings saved to {self.settings_path}")

        self.schedule_render()

    def on_window_configure(self, event: tk.Event) -> None:
        if event.widget is not self.root:
            return
        self.update_main_panel_weights(event.width)
        if self.save_geometry_after_id is not None:
            self.root.after_cancel(self.save_geometry_after_id)
        self.save_geometry_after_id = self.root.after(250, self.persist_window_geometry)

    def update_main_panel_weights(self, width: int | None = None) -> None:
        if self.container is None or self.controls_panel is None:
            return

        if width is None or width <= 1:
            self.root.update_idletasks()
            width = self.root.winfo_width()

        if width < 300:
            left_weight, right_weight = 1, 1
        elif width < 500:
            left_weight, right_weight = 1, 2
        elif width < 1000:
            left_weight, right_weight = 1, 3
        else:
            left_weight, right_weight = 1, 4

        side_panel_width = round(width * right_weight / (left_weight + right_weight))
        side_panel_width = max(SIDE_PANEL_MIN_WIDTH, min(side_panel_width, SIDE_PANEL_MAX_WIDTH))

        self.controls_panel.configure(width=side_panel_width)
        self.container.columnconfigure(0, weight=1)
        self.container.columnconfigure(1, weight=0, minsize=side_panel_width)

    def persist_window_geometry(self) -> None:
        self.save_geometry_after_id = None
        geometry = self.get_window_geometry()
        if self.settings.get("window_geometry") == geometry:
            return

        self.settings["window_geometry"] = geometry
        try:
            self.write_settings(self.settings)
        except OSError as exc:
            self.status_var.set(f"Could not save settings: {exc}")

    def on_close(self) -> None:
        if self.save_geometry_after_id is not None:
            self.root.after_cancel(self.save_geometry_after_id)
            self.save_geometry_after_id = None
        self.persist_window_geometry()
        self.root.destroy()

    def refresh_control_labels(self) -> None:
        self.font_size_label_var.set(f"Font Size: {int(float(self.font_size_var.get()))}")
        self.angle_label_var.set(f"Angle: {int(float(self.angle_var.get()))} deg")
        self.opacity_label_var.set(f"Opacity: {int(float(self.opacity_percent_var.get()))}%")

    def update_color_buttons(self) -> None:
        color = self.color_var.get()
        self.color_button.configure(bg=color, activebackground=color, fg=self.pick_button_text_color(color))
        border_color = self.border_color_var.get().strip()
        if border_color:
            self.border_color_button.configure(
                bg=border_color,
                activebackground=border_color,
                fg=self.pick_button_text_color(border_color),
                text="Border Enabled",
            )
            self.clear_border_button.state(["!disabled"])
        else:
            self.border_color_button.configure(
                bg=self.root.cget("bg"),
                activebackground=self.root.cget("bg"),
                fg="#000000",
                text="Choose Border Color",
            )
            self.clear_border_button.state(["disabled"])

    def add_footer_text(self, parent: ttk.Frame, text: str, column: int, row: int = 0) -> None:
        ttk.Label(parent, text=text).grid(row=row, column=column, sticky="e")

    def add_footer_link(self, parent: ttk.Frame, text: str, url: str, column: int, row: int = 0) -> None:
        link = tk.Label(parent, text=text, fg="#0563c1", cursor="hand2")
        link.grid(row=row, column=column, sticky="e")
        link.bind("<Button-1>", lambda _event: webbrowser.open_new(url))

    def pick_button_text_color(self, color: str) -> str:
        color = color.lstrip("#")
        if len(color) != 6:
            return "#000000"
        red = int(color[0:2], 16)
        green = int(color[2:4], 16)
        blue = int(color[4:6], 16)
        luminance = (0.299 * red) + (0.587 * green) + (0.114 * blue)
        return "#000000" if luminance > 186 else "#ffffff"

    def choose_color(self) -> None:
        _, color = colorchooser.askcolor(color=self.color_var.get(), parent=self.root, title="Choose watermark color")
        if color:
            self.color_var.set(color)

    def choose_border_color(self) -> None:
        initial_color = self.border_color_var.get().strip() or self.color_var.get()
        _, color = colorchooser.askcolor(color=initial_color, parent=self.root, title="Choose text border color")
        if color:
            self.border_color_var.set(color)

    def clear_border_color(self) -> None:
        if self.border_color_var.get():
            self.border_color_var.set("")

    def open_image(self) -> None:
        file_path = filedialog.askopenfilename(title="Open Image", filetypes=IMAGE_FILE_TYPES)
        if file_path:
            self.load_image(Path(file_path))

    def load_image(self, path: Path) -> None:
        logging.info("Loading image: %s", path)
        try:
            with Image.open(path) as image:
                loaded = ImageOps.exif_transpose(image).convert("RGBA")
        except OSError as exc:
            logging.exception("Failed to open image: %s", path)
            messagebox.showerror(APP_TITLE, f"Could not open image:\n{exc}")
            return

        self.source_image = loaded
        self.current_image_path = path
        self.file_var.set(path.name)
        self.status_var.set(f"Loaded {path}")
        self.render_now()

    def on_files_dropped(self, files: list[str]) -> None:
        try:
            logging.info("Drop event received: %r", files)
            if not files:
                logging.warning("Drop event had no files")
                return

            raw_path = files[0]
            path = Path(raw_path)
            logging.info("Drop candidate path: %s", path)
            if not path.exists():
                logging.warning("Dropped path does not exist: %s", path)
                return

            self.root.after(0, lambda: self.load_image(path))
        except Exception:
            logging.exception("Crash inside drag and drop callback")
            messagebox.showerror(APP_TITLE, f"Drag and drop failed.\nLog file:\n{self.log_path}")

    def on_drop_event(self, event) -> str:
        try:
            files = list(self.root.tk.splitlist(event.data))
            self.on_files_dropped(files)
        except Exception:
            logging.exception("Crash inside TkDND drop event")
            messagebox.showerror(APP_TITLE, f"Drag and drop failed.\nLog file:\n{self.log_path}")
        return COPY

    def schedule_render(self) -> None:
        if self.source_image is None:
            return

        if self.render_after_id is not None:
            self.root.after_cancel(self.render_after_id)
        self.render_after_id = self.root.after(60, self.render_now)

    def render_now(self) -> None:
        self.render_after_id = None
        if self.source_image is None:
            self.update_preview_image()
            return

        preview_source, preview_settings = self.build_preview_render_input()
        self.rendered_image = render_watermark(preview_source, preview_settings)
        self.update_preview_image()

    def build_preview_render_input(self) -> tuple[Image.Image, dict]:
        preview_width, preview_height = self.get_preview_render_size()
        source_width, source_height = self.source_image.size
        scale = min(preview_width / source_width, preview_height / source_height, 1.0)

        if scale >= 1.0:
            return self.source_image.copy(), self.get_render_settings()

        preview_size = (
            max(1, int(round(source_width * scale))),
            max(1, int(round(source_height * scale))),
        )
        preview_source = self.source_image.resize(preview_size, Image.Resampling.LANCZOS)
        preview_settings = self.get_render_settings()
        preview_settings["font_size"] = max(8, int(round(self.settings["font_size"] * scale)))
        preview_settings["space_left"] = int(round(self.settings["space_left"] * scale))
        preview_settings["space_right"] = int(round(self.settings["space_right"] * scale))
        preview_settings["space_top"] = int(round(self.settings["space_top"] * scale))
        preview_settings["space_bottom"] = int(round(self.settings["space_bottom"] * scale))
        return preview_source, preview_settings

    def get_preview_render_size(self) -> tuple[int, int]:
        width = self.preview_label.winfo_width() - 24
        height = self.preview_label.winfo_height() - 24
        if width <= 0 or height <= 0:
            return 360, 360
        return max(width, 180), max(height, 180)

    def update_preview_image(self) -> None:
        if self.rendered_image is None:
            self.preview_label.configure(image="", text="No image loaded")
            self.preview_photo = None
            return

        self.preview_photo = ImageTk.PhotoImage(self.rendered_image)
        self.preview_label.configure(image=self.preview_photo, text="")

    def on_preview_resize(self, _event: tk.Event) -> None:
        if self.source_image is not None:
            self.schedule_render()

    def save_image(self) -> None:
        if self.source_image is None:
            messagebox.showinfo(APP_TITLE, "Load an image first.")
            return

        initial_name = "watermarked.png"
        if self.current_image_path is not None:
            initial_name = f"{self.current_image_path.stem}-watermarked.png"

        target = filedialog.asksaveasfilename(
            title="Save Watermarked Image",
            defaultextension=".png",
            initialfile=initial_name,
            filetypes=SAVE_FILE_TYPES,
        )
        if not target:
            return

        output_path = Path(target)
        image_to_save = render_watermark(self.source_image, self.get_render_settings())

        try:
            if output_path.suffix.lower() in {".jpg", ".jpeg"}:
                image_to_save = image_to_save.convert("RGB")
            image_to_save.save(output_path)
        except OSError as exc:
            messagebox.showerror(APP_TITLE, f"Could not save image:\n{exc}")
            return

        self.status_var.set(f"Saved watermarked image to {output_path}")

    def report_callback_exception(self, exc_type, exc_value, exc_traceback) -> None:
        if self.is_debug:
            logging.critical(
                "Tk callback exception",
                exc_info=(exc_type, exc_value, exc_traceback),
            )
        details = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        message = "Unexpected error."
        if self.is_debug:
            message += f"\nLog file:\n{self.log_path}\n\n{details}"
        else:
            message += f"\n\n{details}"
        messagebox.showerror(
            APP_TITLE,
            message,
        )


def main() -> None:
    startup_settings = load_startup_settings()
    log_path = configure_logging(bool(startup_settings.get("isDebug", False)))
    enable_fault_logging(log_path)
    root = TkinterDnD.Tk()
    ttk.Style().theme_use("vista")
    install_exception_logging(log_path)
    WatermarkApp(root, startup_settings)
    root.mainloop()


if __name__ == "__main__":
    main()
