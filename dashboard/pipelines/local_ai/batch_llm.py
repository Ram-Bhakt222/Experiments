"""
pipelines/local_ai/batch_llm.py — Run one prompt over every file in a folder.

Inputs:
  files          uploaded files OR
  folder         host-side folder path (string)
  glob           filename pattern (default *.txt)
  prompt         prompt template; supports {filename} and {content}
  model          Ollama model

Output: results.csv with [filename, response].
"""
from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List

from pipelines._common import all_inputs, job_output_dir
from pipelines.local_ai.ollama_client import chat
from queue_db import update_job

MAX_CONTENT_CHARS = 16000  # truncate per-file content so Ollama isn't overwhelmed


def _collect(job: Dict[str, Any]) -> List[Path]:
    inputs = job.get("inputs") or {}
    files = all_inputs(job)
    folder = (inputs.get("folder") or "").strip()
    pattern = inputs.get("glob") or "*.txt"
    if folder:
        p = Path(folder)
        if p.is_dir():
            files = list(p.glob(pattern))
    return [f for f in files if f.is_file()]


def run(job: Dict[str, Any]) -> None:
    inputs = job.get("inputs") or {}
    prompt_template = inputs.get("prompt") or "Summarize {filename}:\n\n{content}"
    model = inputs.get("model")
    files = _collect(job)
    if not files:
        update_job(job["id"], error="no files matched", progress="no files matched")
        return

    out = job_output_dir(job)
    csv_path = out / "results.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["filename", "response", "chars"])
        for i, src in enumerate(files, start=1):
            try:
                content = src.read_text(encoding="utf-8", errors="ignore")
            except Exception as exc:
                w.writerow([src.name, f"(read error: {exc})", 0])
                continue
            content = content[:MAX_CONTENT_CHARS]
            prompt = prompt_template.format(filename=src.name, content=content)
            update_job(job["id"], progress=f"{i}/{len(files)} {src.name}")
            try:
                reply = chat(prompt, model=model)
            except Exception as exc:
                reply = f"(llm error: {exc})"
            w.writerow([src.name, reply, len(reply)])

    update_job(job["id"], output_path=str(csv_path), progress=f"done ({len(files)} files)")
