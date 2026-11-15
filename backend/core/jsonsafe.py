"""One place that keeps NaN / +-Infinity out of JSON.

Python's json module happily writes the non-standard tokens NaN / Infinity, but starlette's JSONResponse refuses them
(`ValueError: Out of range float values are not JSON compliant: nan`, a 500 in production) and browsers' JSON.parse
rejects them. Missing numbers are `null` in every file and every API response; use `sanitize` / `dumps` / `dump`
for writing and `SafeJSONResponse` (default response class of the app) for responses."""
import json
import math

import numpy as np
from starlette.responses import JSONResponse


def sanitize(o):
    """Recursively replace non-finite floats (python or numpy) by None; numpy scalars/arrays become plain python."""
    if isinstance(o, (float, np.floating)):
        return float(o) if math.isfinite(o) else None
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.ndarray):
        return sanitize(o.tolist())
    if isinstance(o, dict):
        return {k: sanitize(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [sanitize(v) for v in o]
    return o


def dumps(o, **kw):
    return json.dumps(sanitize(o), allow_nan=False, **kw)


def dump(o, f, **kw):
    json.dump(sanitize(o), f, allow_nan=False, **kw)


class SafeJSONResponse(JSONResponse):
    """JSONResponse that turns NaN/Inf into null instead of failing with a 500."""

    def render(self, content):
        return json.dumps(sanitize(content), ensure_ascii=False, allow_nan=False, indent=None,
                          separators=(",", ":")).encode("utf-8")
