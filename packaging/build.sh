#!/bin/bash
# Marker Converter — builds the .app and .dmg
# Usage: ./packaging/build.sh (works from any directory)
# Output: ~/Desktop/MarkerConverter.dmg
set -euo pipefail

APP_NAME="Marker Converter"
PKG_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$PKG_DIR")"
ASSETS_DIR="$ROOT_DIR/assets"

# uv pin: version + sha256 (integrity check of the downloaded binary)
UV_VERSION="0.11.19"
UV_SHA256="d8f59c38e8c4168ee468d423cd63184be12fa6995a4283d41ee1a14d003c9453"

# Build in a temp dir — NOT in /Applications: otherwise the copy is owned by
# the building user and breaks installation for other accounts
STAGE=$(mktemp -d)
APP="$STAGE/$APP_NAME.app"
DMG="$HOME/Desktop/MarkerConverter.dmg"
DMG_RW=$(mktemp -u).dmg
MOUNT_DIR=""

cleanup() {
  # Leave no mounted volumes or temp files behind, whatever the outcome
  [ -n "$MOUNT_DIR" ] && [ -d "$MOUNT_DIR" ] && hdiutil detach "$MOUNT_DIR" -force >/dev/null 2>&1 || true
  rm -f "$DMG_RW"
  rm -rf "$STAGE"
}
trap cleanup EXIT

echo "=== Marker Converter Build ==="
echo ""

# ── Step 1: .app structure ────────────────────────────────────────────────
echo "[1/4] Creating .app structure..."
mkdir -p "$APP/Contents/MacOS"
mkdir -p "$APP/Contents/Resources"

# ── Step 2: Copy files ────────────────────────────────────────────────────
echo "[2/4] Copying files..."

cp "$PKG_DIR/Info.plist"     "$APP/Contents/Info.plist"
cp "$ROOT_DIR/marker-app.py" "$APP/Contents/Resources/marker-app.py"
cp "$PKG_DIR/setup.sh"       "$APP/Contents/Resources/setup.sh"
cp "$ASSETS_DIR/AppIcon.icns"                 "$APP/Contents/Resources/AppIcon.icns"
cp "$ASSETS_DIR/StatusBarIconTemplate.png"    "$APP/Contents/Resources/"
cp "$ASSETS_DIR/StatusBarIconTemplate@2x.png" "$APP/Contents/Resources/"

# Launcher
cp "$PKG_DIR/launcher.sh"    "$APP/Contents/MacOS/$APP_NAME"
chmod +x "$APP/Contents/MacOS/$APP_NAME"
chmod +x "$APP/Contents/Resources/setup.sh"

# Installation progress window (Swift; ld ad-hoc signs it automatically)
if xcrun -f swiftc >/dev/null 2>&1; then
  echo "      compiling installer-ui..."
  swiftc -O "$PKG_DIR/installer-ui.swift" -o "$APP/Contents/Resources/installer-ui"
  chmod +x "$APP/Contents/Resources/installer-ui"
else
  echo "⚠ swiftc not available — setup will run without a progress window (fallback: notifications)"
fi

# ── Step 3: Download uv (Apple Silicon, pinned version and sha256) ────────
echo "[3/4] Downloading uv $UV_VERSION (Apple Silicon)..."
UV_URL="https://github.com/astral-sh/uv/releases/download/$UV_VERSION/uv-aarch64-apple-darwin.tar.gz"
UV_TMP=$(mktemp -d)
curl -fsSL "$UV_URL" -o "$UV_TMP/uv.tar.gz"
echo "$UV_SHA256  $UV_TMP/uv.tar.gz" | shasum -a 256 -c - >/dev/null \
  || { echo "✗ sha256 mismatch — the uv download is corrupted or tampered with"; exit 1; }
tar -xf "$UV_TMP/uv.tar.gz" -C "$UV_TMP"
cp "$UV_TMP/uv-aarch64-apple-darwin/uv" "$APP/Contents/Resources/uv"
chmod +x "$APP/Contents/Resources/uv"
rm -rf "$UV_TMP"

# Permissions: readable and executable for all users
chmod -R u+rwX,go+rX "$APP"

# ── Step 4: Build the DMG (styled Finder window) ──────────────────────────
echo "[4/4] Building DMG..."

ln -s /Applications "$STAGE/Applications"
mkdir "$STAGE/.background"
cp "$PKG_DIR/dmg-background.tiff" "$STAGE/.background/background.tiff"

# Stale volumes with the same name would hijack the AppleScript (Finder addresses by name)
for v in "/Volumes/$APP_NAME"*; do
  [ -d "$v" ] && hdiutil detach "$v" -force >/dev/null 2>&1 || true
done

hdiutil create -volname "$APP_NAME" -srcfolder "$STAGE" \
  -ov -format UDRW -fs HFS+ "$DMG_RW" >/dev/null
MOUNT_DIR=$(hdiutil attach "$DMG_RW" -readwrite -noautoopen | awk -F'\t' '/\/Volumes\//{print $NF}')
[ -n "$MOUNT_DIR" ] && [ -d "$MOUNT_DIR" ] \
  || { echo "✗ Failed to determine the DMG mount point"; exit 1; }
VOL_NAME=$(basename "$MOUNT_DIR")

# Volume icon
cp "$ASSETS_DIR/AppIcon.icns" "$MOUNT_DIR/.VolumeIcon.icns"
SetFile -a C "$MOUNT_DIR" 2>/dev/null || true

# Finder: background, icon size, positions (app on the left, Applications on the right)
osascript <<OSA || echo "⚠ Could not style the window (no Finder access?) — the DMG will be unstyled"
tell application "Finder"
  tell disk "$VOL_NAME"
    open
    set current view of container window to icon view
    set toolbar visible of container window to false
    set statusbar visible of container window to false
    set the bounds of container window to {200, 120, 760, 508}
    set viewOptions to the icon view options of container window
    set arrangement of viewOptions to not arranged
    set icon size of viewOptions to 100
    set text size of viewOptions to 12
    set background picture of viewOptions to POSIX file "$MOUNT_DIR/.background/background.tiff"
    set position of item "$APP_NAME.app" of container window to {140, 165}
    set position of item "Applications" of container window to {420, 165}
    update without registering applications
    delay 1
    close
  end tell
end tell
OSA

sync
# Finder may hold file descriptors for a couple of seconds after styling — retry with pauses
detached=0
for _ in 1 2 3 4 5; do
  if hdiutil detach "$MOUNT_DIR" >/dev/null 2>&1; then detached=1; break; fi
  sleep 2
done
[ "$detached" = 1 ] || { echo "✗ Failed to detach $MOUNT_DIR"; exit 1; }
MOUNT_DIR=""

hdiutil convert "$DMG_RW" -format UDZO -imagekey zlib-level=9 -ov -o "$DMG" >/dev/null

# Icon for the .dmg file itself (resource fork + Finder flag)
APP_PY="$HOME/Library/Application Support/MarkerConverter/env/bin/python"
if [ -x "$APP_PY" ]; then
  ICNS="$ASSETS_DIR/AppIcon.icns" DMG_PATH="$DMG" "$APP_PY" - <<'PY' || echo "⚠ Failed to set the DMG file icon"
import os
from AppKit import NSWorkspace, NSImage
img = NSImage.alloc().initWithContentsOfFile_(os.environ["ICNS"])
ok = NSWorkspace.sharedWorkspace().setIcon_forFile_options_(img, os.environ["DMG_PATH"], 0)
raise SystemExit(0 if ok else 1)
PY
else
  echo "⚠ Python with pyobjc not found — the DMG file keeps the default icon"
fi

echo ""
echo "✓ Done! File: ~/Desktop/MarkerConverter.dmg"
du -sh "$DMG"
