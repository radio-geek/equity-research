#!/usr/bin/env bash
# Render.com (and similar) build: put Playwright browsers inside the repo so they are
# included in the deploy artifact. See README "PDF on Render".
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-$ROOT/.playwright-browsers}"
echo "PLAYWRIGHT_BROWSERS_PATH=$PLAYWRIGHT_BROWSERS_PATH"
pip install -r "$ROOT/requirements.txt"
cd "$ROOT"
# --with-deps installs OS libraries Chromium needs on Debian/Ubuntu (requires apt).
if ! playwright install --with-deps chromium; then
  echo "playwright install --with-deps failed; retrying without system deps..."
  playwright install chromium
fi
echo "Playwright Chromium installed."
