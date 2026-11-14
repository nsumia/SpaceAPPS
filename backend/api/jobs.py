"""SQLite job queue (data/jobs.sqlite). One dispatcher thread, max `max_concurrent` (2) analyses at a time.
States: queued -> running -> done | failed. Requests for a lake that already has a queued/running job attach to it."""
import json
import sqlite3
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

SCHEMA = """CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY, lake_id TEXT NOT NULL, status TEXT NOT NULL, progress REAL DEFAULT 0, current_year INTEGER,
  phase TEXT, error TEXT, request TEXT, created REAL, updated REAL)"""
ACTIVE = ("queued", "running")


class JobManager:
    def __init__(self, db_path, runner, max_concurrent=2, start=True):
        self.db_path, self.runner, self.max = db_path, runner, max_concurrent
        self._lock = threading.RLock()
        self._wake = threading.Event()
        self._stop = False
        self._pool = ThreadPoolExecutor(max_workers=max_concurrent)
        self._running = 0
        with self._conn() as c:
            c.execute(SCHEMA)
            c.execute("UPDATE jobs SET status='failed', error='server restarted while the job was running', updated=? "
                      "WHERE status='running'", (time.time(),))
        self._thread = None
        if start:
            self._thread = threading.Thread(target=self._loop, daemon=True, name="job-dispatcher")
            self._thread.start()

    def _conn(self):
        c = sqlite3.connect(self.db_path, timeout=30)
        c.row_factory = sqlite3.Row
        return c

    def submit(self, lake_id, request):
        """Return (job dict, created: bool). Same lake while a job is active -> the existing job."""
        with self._lock, self._conn() as c:
            row = c.execute("SELECT * FROM jobs WHERE lake_id=? AND status IN ('queued','running') ORDER BY created LIMIT 1",
                            (lake_id,)).fetchone()
            if row:
                return dict(row), False
            jid, now = uuid.uuid4().hex[:12], time.time()
            c.execute("INSERT INTO jobs (id, lake_id, status, request, created, updated) VALUES (?,?,?,?,?,?)",
                      (jid, lake_id, "queued", json.dumps(request), now, now))
        self._wake.set()
        return self.get(jid), True

    def get(self, jid):
        with self._conn() as c:
            row = c.execute("SELECT * FROM jobs WHERE id=?", (jid,)).fetchone()
        return dict(row) if row else None

    def update(self, jid, **kw):
        kw["updated"] = time.time()
        with self._conn() as c:
            c.execute(f"UPDATE jobs SET {', '.join(k + '=?' for k in kw)} WHERE id=?", (*kw.values(), jid))

    def _claim(self):
        with self._lock, self._conn() as c:
            if self._running >= self.max:
                return None
            row = c.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY created LIMIT 1").fetchone()
            if not row:
                return None
            c.execute("UPDATE jobs SET status='running', phase='starting', updated=? WHERE id=?", (time.time(), row["id"]))
            self._running += 1
            return dict(row)

    def _run(self, job):
        try:
            self.runner(job["id"], job["lake_id"], json.loads(job["request"]),
                        lambda **kw: self.update(job["id"], **kw))
            self.update(job["id"], status="done", progress=100.0, phase="complete")
        except Exception as e:  # noqa: BLE001
            self.update(job["id"], status="failed", error=str(e)[:500])
        finally:
            with self._lock:
                self._running -= 1
            self._wake.set()

    def run_pending(self):
        """Synchronous dispatch for tests (no thread)."""
        while (job := self._claim()):
            self._run(job)

    def _loop(self):
        while not self._stop:
            job = self._claim()
            if job:
                self._pool.submit(self._run, job)
            else:
                self._wake.wait(1.0)
                self._wake.clear()

    def close(self):
        self._stop = True
        self._wake.set()
        self._pool.shutdown(wait=False, cancel_futures=True)
