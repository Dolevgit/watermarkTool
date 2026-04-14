from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageColor, ImageDraw, ImageFont

try:
    from bidi.algorithm import get_display
except ImportError:
    get_display = None


RTL_RANGES = (
    (0x0590, 0x05FF),  # Hebrew
    (0x0600, 0x06FF),  # Arabic
    (0x0750, 0x077F),  # Arabic Supplement
    (0x08A0, 0x08FF),  # Arabic Extended-A
    (0xFB1D, 0xFDFF),  # Hebrew/Arabic presentation forms
    (0xFE70, 0xFEFF),  # Arabic presentation forms-B
)


def _load_font(size: int) -> ImageFont.ImageFont:
    candidates = [
        "arial.ttf",
        "segoeui.ttf",
        "tahoma.ttf",
        str(Path("C:/Windows/Fonts/arial.ttf")),
        str(Path("C:/Windows/Fonts/segoeui.ttf")),
        str(Path("C:/Windows/Fonts/tahoma.ttf")),
    ]

    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue

    return ImageFont.load_default(size=size)


def _contains_rtl(text: str) -> bool:
    for char in text:
        codepoint = ord(char)
        if any(start <= codepoint <= end for start, end in RTL_RANGES):
            return True
    return False


def _prepare_text_for_rendering(text: str) -> str:
    if not _contains_rtl(text):
        return text

    if get_display is None:
        return "\n".join(line[::-1] for line in text.splitlines())

    return "\n".join(get_display(line, base_dir="R") for line in text.splitlines())


def render_watermark(image: Image.Image, settings: dict) -> Image.Image:
    base = image.convert("RGBA")
    text = (settings.get("text") or "").strip()
    if not text:
        return base
    text = _prepare_text_for_rendering(text)

    font_size = max(8, int(settings.get("font_size", 36)))
    angle = float(settings.get("angle", 45))
    opacity = max(0.0, min(1.0, float(settings.get("opacity", 0.3))))
    repeat = bool(settings.get("repeat", True))
    space_left = max(0, int(settings.get("space_left", 0)))
    space_right = max(0, int(settings.get("space_right", 0)))
    space_top = max(0, int(settings.get("space_top", 0)))
    space_bottom = max(0, int(settings.get("space_bottom", 0)))

    rgb = ImageColor.getrgb(settings.get("color", "#ffffff"))
    border_color = (settings.get("border_color") or "").strip()
    alpha = max(0, min(255, int(round(opacity * 255))))
    fill = (*rgb, alpha)
    stroke_fill = None
    stroke_width = 0
    if border_color:
        stroke_rgb = ImageColor.getrgb(border_color)
        stroke_fill = (*stroke_rgb, alpha)
        stroke_width = max(1, int(round(font_size / 18)))

    width, height = base.size
    diagonal = int(math.ceil(math.hypot(width, height)))
    step = max(font_size * 4, font_size + 20)
    overlay_size = diagonal + (step * 2)

    overlay = Image.new("RGBA", (overlay_size, overlay_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = _load_font(font_size)
    bbox = draw.multiline_textbbox(
        (0, 0),
        text,
        font=font,
        spacing=max(4, font_size // 5),
        align="center",
        stroke_width=stroke_width,
    )
    text_width = int(math.ceil(bbox[2] - bbox[0]))
    text_height = int(math.ceil(bbox[3] - bbox[1]))

    if repeat:
        tile_width = int(max(step, text_width + space_left + space_right))
        tile_height = int(max(step, text_height + space_top + space_bottom))

        for y in range(-tile_height, overlay_size + tile_height, tile_height):
            for x in range(-tile_width, overlay_size + tile_width, tile_width):
                position = (x + space_left - bbox[0], y + space_top - bbox[1])
                draw.multiline_text(
                    position,
                    text,
                    font=font,
                    fill=fill,
                    stroke_width=stroke_width,
                    stroke_fill=stroke_fill,
                    spacing=max(4, font_size // 5),
                    align="center",
                )
    else:
        position = (
            (overlay_size - text_width) / 2 - bbox[0],
            (overlay_size - text_height) / 2 - bbox[1],
        )
        draw.multiline_text(
            position,
            text,
            font=font,
            fill=fill,
            stroke_width=stroke_width,
            stroke_fill=stroke_fill,
            spacing=max(4, font_size // 5),
            align="center",
        )

    rotated = overlay.rotate(angle, resample=Image.Resampling.BICUBIC, expand=False)
    left = (overlay_size - width) // 2
    top = (overlay_size - height) // 2
    watermark_layer = rotated.crop((left, top, left + width, top + height))

    return Image.alpha_composite(base, watermark_layer)
