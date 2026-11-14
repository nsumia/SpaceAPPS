#!/usr/bin/env bash
# Single test command. Offline (synthetic data only). Exits non-zero on any failure/error.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python
[ -x "$PY" ] || { echo "missing .venv: uv venv --python 3.12 .venv && uv pip install -p .venv/bin/python -r requirements.txt"; exit 2; }
exec "$PY" -m pytest -q -W error::RuntimeWarning tests "$@"
