"""
queue_db.py — SQLite-backed job queue.

One table, one worker thread (GPU jobs serialize). Mirrors the field set on
AI Video Studio's Job class so the two systems play nicely.

Public API:
    init_db()
    create_job(user, pipeline, input_path, inputs_json) -> job dict
    update_job(job_id, **fields)
    get_job(job_id) -> dict | None
    list_jobs(limit=100) -> list[dict]
    next_queued() -> dict | None
    register(pipeline_name, fn)             # fn(job) -> None
    start_worker()
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

DB_PATH = Path(__file__).parent / "storage" / "jobs.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

_lock = threading.RLock()
_registry: Dict[str, Callable[[Dict[str, Any]], None]] = {}
_worker_started = False


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(DB_PATH))
    c.row_factory = sqlite3.Row
    return c


def init_db() -> None:
    with _lock, _conn() as c:
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                user TEXT,
                pipeline TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                input_path TEXT,
                inputs_json TEXT,
                output_path TEXT,
                progress TEXT DEFAULT '',
                error TEXT,
                cost_usd REAL DEFAULT 0,
                created_at TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT
            )
            """
        )
        c.execute("CREATE INDEX IF NOT EXISTS idx_status ON jobs(status)")


def _row_to_dict(row: sqlite3.Row | None) -> Optional[Dict[str, Any]]:
    if row is None:
        return None
    d = dict(row)
    try:
        d["inputs"] = json.loads(d.get("inputs_json") or "{}")
    except Exception:
        d["inputs"] = {}
    return d


def create_job(user: str, pipeline: str, input_path: str = "", inputs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    job_id = uuid.uuid4().hex[:12]
    now = datetime.utcnow().isoformat() + "Z"
    with _lock, _conn() as c:
        c.execute(
            "INSERT INTO jobs (id,user,pipeline,status,input_path,inputs_json,created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (job_id, user, pipeline, "queued", input_path, json.dumps(inputs or {}), now),
        )
    return get_job(job_id)  # type: ignore[return-value]


def update_job(job_id: str, **fields: Any) -> None:
    if not fields:
        return
    sets = ", ".join(f"{k} = ?" for k in fields)
    params = list(fields.values()) + [job_id]
    with _lock, _conn() as c:
        c.execute(f"UPDATE jobs SET {sets} WHERE id = ?", params)


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    with _lock, _conn() as c:
        row = c.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return _row_to_dict(row)


def list_jobs(limit: int = 100) -> List[Dict[str, Any]]:
    with _lock, _conn() as c:
        rows = c.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [_row_to_dict(r) for r in rows]  # type: ignore[misc]


def next_queued() -> Optional[Dict[str, Any]]:
    with _lock, _conn() as c:
        row = c.execute(
            "SELECT * FROM jobs WHERE status = 'queued' ORDER BY created_at ASC LIMIT 1"
        ).fetchone()
    return _row_to_dict(row)


def register(pipeline_name: str, fn: Callable[[Dict[str, Any]], None]) -> None:
    _registry[pipeline_name] = fn


def _run_one(job: Dict[str, Any]) -> None:
    pipeline = job["pipeline"]
    fn = _registry.get(pipeline)
    if fn is None:
        update_job(
            job["id"],
            status="failed",
            error=f"No handler registered for pipeline '{pipeline}'",
            finished_at=datetime.utcnow().isoformat() + "Z",
        )
        return
    update_job(job["id"], status="running", started_at=datetime.utcnow().isoformat() + "Z", progress="started")
    try:
        fn(job)
        fresh = get_job(job["id"]) or job
        if fresh["status"] == "running":
            update_job(
                job["id"], status="completed", finished_at=datetime.utcnow().isoformat() + "Z", progress="done"
            )
    except Exception as exc:
        update_job(
            job["id"],
            status="failed",
            error=f"{exc}\n{traceback.format_exc()}",
            finished_at=datetime.utcnow().isoformat() + "Z",
            progress=f"error: {exc}",
        )


def _worker_loop() -> None:
    while True:
        job = next_queued()
        if job is None:
            time.sleep(1.0)
            continue
        _run_one(job)


def start_worker() -> None:
    global _worker_started
    if _worker_started:
        return
    _worker_started = True
    t = threading.Thread(target=_worker_loop, daemon=True, name="job-worker")
    t.start()
