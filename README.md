# Watermark Tool

![ActiveTime logo](Logo.png)

Simple desktop utility for adding repeated text watermarks to images.

No installer is required.

Users can download the Windows EXE from the GitHub Releases page and run it directly.

![App Screenshot](Screenshot.png)

## What It Does

- Open or drag and drop an image
- Add a text watermark
- Repeat the watermark across the image or place a single centered watermark
- Control font size, angle, color, and opacity
- Use multiline watermark text
- Add extra spacing between repeated watermarks:
  - left
  - right
  - top
  - bottom
- Save the result as a new image

## Main Options

- `Watermark Text`: the text drawn on the image
- `Font Size`: watermark text size
- `Angle`: watermark rotation
- `Color`: watermark color
- `Opacity`: watermark transparency
- `Repeat Across Image`: repeat or center the watermark
- `Top / Left / Right / Bottom Space`: extra spacing between repeated watermark copies

## Settings File

The app saves settings automatically in `settings.json`.

Extra setting:

- `isDebug`: when `true`, the app writes a log file; when `false`, no log file is written

## Download For Users

For normal users, the recommended flow is:

1. Open the GitHub repository
2. Go to `Releases`
3. Download `watermark-tool.exe` from the latest release
4. Run it

No Python installation is required for release users.

## Release v1

Suggested first release:

- Tag: `ver-1`
- Release title: `Watermark Tool ver-1`
- Release asset: `dist/watermark-tool.exe`

Suggested short release text:

`First public release of the Watermark Tool. Includes drag and drop, multiline watermark text, repeat spacing controls, auto-saved settings, and a standalone Windows EXE.`

## Development

Requirements:

- Python 3
- Pillow
- tkinterdnd2
- PyInstaller

Install:

```bash
pip install -r requirements.txt
```

Run:

```bash
python main.py
```

Build EXE:

```bash
python -m PyInstaller watermark-tool.spec
```

The spec file includes the EXE icon and bundles `AppIcons/app.ico` so the built app also has the runtime window icon.

## Known Issues

- Live preview performance can be slow.

## Project Files

- `main.py`: app window, UI, settings, drag and drop
- `renderer.py`: watermark rendering logic
- `settings.json`: default saved settings

Built with Codex.
