"""
pipelines/docs/halo_proxy.py — Forward a portrait to the running HALO server.

HALO already exposes /analyze and /generate-image at HALO_URL (default 8765).
We POST the image, poll, and copy the resulting analysis JSON + any rendered
images back into this job's output folder.
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Dict

import requests

from pipelines._common import first_input, job_output_dir
from queue_db import update_job


def run(job: Dict[str, Any]) -> None:
    halo_url = os.environ.get("HALO_URL", "http://localhost:8765").rstrip("/")
    src = first_input(job)
    out = job_output_dir(job)
    update_job(job["id"], progress=f"posting {src.name} to HALO")

    # 1) Upload + analyze
    with src.open("rb") as f:
        r = requests.post(f"{halo_url}/upload-photo", files={"photo": (src.name, f)}, timeout=120)
    r.raise_for_status()
    photo = r.json()

    update_job(job["id"], progress="HALO analyzing")
    r = requests.post(f"{halo_url}/analyze", json={"photo_path": photo.get("path")}, timeout=300)
    r.raise_for_status()
    analysis = r.json()

    # Persist analysis JSON
    import json as _json
    analysis_path = out / "halo_analysis.json"
    analysis_path.write_text(_json.dumps(analysis, indent=2), encoding="utf-8")

    update_job(
        job["id"],
        output_path=str(analysis_path),
        progress="HALO analysis complete (run style image generation from HALO UI for full report)",
    )
