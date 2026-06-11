#!/bin/bash
# Marker Converter — first-run installer
# Installs Python 3.12 + marker-pdf + customtkinter into ~/Library/Application Support/MarkerConverter/env
# If PROGRESS_FILE is set, writes "NN|text" lines to it for the progress window (installer-ui)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
UV="$SCRIPT_DIR/uv"

SUPPORT="$HOME/Library/Application Support/MarkerConverter"
VENV="$SUPPORT/env"

mkdir -p "$SUPPORT"

progress() {
    [ -n "${PROGRESS_FILE:-}" ] && echo "$1|$2" >> "$PROGRESS_FILE" || true
}

# Tell uv to store Python and caches inside our support dir (not ~/.local)
export UV_PYTHON_INSTALL_DIR="$SUPPORT/python"
export UV_CACHE_DIR="$SUPPORT/uv-cache"

progress 5 "Installing Python 3.12…"
echo "[1/4] Installing Python 3.12..."
"$UV" python install 3.12

progress 14 "Creating environment…"
echo "[2/4] Creating virtual environment..."
"$UV" venv --python 3.12 "$VENV"

progress 18 "Downloading packages (~2 GB)… This is the longest step"
echo "[3/4] Installing packages (marker-pdf, customtkinter, pyobjc)..."
"$UV" pip install \
    --python "$VENV/bin/python" \
    "marker-pdf[full]==1.10.2" \
    "customtkinter==5.2.2" \
    "pyobjc-framework-Cocoa==12.2"

progress 55 "Downloading ML models (~3.3 GB)…"
echo "[4/4] Downloading ML models (~3 GB, may take a while)..."
"$VENV/bin/python" - <<'PY'
import os

def progress(pct, msg):
    p = os.environ.get("PROGRESS_FILE")
    if p:
        with open(p, "a") as f:
            f.write(f"{pct}|{msg}\n")

# Models download sequentially inside create_model_dict —
# mark the known stages as cache folders appear
from marker.models import create_model_dict
progress(60, "Downloading ML models: page layout, OCR, tables…")
create_model_dict()
progress(97, "Models ready")
print("Models ready.")
PY

touch "$SUPPORT/.installed"
progress 99 "Finishing…"
echo "Setup complete."
