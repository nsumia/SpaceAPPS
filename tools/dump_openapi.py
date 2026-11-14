"""Write the FastAPI OpenAPI schema to a file (used by `npm run gen:api`). Usage: dump_openapi.py out.json"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from backend.api.main import create_app  # noqa: E402
from backend.api.store import Settings  # noqa: E402

app = create_app(Settings(start_worker=False))
with open(sys.argv[1], "w") as f:
    json.dump(app.openapi(), f, indent=1)
