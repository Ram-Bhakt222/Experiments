"""
pipelines/local_ai/rag_index.py — Index a folder into Qdrant via Ollama embeddings.

Inputs:
  folder       host-side folder path
  collection   Qdrant collection name (default QDRANT_DEFAULT_COLLECTION env)
  glob         filename pattern, default '**/*.txt;**/*.md;**/*.pdf'
                (PDF rough-extracted via pypdf if available)

Writes a CSV manifest of indexed chunks to outputs.
"""
from __future__ import annotations

import csv
import os
import re
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from pipelines._common import job_output_dir
from pipelines.local_ai.ollama_client import embed
from queue_db import update_job

QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
DEFAULT_COLLECTION = os.environ.get("QDRANT_DEFAULT_COLLECTION", "dashboard_docs")
CHUNK_CHARS = 1200
CHUNK_OVERLAP = 200


def _read_file(p: Path) -> str:
    if p.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(p))
            return "\n\n".join((page.extract_text() or "") for page in reader.pages)
        except Exception:
            return ""
    try:
        return p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def _chunks(text: str) -> Iterable[str]:
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return
    i = 0
    while i < len(text):
        yield text[i : i + CHUNK_CHARS]
        i += CHUNK_CHARS - CHUNK_OVERLAP


def _ensure_collection(name: str, dim: int) -> None:
    import requests
    # Check
    r = requests.get(f"{QDRANT_URL}/collections/{name}", timeout=10)
    if r.status_code == 200:
        return
    # Create
    r = requests.put(
        f"{QDRANT_URL}/collections/{name}",
        json={"vectors": {"size": dim, "distance": "Cosine"}},
        timeout=30,
    )
    r.raise_for_status()


def _upsert(name: str, points: List[Dict[str, Any]]) -> None:
    import requests
    r = requests.put(
        f"{QDRANT_URL}/collections/{name}/points?wait=true",
        json={"points": points},
        timeout=120,
    )
    r.raise_for_status()


def run(job: Dict[str, Any]) -> None:
    inputs = job.get("inputs") or {}
    folder = (inputs.get("folder") or "").strip()
    collection = inputs.get("collection") or DEFAULT_COLLECTION
    if not folder or not Path(folder).is_dir():
        update_job(job["id"], error=f"folder not found: {folder}", progress="folder not found")
        return

    out = job_output_dir(job)
    manifest = out / "indexed.csv"

    patterns = ["**/*.txt", "**/*.md", "**/*.pdf"]
    files: List[Path] = []
    for pat in patterns:
        files.extend(Path(folder).glob(pat))
    files = sorted(set(files))
    if not files:
        update_job(job["id"], error="no files in folder", progress="empty folder")
        return

    update_job(job["id"], progress=f"embedding {len(files)} files")
    rows: List[Tuple[str, int, int]] = []  # filename, chunk_idx, chars
    all_points: List[Dict[str, Any]] = []
    dim = 0

    for fi, src in enumerate(files, start=1):
        text = _read_file(src)
        chunk_list = list(_chunks(text))
        if not chunk_list:
            continue
        update_job(job["id"], progress=f"{fi}/{len(files)} {src.name} ({len(chunk_list)} chunks)")
        vecs = embed(chunk_list)
        if vecs and not dim:
            dim = len(vecs[0])
            _ensure_collection(collection, dim)
        for ci, (ch, vec) in enumerate(zip(chunk_list, vecs)):
            if not vec:
                continue
            pid = uuid.uuid4().hex
            all_points.append(
                {
                    "id": pid,
                    "vector": vec,
                    "payload": {
                        "source": str(src),
                        "filename": src.name,
                        "chunk_idx": ci,
                        "text": ch,
                    },
                }
            )
            rows.append((src.name, ci, len(ch)))
        # Flush periodically
        if len(all_points) >= 128:
            _upsert(collection, all_points)
            all_points = []

    if all_points:
        _upsert(collection, all_points)

    with manifest.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["filename", "chunk_idx", "chars"])
        w.writerows(rows)

    update_job(
        job["id"],
        output_path=str(manifest),
        progress=f"indexed {len(rows)} chunks from {len(files)} files into {collection}",
    )
