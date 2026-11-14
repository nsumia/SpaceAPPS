"""Live cards with a per-source cache (TTL 3 h) in data/live_cache/<lake_id>.json.
Each source (landsat, swot, precip) is cached and fails independently. Rules per source:
fresh (< TTL) -> cached result, no network; otherwise fetch; fetch ok -> store; fetch failed -> last good result with
stale=true (+ refresh_error), or the failure itself if there never was a good result (retried after RETRY_FAIL_S so a
broken upstream is not hammered on every page load). GIBS URL is computed, no network. FETCHERS is patched in tests."""
import json
import os
import threading
import time
from datetime import datetime, timezone

from backend.core import live

RETRY_FAIL_S = 300
FETCHERS = {"landsat": live.landsat_now, "swot": live.swot_now, "precip": live.precip_now}
_locks, _glock = {}, threading.Lock()


def _lock(key):
    with _glock:
        return _locks.setdefault(key, threading.Lock())


def lake_cfg(meta):
    return dict(name=meta.get("name"), bbox=tuple(meta["bbox"]), seed=tuple(meta["seed"]), pld_id=meta.get("pld_id"))


def _path(st, lake_id):
    os.makedirs(st.cache_dir, exist_ok=True)
    return os.path.join(st.cache_dir, f"{lake_id}.json")


def _read(p):
    try:
        with open(p) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def get_live(st, lake_id, meta, now=None):
    now = time.time() if now is None else now
    cfg = lake_cfg(meta)
    p = _path(st, lake_id)
    with _lock(lake_id):
        cache = _read(p)
        out = {}
        for name, fn in FETCHERS.items():
            ent = cache.get(name, {})
            good, age = ent.get("good"), None
            if good is not None:
                age = now - ent["good_ts"]
                if age < st.live_ttl_s:
                    out[name] = dict(good, cached=True, stale=False, age_s=int(age))
                    continue
            if good is None and ent.get("fail_ts") is not None and now - ent["fail_ts"] < RETRY_FAIL_S:
                out[name] = dict(ent["fail"], cached=True, stale=False, age_s=int(now - ent["fail_ts"]))
                continue
            try:
                res = fn(cfg)
            except Exception as e:  # noqa: BLE001
                res = live._fail(name, e)
            if res.get("ok"):
                ent = dict(good=res, good_ts=now)
                cache[name] = ent
                out[name] = dict(res, cached=False, stale=False, age_s=0)
            elif good is not None:
                cache[name] = dict(ent, last_error=res.get("error"))
                out[name] = dict(good, cached=True, stale=True, age_s=int(age), refresh_error=res.get("error"))
            else:
                cache[name] = dict(ent, fail=res, fail_ts=now)
                out[name] = dict(res, cached=False, stale=False, age_s=0)
        tmp = p + ".tmp"
        with open(tmp, "w") as f:
            json.dump(cache, f)
        os.replace(tmp, p)
    out["gibs"] = dict(live._ok("NASA GIBS VIIRS NOAA-20 true colour", image_url=live.gibs_image_url(cfg)),
                       cached=False, stale=False, age_s=0)
    return dict(lake_id=lake_id, name=meta.get("name"), ttl_s=st.live_ttl_s, stale=any(v.get("stale") for v in out.values()),
                generated_utc=datetime.fromtimestamp(now, timezone.utc).isoformat(timespec="seconds"), cards=out)
