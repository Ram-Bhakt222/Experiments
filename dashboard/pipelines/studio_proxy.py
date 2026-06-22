"""
pipelines/studio_proxy.py — Forward a job to AI Video Studio (localhost:8780).

Inputs:
  station       Studio station name (e.g. "ltx-t2v", "hedra-avatar", "silero-vad")
  inputs_json   JSON string of station inputs (already in Studio's expected shape)

We POST /api/generate/<station> with those inputs, then poll /api/jobs/<id>
until Studio reports completed/failed. The result_url/output_path returned by
Studio is mirrored onto our job so the dashboard can link straight to it.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any, Dict

import requests

from pipelines._common import job_output_dir
from queue_db import update_job

STUDIO_URL = os.environ.get("STUDIO_URL", "http://localhost:8780").rstrip("/")
POLL_INTERVAL = 2.0
POLL_TIMEOUT_S = 60 * 30  # 30 minutes


def run(job: Dict[str, Any]) -> None:
    inputs = job.get("inputs") or {}
    station = (inputs.get("station") or "").strip()
    if not station:
        update_job(job["id"], error="no station provided", progress="missing station")
        return

    payload_raw = inputs.get("inputs_json") or "{}"
    try:
        station_inputs = json.loads(payload_raw) if isinstance(payload_raw, str) else payload_raw
    except Exception as exc:
        update_job(job["id"], error=f"inputs_json parse: {exc}", progress="bad inputs_json")
        return

    update_job(job["id"], progress=f"submit -> studio:{station}")
    r = requests.post(f"{STUDIO_URL}/api/generate/{station}", json=station_inputs, timeout=120)
    r.raise_for_status()
    studio_job = r.json()
    sjob_id = studio_job.get("id") or studio_job.get("job_id")
    if not sjob_id:
        update_job(job["id"], error=f"studio did not return job id: {studio_job}", progress="no job id")
        return

    # Poll
    t0 = time.time()
    last_status = ""
    while time.time() - t0 < POLL_TIMEOUT_S:
        r = requests.get(f"{STUDIO_URL}/api/jobs/{sjob_id}", timeout=30)
        if r.status_code == 404:
            time.sleep(POLL_INTERVAL)
            continue
        r.raise_for_status()
        sj = r.json()
        status = sj.get("status", "")
        progress = sj.get("progress", "")
        if status != last_status or progress:
            update_job(job["id"], progress=f"studio:{status} {progress}")
            last_status = status
        if status in ("completed", "failed"):
            out = job_output_dir(job)
            # Mirror metadata
            (out / "studio_job.json").write_text(json.dumps(sj, indent=2), encoding="utf-8")
            update_job(
                job["id"],
                output_path=sj.get("output_path") or str(out / "studio_job.json"),
                cost_usd=float(sj.get("cost_usd") or 0.0),
                error=sj.get("error"),
                progress=f"studio:{status}",
            )
            if status == "failed":
                raise RuntimeError(sj.get("error") or "studio job failed")
            return
        time.sleep(POLL_INTERVAL)

    raise TimeoutError(f"studio job {sjob_id} did not finish in {POLL_TIMEOUT_S}s")
