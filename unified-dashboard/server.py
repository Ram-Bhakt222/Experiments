from __future__ import annotations

import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, send_from_directory

ROOT = Path(__file__).parent.resolve()
WORKSPACE = ROOT.parent.parent
PROGRAMMING = WORKSPACE / "Programming Projects"
EXPERIMENTS = WORKSPACE / "Experiments"
HALO_DIR = WORKSPACE / "hair analysis"
DOC_DASHBOARD_DIR = EXPERIMENTS / "dashboard"
N8N_TEMPLATES_DIR = PROGRAMMING / "n8n-templates-main"
AUDIO_DIR = PROGRAMMING / "audio_to_text"
MCMASTER_DIR = PROGRAMMING / "McMaster Deliverables"

load_dotenv(ROOT / ".env")

app = Flask(__name__, static_folder=None)
SERVICE_TIMEOUT = float(os.environ.get("SERVICE_TIMEOUT", "0.4"))


@dataclass(frozen=True)
class Service:
    key: str
    name: str
    url: str
    health_url: str
    description: str
    kind: str
    path: Path | None = None


SERVICES = [
    Service(
        "halo",
        "HALO Hair Analysis",
        "http://localhost:8765",
        "http://localhost:8765/health",
        "Front-of-house portrait, hair, color, image, and video analysis.",
        "app",
        HALO_DIR,
    ),
    Service(
        "halo-admin",
        "HALO Admin",
        "http://localhost:8765/admin",
        "http://localhost:8765/health",
        "Stored HALO sessions and generated assets.",
        "admin",
        HALO_DIR,
    ),
    Service(
        "halo-studio",
        "HALO Studio",
        "http://localhost:8765/studio/",
        "http://localhost:8765/health",
        "Back-office stations for transcripts, clips, library, ComfyUI, and n8n.",
        "studio",
        HALO_DIR,
    ),
    Service(
        "doc-dashboard",
        "Doc Dashboard",
        "http://localhost:8900",
        "http://localhost:8900/health",
        "Queued local pipelines for docs, audio, RAG, HALO, Studio, and video splits.",
        "app",
        DOC_DASHBOARD_DIR,
    ),
    Service(
        "ai-video-studio",
        "AI Video Studio",
        "http://localhost:8780",
        "http://localhost:8780/health",
        "Video, avatar, music, upscale, interpolation, and ffmpeg stations.",
        "studio",
    ),
    Service(
        "cockpit",
        "MYN Cockpit",
        "http://localhost:8787",
        "http://localhost:8787",
        "Higher-level local cockpit that links dashboards across the machine.",
        "app",
    ),
    Service(
        "n8n",
        "n8n",
        "http://localhost:5678",
        "http://localhost:5678/healthz",
        "Workflow automation runtime for the SEO and ops templates.",
        "runtime",
        N8N_TEMPLATES_DIR,
    ),
    Service(
        "comfyui",
        "ComfyUI",
        "http://localhost:8000",
        "http://localhost:8000/system_stats",
        "Local image workflow runtime used by Studio-style pipelines.",
        "runtime",
    ),
    Service(
        "ollama",
        "Ollama",
        "http://localhost:11434",
        "http://localhost:11434/api/tags",
        "Local LLM and embedding models for chat, batch jobs, and RAG.",
        "runtime",
    ),
    Service(
        "qdrant",
        "Qdrant",
        "http://localhost:6333/dashboard",
        "http://localhost:6333/collections",
        "Local vector database for searchable document and transcript collections.",
        "runtime",
    ),
]


@app.after_request
def no_cache(resp):
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.route("/")
def index():
    return (ROOT / "index.html").read_text(encoding="utf-8")


@app.route("/api/status")
def api_status():
    with ThreadPoolExecutor(max_workers=len(SERVICES)) as executor:
        statuses = list(executor.map(service_status, SERVICES))
    return jsonify(statuses)


@app.route("/api/inventory")
def api_inventory():
    return jsonify(
        {
            "workspace": str(WORKSPACE),
            "generated_at": int(time.time()),
            "summary": inventory_summary(),
            "n8n_templates": n8n_templates(),
            "audio": audio_inventory(),
            "deliverables": deliverables_inventory(),
            "repos": git_repos(),
        }
    )


@app.route("/api/paths")
def api_paths():
    return jsonify(
        {
            "workspace": str(WORKSPACE),
            "halo": str(HALO_DIR),
            "doc_dashboard": str(DOC_DASHBOARD_DIR),
            "n8n_templates": str(N8N_TEMPLATES_DIR),
            "audio_to_text": str(AUDIO_DIR),
            "mcmaster_deliverables": str(MCMASTER_DIR),
        }
    )


@app.route("/static/<path:name>")
def static_file(name: str):
    return send_from_directory(ROOT, name)


@app.route("/health")
def health():
    return jsonify({"ok": True, "name": "unified-dashboard"})


def service_status(service: Service) -> dict[str, Any]:
    started = time.perf_counter()
    result: dict[str, Any] = {
        "key": service.key,
        "name": service.name,
        "url": service.url,
        "health_url": service.health_url,
        "description": service.description,
        "kind": service.kind,
        "path": str(service.path) if service.path else "",
        "exists": bool(service.path.exists()) if service.path else None,
        "online": False,
        "state": "offline",
        "status_code": None,
        "latency_ms": None,
        "error": "",
    }
    try:
        response = requests.get(service.health_url, timeout=SERVICE_TIMEOUT)
        result["status_code"] = response.status_code
        result["latency_ms"] = round((time.perf_counter() - started) * 1000)
        if response.status_code < 500:
            result["online"] = True
            result["state"] = "auth" if response.status_code in (401, 403) else "online"
        else:
            result["state"] = "error"
    except requests.RequestException as exc:
        result["error"] = exc.__class__.__name__
    return result


def inventory_summary() -> dict[str, int]:
    files = list(workspace_files())
    return {
        "files": len(files),
        "readmes": len([p for p in files if p.name.lower() == "readme.md"]),
        "python": len([p for p in files if p.suffix.lower() == ".py"]),
        "html": len([p for p in files if p.suffix.lower() == ".html"]),
        "json": len([p for p in files if p.suffix.lower() == ".json"]),
        "audio": len([p for p in files if p.suffix.lower() in (".mp3", ".m4a", ".wav", ".flac")]),
        "documents": len([p for p in files if p.suffix.lower() in (".pdf", ".docx", ".pptx")]),
    }


def n8n_templates() -> list[dict[str, Any]]:
    if not N8N_TEMPLATES_DIR.exists():
        return []
    rows = []
    for folder in sorted([p for p in N8N_TEMPLATES_DIR.iterdir() if p.is_dir()]):
        readme = folder / "readme.md"
        title = folder.name.replace("-", " ").title()
        if readme.exists():
            title = first_heading(readme) or title
        rows.append(
            {
                "name": folder.name,
                "title": title,
                "path": str(folder),
                "json_files": len(list(folder.glob("*.json"))),
                "html_files": len(list(folder.glob("*.html"))),
                "images": len([p for p in folder.glob("*") if p.suffix.lower() in (".png", ".gif", ".jpg", ".jpeg")]),
            }
        )
    return rows


def audio_inventory() -> dict[str, Any]:
    groups = []
    if AUDIO_DIR.exists():
        for folder in sorted([p for p in AUDIO_DIR.iterdir() if p.is_dir()]):
            transcripts = folder / "transcripts"
            groups.append(
                {
                    "name": folder.name,
                    "path": str(folder),
                    "audio_files": len([p for p in folder.glob("*") if p.suffix.lower() in (".mp3", ".m4a", ".wav", ".flac")]),
                    "transcripts": len(list(transcripts.glob("*.txt"))) if transcripts.exists() else 0,
                }
            )
    return {"path": str(AUDIO_DIR), "groups": groups}


def deliverables_inventory() -> list[dict[str, Any]]:
    if not MCMASTER_DIR.exists():
        return []
    return [
        {"name": p.name, "path": str(p), "kind": p.suffix.lower().lstrip("."), "size_mb": round(p.stat().st_size / 1024 / 1024, 2)}
        for p in sorted(MCMASTER_DIR.iterdir())
        if p.is_file() and p.suffix.lower() in (".pdf", ".docx", ".pptx")
    ]


def git_repos() -> list[dict[str, Any]]:
    repos = [EXPERIMENTS, HALO_DIR]
    rows = []
    for repo in repos:
        if not (repo / ".git").exists():
            continue
        status = run_git(repo, ["status", "--short"])
        branch = run_git(repo, ["branch", "--show-current"]).strip() or "(detached)"
        rows.append(
            {
                "name": repo.name,
                "path": str(repo),
                "branch": branch,
                "dirty": bool(status.strip()),
                "changes": status.splitlines()[:12],
            }
        )
    return rows


def workspace_files():
    skipped = {".git", ".venv", "venv", "__pycache__", "node_modules"}
    for dirpath, dirnames, filenames in os.walk(WORKSPACE):
        dirnames[:] = [name for name in dirnames if name not in skipped and not name.startswith(".")]
        for filename in filenames:
            yield Path(dirpath) / filename


def first_heading(path: Path) -> str:
    try:
        for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if line.startswith("# "):
                return line[2:].strip()
    except OSError:
        return ""
    return ""


def run_git(cwd: Path, args: list[str]) -> str:
    try:
        completed = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, timeout=2)
        return completed.stdout.strip()
    except Exception:
        return ""


if __name__ == "__main__":
    host = os.environ.get("UNIFIED_HOST", "127.0.0.1")
    port = int(os.environ.get("UNIFIED_PORT", "8910"))
    print(f"Unified Dashboard at http://localhost:{port}")
    app.run(host=host, port=port, debug=False, threaded=True)
