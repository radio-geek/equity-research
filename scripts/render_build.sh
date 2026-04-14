#!/usr/bin/env bash
# Render.com build: install deps and Playwright Chromium into the repo. Some hosts omit
# gitignored paths from the deploy slug — use scripts/render_start.sh so browsers exist
# at runtime regardless.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# Not a dot-directory: avoid hidden-path quirks; must NOT be in .gitignore if your host
# strips ignored paths from the runtime bundle (Render does).
export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-$ROOT/playwright-browsers}"
echo "PLAYWRIGHT_BROWSERS_PATH=$PLAYWRIGHT_BROWSERS_PATH"
pip install -r "$ROOT/requirements.txt"
cd "$ROOT"
if ! python -m playwright install --with-deps chromium; then
  echo "playwright install --with-deps failed; retrying without system deps..."
  python -m playwright install chromium
fi
if ! find "$PLAYWRIGHT_BROWSERS_PATH" -type f \( -name chrome-headless-shell -o -name chrome \) 2>/dev/null | head -1 | grep -q .; then
  echo "ERROR: Playwright Chromium not found under $PLAYWRIGHT_BROWSERS_PATH after install."
  ls -la "$PLAYWRIGHT_BROWSERS_PATH" 2>/dev/null || echo "(directory missing)"
  exit 1
fi
echo "Playwright Chromium installed and verified."
