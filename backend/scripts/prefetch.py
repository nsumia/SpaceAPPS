"""Fetch and cache all live data (Landsat now-window, SWOT, POWER precipitation, GIBS VIIRS picture) for every
precomputed lake, so the demo runs offline. Idempotent: fresh cache entries are skipped (--force refetches).
  .venv/bin/python -m backend.scripts.prefetch [--force] [--workers 3] [--lake burdur ...] [--demo] [--width 600]
--demo copies the good results + pictures to data/demo_cache/ (committed; seeds an empty live_cache). Only `good`
entries are copied (no failures, no URLs with tokens: none of the sources stores any)."""
import argparse
import json
import os
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout

import requests

from backend.api import live_cache, store
from backend.core import live


def fetch_snapshot(st, lake_id, meta, width, force):
    dest = os.path.join(st.cache_dir, "gibs", f"{lake_id}.jpg")
    if os.path.exists(dest) and not force:
        return "cached"
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    url = live.gibs_image_url(live_cache.lake_cfg(meta), width=width)
    last = None
    for attempt in range(2):
        try:
            r = requests.get(url, timeout=40)
            if r.ok and r.headers.get("content-type", "").startswith("image/") and len(r.content) > 2000:
                with open(dest, "wb") as f:
                    f.write(r.content)
                return f"ok {len(r.content) // 1024} KB"
            last = f"HTTP {r.status_code} {r.headers.get('content-type')} {len(r.content)} B"
        except requests.RequestException as e:
            last = str(e)[:120]
        time.sleep(2 ** attempt)
    return f"FAILED {last}"


def prefetch_one(st, lk, width, force):
    key = lk["id"]
    meta = store.record(st, key)["meta"]
    lid = meta.get("lake_id", key)
    t0 = time.time()
    res = live_cache.get_live(st, lid, meta)
    cards = {n: ("ok" if c.get("ok") else "FAILED") + (" (stale)" if c.get("stale") else "") + (" [cache]" if c.get("cached") else "")
             for n, c in res["cards"].items() if n != "gibs"}
    snap = fetch_snapshot(st, lid, meta, width, force)
    return lk["name"], lid, cards, snap, time.time() - t0


def to_demo(st):
    os.makedirs(os.path.join(st.demo_dir, "gibs"), exist_ok=True)
    n = 0
    for fn in sorted(os.listdir(st.cache_dir)):
        if fn.endswith(".json"):
            c = json.load(open(os.path.join(st.cache_dir, fn)))
            keep = {k: dict(good=v["good"], good_ts=v["good_ts"]) for k, v in c.items() if v.get("good")}
            if keep:
                json.dump(keep, open(os.path.join(st.demo_dir, fn), "w"), separators=(",", ":"))
                n += 1
    g = os.path.join(st.cache_dir, "gibs")
    for fn in sorted(os.listdir(g)) if os.path.isdir(g) else []:
        shutil.copy(os.path.join(g, fn), os.path.join(st.demo_dir, "gibs", fn))
    return n


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--force", action="store_true", help="refetch even when the cache is fresh")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--lake", action="append", help="limit to these aliases/ids")
    ap.add_argument("--lake-timeout", type=int, default=300, help="seconds to wait per lake before giving up on it")
    ap.add_argument("--demo", action="store_true", help="copy the result into data/demo_cache/")
    ap.add_argument("--width", type=int, default=600, help="width of the VIIRS picture in px")
    a = ap.parse_args(argv)
    st = store.Settings()
    if a.force:
        st.live_ttl_s = 0
    lakes = [lk for lk in store.list_lakes(st) if not lk.get("unverified") and (not a.lake or lk["id"] in a.lake or lk.get("alias") in a.lake)]
    t0, bad, warn = time.time(), 0, 0
    ex = ThreadPoolExecutor(a.workers)
    futs = [(lk, ex.submit(prefetch_one, st, lk, a.width, a.force)) for lk in lakes]
    timeouts = 0
    for lk, fut in futs:
        try:
            name, lid, cards, snap, dt = fut.result(timeout=a.lake_timeout)
        except FutureTimeout:      # huge lakes (Balkhash) can take > 10 min per call: give up, report, keep going
            timeouts += 1
            print(f"{lk['name']:28s} TIMEOUT after {a.lake_timeout}s (not cached; rerun with a larger --lake-timeout)", flush=True)
            continue
        # SWOT has no keyless access (Earthdata login): a known gap, reported as a warning, not a failure
        bad += sum("FAILED" in v for n, v in cards.items() if n != "swot") + snap.startswith("FAILED")
        warn += sum("FAILED" in v for n, v in cards.items() if n == "swot")
        print(f"{name:28s} {dt:6.1f}s  " + "  ".join(f"{k}={v}" for k, v in cards.items()) + f"  viirs={snap}", flush=True)
    print(f"prefetched {len(lakes)} lakes in {time.time() - t0:.0f}s; failed items: {bad}; timeouts: {timeouts}; swot warnings (known gap): {warn}")
    if a.demo:
        print(f"demo_cache: {to_demo(st)} lake files -> {st.demo_dir}")
    sys.stdout.flush()
    os._exit(1 if (bad or timeouts) else 0)          # abandoned worker threads must not keep the process alive


if __name__ == "__main__":
    sys.exit(main())
