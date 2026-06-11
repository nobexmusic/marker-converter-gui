# Marker Converter

**English** | [Русский](README.ru.md)

A native macOS app for converting documents (PDF, DOCX, PPTX and more) to
Markdown / JSON / HTML. A GUI for [marker-pdf](https://github.com/datalab-to/marker):
pick a file, a folder and a format — get clean Markdown with extracted images.

Light macOS-style interface: fixed 680px window, format segmented control,
animated progress, a result card with an "Open ↗" button, a collapsible log
and a `#` menu bar icon.

## Requirements

- Mac with Apple Silicon (M1 or later)
- macOS 12.0+
- ~10 GB of free space and an internet connection for the first launch

## Installation

1. Mount `MarkerConverter.dmg` and drag the app into `Applications`.
2. First launch: right-click → "Open" (the app is unsigned).
3. Wait 5–15 minutes — the installer downloads Python, packages and ML models (~5 GB)
   on its own. Progress is logged to `~/Library/Logs/MarkerConverter-setup.log`.

After that the app starts instantly. Each macOS user gets their own installation
(`~/Library/Application Support/MarkerConverter`).

## Building the DMG

```bash
./packaging/build.sh
# → ~/Desktop/MarkerConverter.dmg
```

The script builds the .app in a temp folder, downloads a pinned uv version
(with a sha256 check), styles the DMG window (background, icon positions,
volume icon) and sets the app icon on the .dmg file itself.

## Running from sources (for development)

```bash
"$HOME/Library/Application Support/MarkerConverter/env/bin/python" marker-app.py
```

Requires the app's installed env (created by `packaging/setup.sh` or by the
first launch of the installed app).

## Repository layout

```
marker-converter-gui/
├── marker-app.py        # the whole app: UI (customtkinter) + marker_single runner
├── packaging/
│   ├── build.sh         # builds the .app + the styled DMG
│   ├── launcher.sh      # bundle entrypoint: first run → setup.sh, then → python
│   ├── setup.sh         # installs Python 3.12 + marker-pdf + preloads the models
│   ├── Info.plist
│   └── dmg-background.tiff  # DMG window background (1x+2x)
└── assets/
    ├── icon.svg              # icon source, 1024×1024
    ├── AppIcon.icns / .png   # app icon (all sizes + Retina)
    └── StatusBarIconTemplate.svg / .png / @2x.png  # menu bar icon (Template)
```

## How it works

- On first launch `launcher.sh` runs `setup.sh`: installs Python 3.12 via the
  bundled uv, the `marker-pdf[full]==1.10.2`, `customtkinter`, `pyobjc` packages,
  and downloads all ML models — conversion is ready right after the installation.
- The app runs `marker_single <file> --output_dir <folder> --output_format <fmt>`
  (plus `--disable_image_extraction` when the "No images" checkbox is on) and waits
  for the process to finish; its output is streamed to the log with highlighting.
- Result: `<folder>/<name>/<name>.{md,json,html}` with the extracted images next to it.

## License

The code in this repository is licensed under the [MIT License](LICENSE).

Note: this app does not bundle marker itself — the installer downloads
[marker-pdf](https://github.com/datalab-to/marker) at first launch. Marker's code
is GPL-3.0 and its model weights use a modified AI Pubs Open Rail-M license
(free for research, personal use and small startups; see the marker repository
for commercial terms). Your use of marker through this app is subject to those terms.
