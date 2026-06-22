"""
pipelines/local_ai/classifier.py — "Sort N files into M buckets" pipeline.

Inputs:
  files     uploaded files (or folder via inputs)
  folder    host-side folder
  buckets   comma-separated bucket names
  model     Ollama model

Writes classifications.csv with [filename, bucket, rationale]. Does NOT move
files — that's a manual step after review.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List

from pipelines._common import all_inputs, job_output_dir
from pipelines.local_ai.ollama_client import chat
from queue_db import update_job

SYSTEM = (
    "You are a file classifier. Given a filename and an excerpt, pick the single "
    "most appropriate bucket from a comma-separated list. Respond as JSON: "
    '{"bucket":"...","reason":"..."}.'
)


def _collect(job: Dict[str, Any]) -> List[Path]:
    inputs = job.get("inputs") or {}
    files = all_inputs(job)
    folder = (inputs.get("folder") or "").strip()
    if folder and Path(folder).is_dir():
        files = [p for p in Path(folder).glob("*") if p.is_file()]
    return files


def run(job: Dict[str, Any]) -> None:
    import json as _json

    inputs = job.get("inputs") or {}
    buckets = [b.strip() for b in (inputs.get("buckets") or "").split(",") if b.strip()]
    if not buckets:
        update_job(job["id"], error="no buckets provided", progress="missing buckets")
        return
    files = _collect(job)
    if not files:
        update_job(job["id"], error="no files", progress="no files")
        return
    model = inputs.get("model")

    out = job_output_dir(job)
    csv_path = out / "classifications.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["filename", "bucket", "rationale"])
        for i, src in enumerate(files, start=1):
            try:
                excerpt = src.read_text(encoding="utf-8", errors="ignore")[:2000]
            except Exception:
                excerpt = ""
            prompt = (
                f"Buckets: {', '.join(buckets)}\n"
                f"Filename: {src.name}\n"
                f"Excerpt:\n{excerpt}\n\n"
                "Pick exactly one bucket. Reply with JSON only."
            )
            update_job(job["id"], progress=f"{i}/{len(files)} {src.name}")
            try:
                reply = chat(prompt, model=model, system=SYSTEM)
                # Extract JSON
                bucket = "unknown"
                reason = reply
                try:
                    start = reply.find("{")
                    end = reply.rfind("}")
                    if start >= 0 and end > start:
                        obj = _json.loads(reply[start : end + 1])
                        bucket = obj.get("bucket", "unknown")
                        reason = obj.get("reason", "")
                except Exception:
                    pass
                w.writerow([src.name, bucket, reason])
            except Exception as exc:
                w.writerow([src.name, "error", str(exc)])

    update_job(job["id"], output_path=str(csv_path), progress=f"done ({len(files)} files)")
