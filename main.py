from __future__ import annotations

import json
import logging
import os
import sys
import traceback
import faulthandler
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
DEFAULT_SETTINGS = {
    "text": "Build with Codex",
    "font_size": 36,
    "angle": 45,
    "color": "#000000",
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


def load_startup_settings() -> dict:
    settings_path = get_settings_path()
    if not settings_path.exists():
        with settings_path.open("w", encoding="utf-8") as handle:
            json.dump(DEFAULT_SETTINGS, handle, indent=2)
        return DEFAULT_SETTINGS.copy()

    try:
        with settings_path.open("r", encoding="utf-8") as handle:
            loaded = json.load(handle)
    except (json.JSONDecodeError, OSError):
        return DEFAULT_SETTINGS.copy()

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

        self.font_size_var = tk.IntVar(value=self.settings["font_size"])
        self.angle_var = tk.IntVar(value=self.settings["angle"])
        self.opacity_percent_var = tk.IntVar(value=int(round(self.settings["opacity"] * 100)))
        self.color_var = tk.StringVar(value=self.settings["color"])
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
        self.update_color_button()
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
        container = ttk.Frame(self.root, padding=14)
        container.pack(fill="both", expand=True)

        container.columnconfigure(0, weight=1)
        container.columnconfigure(1, weight=2)
        container.rowconfigure(0, weight=1)

        preview_panel = ttk.Frame(container, padding=(0, 0, 14, 0))
        preview_panel.grid(row=0, column=0, sticky="nsew")
        preview_panel.rowconfigure(1, weight=1)
        preview_panel.columnconfigure(0, weight=1)

        controls_panel = ttk.Frame(container, padding=18)
        controls_panel.grid(row=0, column=1, sticky="nsew")
        controls_panel.columnconfigure(0, weight=1)

        ttk.Label(preview_panel, textvariable=self.file_var).grid(row=0, column=0, sticky="w", pady=(0, 8))

        self.preview_label = ttk.Label(
            preview_panel,
            text="No image loaded",
            anchor="center",
            relief="solid",
            padding=10,
            background="#f5f5f5",
        )
        self.preview_label.grid(row=1, column=0, sticky="nsew")
        self.preview_label.bind("<Configure>", self.on_preview_resize)

        preview_actions = ttk.Frame(preview_panel, padding=(0, 10, 0, 0))
        preview_actions.grid(row=2, column=0, sticky="ew")
        preview_actions.columnconfigure(0, weight=1)
        preview_actions.columnconfigure(1, weight=1)

        ttk.Button(preview_actions, text="Open Image", command=self.open_image).grid(
            row=0, column=0, sticky="ew", padx=(0, 6)
        )
        ttk.Button(preview_actions, text="Save As...", command=self.save_image).grid(
            row=0, column=1, sticky="ew", padx=(6, 0)
        )

        ttk.Label(controls_panel, text="Watermark Text").grid(row=0, column=0, sticky="w")
        self.text_input = tk.Text(controls_panel, height=4, width=28, wrap="word", relief="solid", bd=1)
        self.text_input.grid(row=1, column=0, sticky="ew", pady=(4, 14))
        self.text_input.insert("1.0", self.settings["text"])
        self.text_input.edit_modified(False)

        ttk.Label(controls_panel, textvariable=self.font_size_label_var).grid(row=2, column=0, sticky="w")
        ttk.Scale(
            controls_panel,
            from_=12,
            to=160,
            orient="horizontal",
            variable=self.font_size_var,
        ).grid(row=3, column=0, sticky="ew", pady=(4, 14))

        ttk.Label(controls_panel, textvariable=self.angle_label_var).grid(row=4, column=0, sticky="w")
        ttk.Scale(
            controls_panel,
            from_=-90,
            to=90,
            orient="horizontal",
            variable=self.angle_var,
        ).grid(row=5, column=0, sticky="ew", pady=(4, 14))

        ttk.Label(controls_panel, text="Color").grid(row=6, column=0, sticky="w")
        self.color_button = tk.Button(
            controls_panel,
            text="Choose Color",
            command=self.choose_color,
            relief="ridge",
            bd=1,
        )
        self.color_button.grid(row=7, column=0, sticky="ew", pady=(4, 14))

        ttk.Label(controls_panel, textvariable=self.opacity_label_var).grid(row=8, column=0, sticky="w")
        ttk.Scale(
            controls_panel,
            from_=5,
            to=100,
            orient="horizontal",
            variable=self.opacity_percent_var,
        ).grid(row=9, column=0, sticky="ew", pady=(4, 14))

        spacing_frame = ttk.Frame(controls_panel, padding=(0, 0, 0, 6))
        spacing_frame.grid(row=10, column=0, sticky="ew", pady=(0, 12))
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

        ttk.Checkbutton(controls_panel, text="Repeat Across Image", variable=self.repeat_var).grid(
            row=11, column=0, sticky="w", pady=(0, 18)
        )

        instructions = (
            "Changes are applied immediately.\n"
            "Settings save automatically.\n"
            "Drag and drop works on Windows."
        )
        ttk.Label(controls_panel, text=instructions, justify="left").grid(row=12, column=0, sticky="w")

        footer = ttk.Frame(self.root, padding=(14, 0, 14, 10))
        footer.pack(fill="x", side="bottom")
        footer.columnconfigure(0, weight=1)
        ttk.Label(footer, textvariable=self.status_var).grid(row=0, column=0, sticky="w")
        footer_links = ttk.Frame(footer)
        footer_links.grid(row=0, column=1, sticky="e")
        self.add_footer_text(footer_links, "Built with Codex", 0)
        self.add_footer_text(footer_links, " | ", 1)
        self.add_footer_link(footer_links, "@Dolevgit", AUTHOR_GITHUB_URL, 2)
        self.add_footer_text(footer_links, " | ", 3)
        self.add_footer_link(footer_links, "Project on GitHub", PROJECT_GITHUB_URL, 4)
        self.add_footer_text(footer_links, " | ", 5)
        self.add_footer_text(footer_links, f"version {APP_VERSION}", 6)

    def attach_traces(self) -> None:
        self.root.bind("<Configure>", self.on_window_configure)
        for variable in (
            self.font_size_var,
            self.angle_var,
            self.opacity_percent_var,
            self.color_var,
            self.repeat_var,
            self.space_left_var,
            self.space_right_var,
            self.space_top_var,
            self.space_bottom_var,
        ):
            variable.trace_add("write", self.on_settings_changed)
        self.text_input.bind("<<Modified>>", self.on_text_modified)

    def setup_drag_and_drop(self) -> None:
        logging.info("Installing drag and drop hook")
        self.preview_label.drop_target_register(DND_FILES)
        self.preview_label.dnd_bind("<<Drop>>", self.on_drop_event)

    def load_settings(self) -> dict:
        return load_startup_settings()

    def write_settings(self, settings: dict) -> None:
        with self.settings_path.open("w", encoding="utf-8") as handle:
            json.dump(settings, handle, indent=2)

    def get_current_settings(self) -> dict:
        return {
            "text": self.text_input.get("1.0", "end-1c"),
            "font_size": int(float(self.font_size_var.get())),
            "angle": int(float(self.angle_var.get())),
            "color": self.color_var.get(),
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
        if not self.text_input.edit_modified():
            return
        self.text_input.edit_modified(False)
        self.on_settings_changed()

    def on_settings_changed(self, *_args) -> None:
        self.settings = self.get_current_settings()
        self.refresh_control_labels()
        self.update_color_button()

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
        if self.save_geometry_after_id is not None:
            self.root.after_cancel(self.save_geometry_after_id)
        self.save_geometry_after_id = self.root.after(250, self.persist_window_geometry)

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

    def update_color_button(self) -> None:
        color = self.color_var.get()
        self.color_button.configure(bg=color, activebackground=color, fg=self.pick_button_text_color(color))

    def add_footer_text(self, parent: ttk.Frame, text: str, column: int) -> None:
        ttk.Label(parent, text=text).grid(row=0, column=column, sticky="e")

    def add_footer_link(self, parent: ttk.Frame, text: str, url: str, column: int) -> None:
        link = tk.Label(parent, text=text, fg="#0563c1", cursor="hand2")
        link.grid(row=0, column=column, sticky="e")
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
            return self.source_image.copy(), self.settings.copy()

        preview_size = (
            max(1, int(round(source_width * scale))),
            max(1, int(round(source_height * scale))),
        )
        preview_source = self.source_image.resize(preview_size, Image.Resampling.LANCZOS)
        preview_settings = self.settings.copy()
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
        image_to_save = render_watermark(self.source_image, self.settings)

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
