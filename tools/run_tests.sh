#!/usr/bin/env bash
# Single test command. Offline (synthetic data / mocked network). Exits non-zero on any failure/error.
#   backend: pytest (warnings: RuntimeWarning is an error)   frontend: typecheck + vitest
#   e2e (Playwright): runs when a Chromium is available (CHROMIUM_PATH, /usr/bin/chromium, or Playwright's own);
#   set SKIP_E2E=1 to skip. It needs frontend/dist (built here).
set -euo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python
[ -x "$PY" ] || { echo "missing .venv: uv venv --python 3.12 .venv && uv pip install -p .venv/bin/python -r requirements.txt"; exit 2; }
"$PY" -m pytest -q -W error::RuntimeWarning backend/tests "$@"

cd frontend
[ -d node_modules ] || npm ci --no-audit --no-fund
npm run typecheck
npm test
if [ -n "${SKIP_E2E:-}" ]; then echo "e2e: SKIPPED (SKIP_E2E set)"; exit 0; fi
CHROME="${CHROMIUM_PATH:-}"
[ -n "$CHROME" ] || { [ -x /usr/bin/chromium ] && CHROME=/usr/bin/chromium; } || true
if [ -z "$CHROME" ] && ! ls "${PLAYWRIGHT_BROWSERS_PATH:-$HOME/.cache/ms-playwright}"/chromium-* >/dev/null 2>&1; then
  echo "e2e: SKIPPED (no Chromium found; run 'npx playwright install chromium' then 'npm run build && npm run e2e' in frontend/)"; exit 0
fi
npm run build
CHROMIUM_PATH="$CHROME" npm run e2e
