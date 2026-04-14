#!/usr/bin/env bash
# Render.com start: deploy slug may omit browser binaries from the build (e.g. gitignored
# paths). Installing here writes to PLAYWRIGHT_BROWSERS_PATH on the runtime disk. If the
# dashboard left an empty override, this repopulates that directory; otherwise default to
# ./playwright-browsers (matches render_build.sh).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${PYTHONPATH:-.}"
export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-$ROOT/playwright-browsers}"
python -m playwright install chromium
exec python -m uvicorn backend.main:app --host 0.0.0.0 --port "${PORT:-10000}"
