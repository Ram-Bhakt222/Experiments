"""
server.py — Doc Dashboard Flask app.

Local Flask + browser, HALO/Studio shape. Tile UI lives in index.html.
Pipelines are registered in queue_db; the worker thread runs them serially.

Run:  python server.py
Or:   Run Dashboard.bat
"""
from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory

# Load env from .env if present
load_dotenv(Path(__file__).parent / ".env")

from auth import current_user, requires_auth  # noqa: E402
from queue_db import (  # noqa: E402
    create_job,
    get_job,
    init_db,
    list_jobs,
    register,
    start_worker,
)

# ---------- Pipelines ----------
from pipelines.docs.transcribe import run as run_transcribe  # noqa: E402
from pipelines.docs.pdf_extract import run as run_pdf  # noqa: E402
from pipelines.docs.docx_extract import run as run_docx  # noqa: E402
from pipelines.docs.pptx_extract import run as run_pptx  # noqa: E402
from pipelines.docs.soap_note import run as run_soap  # noqa: E402
from pipelines.docs.halo_proxy import run as run_halo  # noqa: E402
from pipelines.local_ai.ollama_client import run_chat as run_ollama_chat  # noqa: E402
from pipelines.local_ai.batch_llm import run as run_batch_llm  # noqa: E402
from pipelines.local_ai.rag_index import run as run_rag  # noqa: E402
from pipelines.local_ai.classifier import run as run_classify  # noqa: E402
from pipelines.studio_proxy import run as run_studio  # noqa: E402
from pipelines.video.video_split import run as run_video_split  # noqa: E402

PIPELINES = {
    "transcribe":   ("Audio → Transcript",      "audio",  run_transcribe),
    "pdf-extract":  ("PDF → Text + Tables",    "pdf",    run_pdf),
    "docx-extract": ("DOCX → Markdown",         "docx",   run_docx),
    "pptx-extract": ("PPTX → Outline",          "pptx",   run_pptx),
    "soap-note":    ("Session → SOAP + Actions","docs",   run_soap),
    "halo-proxy":   ("Portrait → HALO Report",  "image",  run_halo),
    "ollama-chat":  ("Local Chat (Ollama)",         "ai",     run_ollama_chat),
    "batch-llm":    ("Batch LLM over Folder",       "ai",     run_batch_llm),
    "rag-index":    ("RAG: index a folder",         "ai",     run_rag),
    "classifier":   ("LLM File Classifier",         "ai",     run_classify),
    "studio":       ("AI Video Studio Job",         "video",  run_studio),
    "video-split":  ("Video → Clips",           "video",  run_video_split),
}

# Wire pipelines into the queue
init_db()
for name, (_label, _kind, fn) in PIPELINES.items():
    register(name, fn)
start_worker()

# ---------- Flask ----------
ROOT = Path(__file__).parent
UPLOAD_DIR = ROOT / "storage" / "uploads"
OUTPUT_DIR = ROOT / "storage" / "outputs"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__, static_folder=None)


@app.after_request
def _no_cache(resp):
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.route("/")
@requires_auth
def index():
    return (ROOT / "index.html").read_text(encoding="utf-8")


@app.route("/how-to")
@requires_auth
def how_to():
    return (ROOT / "how_to.html").read_text(encoding="utf-8")


@app.route("/api/pipelines")
@requires_auth
def api_pipelines():
    return jsonify(
        [
            {"name": name, "label": label, "kind": kind}
            for name, (label, kind, _fn) in PIPELINES.items()
        ]
    )


@app.route("/api/jobs")
@requires_auth
def api_jobs():
    return jsonify(list_jobs(limit=200))


@app.route("/api/jobs/<job_id>")
@requires_auth
def api_job(job_id: str):
    job = get_job(job_id)
    if not job:
        return jsonify({"error": "not found"}), 404
    return jsonify(job)


@app.route("/api/upload", methods=["POST"])
@requires_auth
def api_upload():
    pipeline = request.form.get("pipeline", "").strip()
    if pipeline not in PIPELINES:
        return jsonify({"error": f"unknown pipeline: {pipeline}"}), 400

    job_id_seed = uuid.uuid4().hex[:12]
    job_uploads = UPLOAD_DIR / job_id_seed
    job_uploads.mkdir(parents=True, exist_ok=True)

    saved = []
    for key in request.files:
        f = request.files[key]
        if not f or not f.filename:
            continue
        dest = job_uploads / f.filename
        f.save(dest)
        saved.append(str(dest))

    # Optional structured inputs (JSON-encoded) for pipelines that need params
    import json as _json
    extra_inputs = {}
    raw = request.form.get("inputs")
    if raw:
        try:
            extra_inputs = _json.loads(raw)
        except Exception:
            extra_inputs = {}

    primary = saved[0] if saved else ""
    inputs = {"files": saved, **extra_inputs}
    job = create_job(
        user=current_user() or "anon",
        pipeline=pipeline,
        input_path=primary,
        inputs=inputs,
    )
    return jsonify(job)


@app.route("/api/run/<pipeline>", methods=["POST"])
@requires_auth
def api_run(pipeline: str):
    """Pipeline-launch without file upload (e.g. ollama-chat, rag query)."""
    if pipeline not in PIPELINES:
        return jsonify({"error": f"unknown pipeline: {pipeline}"}), 400
    inputs = request.get_json(silent=True) or {}
    job = create_job(
        user=current_user() or "anon",
        pipeline=pipeline,
        input_path=inputs.get("path", ""),
        inputs=inputs,
    )
    return jsonify(job)


@app.route("/outputs/<path:relpath>")
@requires_auth
def serve_output(relpath: str):
    return send_from_directory(OUTPUT_DIR, relpath, as_attachment=False)


@app.route("/health")
def health():
    return jsonify({"ok": True, "pipelines": list(PIPELINES.keys())})


if __name__ == "__main__":
    port = int(os.environ.get("DASHBOARD_PORT", 8900))
    host = os.environ.get("DASHBOARD_HOST", "127.0.0.1")
    app.run(host=host, port=port, debug=False, threaded=True)
