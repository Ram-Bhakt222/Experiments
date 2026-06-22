"""
pipelines/_common.py — Shared helpers for every pipeline.

A pipeline function takes a job dict and:
  - reads job["input_path"] / job["inputs"]
  - writes outputs under storage/outputs/<job_id>/...
  - calls update_job(job["id"], output_path=..., progress=..., cost_usd=...)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "storage" / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def job_output_dir(job: Dict[str, Any]) -> Path:
    d = OUTPUT_DIR / job["id"]
    d.mkdir(parents=True, exist_ok=True)
    return d


def first_input(job: Dict[str, Any]) -> Path:
    files: List[str] = (job.get("inputs") or {}).get("files") or []
    if files:
        return Path(files[0])
    if job.get("input_path"):
        return Path(job["input_path"])
    raise ValueError("No input file on job")


def all_inputs(job: Dict[str, Any]) -> List[Path]:
    files: List[str] = (job.get("inputs") or {}).get("files") or []
    return [Path(f) for f in files] if files else ([Path(job["input_path"])] if job.get("input_path") else [])


def relative_output(p: Path) -> str:
    """Relative path under storage/outputs, suitable for /outputs/<x> URLs."""
    try:
        return str(p.relative_to(OUTPUT_DIR))
    except ValueError:
        return str(p)
