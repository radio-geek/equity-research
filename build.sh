#!/usr/bin/env bash
set -e

echo "Installing Python dependencies..."
pip install --no-cache-dir -r requirements.txt

# Playwright: use minimal Chromium (~35-40 MB) instead of full browser bundle (~150+ MB).
# DO NOT run `playwright install` (downloads huge browsers).
# Minimal build is Linux x64 (Render/Docker/CI). On macOS, skip or set CHROMIUM_PATH to a local binary.

CHROMIUM_DIR="${CHROMIUM_DIR:-/opt/chromium}"
CHROMIUM_BIN="${CHROMIUM_DIR}/chromium"

if [ -f "$CHROMIUM_BIN" ]; then
  echo "Chromium already present at $CHROMIUM_BIN, skipping download."
elif [ "$(uname -s)" = "Linux" ] && [ "$(uname -m)" = "x86_64" ]; then
  echo "Creating chromium directory..."
  mkdir -p "$CHROMIUM_DIR"

  echo "Downloading minimal Chromium build (~35-40 MB)..."
  CHROMIUM_URL="https://github.com/Sparticuz/chromium/releases/latest/download/chromium-v131-linux-x64.tar.gz"
  curl -fsSL "$CHROMIUM_URL" -o /tmp/chromium.tar.gz

  echo "Extracting Chromium..."
  tar -xzf /tmp/chromium.tar.gz -C "$CHROMIUM_DIR"
  chmod +x "$CHROMIUM_BIN"
  rm -f /tmp/chromium.tar.gz
  echo "Playwright lightweight setup complete! Chromium at $CHROMIUM_BIN"
else
  # Local builds (e.g. macOS): use Playwright's bundled Chromium so PDF works without setting CHROMIUM_PATH.
  echo "Local build (non-Linux x64): installing Playwright Chromium for PDF..."
  playwright install chromium
  echo "Playwright Chromium installed. App will use it automatically (no CHROMIUM_PATH needed)."
fi
