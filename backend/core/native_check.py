"""Import every native-backed dependency the analysis path imports lazily (inside functions).

Those imports only run on the first "Analyze this lake" click, so a missing OS library in the Docker image (production:
`ImportError: libexpat.so.1` from rasterio) stays hidden until a user hits it. The Dockerfile runs
`python -m backend.core.native_check` at build time (fails the Render build) and /api/health reports `analysis_ready`.
"""
import importlib
import sys

MODULES = ("numpy", "scipy.ndimage", "pandas", "pyproj", "shapely", "rasterio", "rasterio.features", "xarray", "dask",
           "pymannkendall", "pyogrio.raw", "PIL", "planetary_computer", "pystac_client", "odc.stac")


def check(modules=MODULES):
    """{module: 'ErrorType: message'} for every module that does not import (empty dict = all fine)."""
    bad = {}
    for m in modules:
        try:
            importlib.import_module(m)
        except Exception as e:  # noqa: BLE001 - ImportError (missing .so), OSError, anything a wheel raises
            bad[m] = f"{type(e).__name__}: {e}"[:300]
    return bad


if __name__ == "__main__":
    problems = check()
    for m, e in problems.items():
        print(f"NATIVE IMPORT FAILED {m}: {e}", file=sys.stderr)
    if problems:
        sys.exit(1)
    print("native imports ok:", ", ".join(MODULES))
