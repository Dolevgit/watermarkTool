# Simple Watermark Tool – Minimal Specification

## Goal
Build a very small desktop application that adds a repeated text watermark to an image.

The application must be:

- Extremely simple
- Fast to develop
- Easy to maintain
- Packaged as a single standalone EXE
- No complex dependencies
- No runtime installations required on the target machine

---

# Option 1 – Recommended Stack (Minimal)

Python
Tkinter (built-in GUI)
Pillow (image processing)

Reasons:

- Very small codebase
- No heavy frameworks
- Native desktop window
- Easy to package into a single EXE
- Reliable and predictable behavior

---

# Minimal Architecture

```
project/

main.py
renderer.py
settings.json
```

Description:

main.py

- Creates the window
- Handles UI
- Loads image
- Triggers rendering
- Saves settings automatically

renderer.py

- Contains the watermark rendering logic only

settings.json

- Stores user preferences automatically

---

# UI Layout

```
+----------------------+----------------------+
|                      |                      |
|                      |  Text input          |
|                      |                      |
|      Image           |  Font size slider    |
|      preview         |                      |
|                      |  Angle slider        |
|                      |                      |
|                      |  Color picker        |
|                      |                      |
|                      |  Opacity slider      |
|                      |                      |
|                      |  Repeat checkbox     |
|                      |                      |
+----------------------+----------------------+
```

Left panel

- Image preview
- Drag and drop image
- Or open image button

Right panel

- Text input
- Font size control
- Angle control
- Color selector
- Opacity control
- Repeat toggle

No menus
No tabs
No advanced features

---

# Application Flow

```
1. Start application
2. Load saved settings
3. User opens image
4. Image is displayed
5. User changes any control
6. Watermark is rendered immediately
7. Settings are saved automatically
```

No manual save button required.

---

# Minimal State

```
settings = {
  "text": "",
  "font_size": 36,
  "angle": 45,
  "color": "#ffffff",
  "opacity": 0.3,
  "repeat": true
}
```

Stored in:

```
settings.json
```

Behavior:

- Loaded automatically on startup
- Saved automatically after every change

---

# Rendering Logic

Single responsibility function:

```
render_watermark(image, settings)
```

Responsibilities:

- Create transparent text layer
- Apply rotation
- Apply opacity
- Draw text
- Merge with image
- Return result

No additional abstraction layers.

---

# Repeat Watermark Logic

If repeat is enabled:

```
for x in range(0, image_width, step):
    for y in range(0, image_height, step):
        draw_text(x, y)
```

If repeat is disabled:

```
draw_text(center_x, center_y)
```

Step value can be calculated as:

```
step = font_size * 4
```

Simple and predictable behavior.

---

# Save Settings (Automatic)

Every UI change triggers:

```
save_settings(settings)
```

Implementation:

```
write settings to settings.json
```

No confirmation dialog
No manual save
No configuration screen

---

# Packaging Requirement – Single EXE

Final deliverable must be:

```
watermark-tool.exe
```

Characteristics:

- Runs on Windows
- No installation required
- No external dependencies
- No Python required on target machine
- Double-click to run

Distribution model:

```
Single file executable
```

---

# Explicit Non-Goals

The application must NOT include:

- Database
- Plugin system
- Themes
- Multi-language support
- Undo history
- Batch processing
- Network features
- Logging framework
- Complex architecture

This is intentionally a very small utility.

---

# Expected Development Time

Experienced developer:

```
2 to 4 hours
```

Polished UI:

```
Half day
```

---

# Summary

This project is intentionally minimal.

Core components only:

```
UI
Render watermark
Auto-save settings
```

Nothing more.

