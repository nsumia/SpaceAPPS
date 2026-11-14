# Lake Loss Detective (NASA Space Apps 2026)

Work in progress. Original prototype in legacy/; task spec in docs/PROMPT-v2.md.

## Backend (Stage 2)
- `backend/core/` landsat, stats, climate, swot, live, geo (auto UTM, adaptive resolution, lake component), basin (HydroBASINS), lakes (definitions).
- `backend/api/main.py` minimal FastAPI app (`/api/health`, `/docs`): `.venv/bin/uvicorn backend.api.main:app`.
- Precompute a lake record: `.venv/bin/python -m backend.scripts.precompute --lake burdur` (writes `data/lakes/<alias>/`; aliases burdur, aksehir, egirdir, van; the alias maps to the `lake_id` stored in `meta.json`).
- Tests (offline): `tools/run_tests.sh`. HydroBASINS (~360 MB) is downloaded once to `data/raw/` (gitignored).
