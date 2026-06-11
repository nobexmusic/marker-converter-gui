#!/bin/bash
# Marker Converter launcher
# — On first run: shows the progress window (installer-ui) and installs
#   Python + packages + models via setup.sh; cancellation via a cancel file
# — On subsequent runs: starts the app right away

# The bundle ships uv for aarch64 — on Intel, report the incompatibility honestly.
# Not uname -m: macOS runs script-based .apps under Rosetta, where uname lies.
# hw.optional.arm64 reflects the real hardware.
if [ "$(sysctl -n hw.optional.arm64 2>/dev/null)" != "1" ]; then
    osascript -e 'display alert "Marker Converter" message "This app supports only Macs with Apple Silicon (M1 or later)." as critical' 2>/dev/null || true
    exit 1
fi

RESOURCES="$(cd "$(dirname "$0")/../Resources" && pwd)"
SUPPORT="$HOME/Library/Application Support/MarkerConverter"
INSTALLED="$SUPPORT/.installed"
PYTHON="$SUPPORT/env/bin/python"

if [ ! -f "$INSTALLED" ] || [ ! -f "$PYTHON" ]; then
    mkdir -p "$SUPPORT" "$HOME/Library/Logs"
    LOG="$HOME/Library/Logs/MarkerConverter-setup.log"
    PROGRESS="$SUPPORT/.setup-progress"
    CANCEL="$SUPPORT/.setup-cancel"
    rm -f "$PROGRESS" "$CANCEL"
    echo "2|Preparing…" > "$PROGRESS"

    echo "$(date): Starting setup..." >> "$LOG"

    # Progress window (if built); fallback — a notification
    UI_PID=""
    if [ -x "$RESOURCES/installer-ui" ]; then
        "$RESOURCES/installer-ui" "$PROGRESS" "$CANCEL" &
        UI_PID=$!
    else
        osascript -e 'display notification "Installing packages and models (~5 GB) will take 5–15 minutes. Do not close the app." with title "Marker Converter" subtitle "First launch — setting up…"' 2>/dev/null || true
    fi

    # setup in its own process group — so cancellation kills its children too (uv, python)
    set -m
    PROGRESS_FILE="$PROGRESS" bash "$RESOURCES/setup.sh" >> "$LOG" 2>&1 &
    SETUP_PID=$!
    set +m

    while kill -0 "$SETUP_PID" 2>/dev/null; do
        if [ -f "$CANCEL" ]; then
            echo "$(date): Setup cancelled by user." >> "$LOG"
            kill -TERM -- -"$SETUP_PID" 2>/dev/null || kill -TERM "$SETUP_PID" 2>/dev/null
            sleep 2
            kill -KILL -- -"$SETUP_PID" 2>/dev/null
            [ -n "$UI_PID" ] && kill "$UI_PID" 2>/dev/null
            rm -f "$INSTALLED" "$PROGRESS" "$CANCEL"
            osascript -e 'display notification "Installation cancelled. Launch the app again to continue — the download will resume." with title "Marker Converter"' 2>/dev/null || true
            exit 0
        fi
        sleep 1
    done

    if wait "$SETUP_PID"; then
        echo "$(date): Setup succeeded." >> "$LOG"
        echo "100|Done" >> "$PROGRESS"
        sleep 1
        [ -n "$UI_PID" ] && kill "$UI_PID" 2>/dev/null
        rm -f "$PROGRESS" "$CANCEL"
        osascript -e 'display notification "Done! Launching the converter." with title "Marker Converter"' 2>/dev/null || true
    else
        echo "$(date): Setup FAILED. See $LOG" >> "$LOG"
        [ -n "$UI_PID" ] && kill "$UI_PID" 2>/dev/null
        rm -f "$PROGRESS" "$CANCEL"
        osascript -e "display alert \"Installation failed\" message \"Details: $LOG\" as critical" 2>/dev/null || true
        exit 1
    fi
fi

exec "$PYTHON" "$RESOURCES/marker-app.py"
