"""
pipelines/local_ai/ollama_client.py — Thin client for an Ollama server.

Exposes a single chat pipeline (run_chat) and a helper used by batch_llm /
rag_index / classifier. No SDK required — raw HTTP.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List

import requests

from pipelines._common import job_output_dir
from queue_db import update_job

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434").rstrip("/")
DEFAULT_CHAT_MODEL = os.environ.get("OLLAMA_CHAT_MODEL", "llama3.1:8b-instruct-q4_K_M")
DEFAULT_EMBED_MODEL = os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text")


def chat(prompt: str, model: str | None = None, system: str | None = None, keep_alive: str = "5m") -> str:
    payload: Dict[str, Any] = {
        "model": model or DEFAULT_CHAT_MODEL,
        "messages": [],
        "stream": False,
        "keep_alive": keep_alive,
    }
    if system:
        payload["messages"].append({"role": "system", "content": system})
    payload["messages"].append({"role": "user", "content": prompt})
    r = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=600)
    r.raise_for_status()
    data = r.json()
    return (data.get("message") or {}).get("content", "")


def embed(texts: List[str], model: str | None = None) -> List[List[float]]:
    out = []
    for t in texts:
        r = requests.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": model or DEFAULT_EMBED_MODEL, "prompt": t},
            timeout=120,
        )
        r.raise_for_status()
        out.append(r.json().get("embedding") or [])
    return out


def evict(model: str | None = None) -> None:
    """Tell Ollama to unload a model (free VRAM before video jobs)."""
    try:
        requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": model or DEFAULT_CHAT_MODEL, "prompt": "", "keep_alive": 0},
            timeout=15,
        )
    except Exception:
        pass


def run_chat(job: Dict[str, Any]) -> None:
    """Pipeline: ollama-chat — answers a single prompt, writes reply.md."""
    inputs = job.get("inputs") or {}
    prompt = (inputs.get("prompt") or "").strip()
    if not prompt:
        update_job(job["id"], progress="no prompt provided", error="empty prompt")
        return
    model = inputs.get("model") or DEFAULT_CHAT_MODEL

    update_job(job["id"], progress=f"chat -> {model}")
    reply = chat(prompt, model=model)

    out = job_output_dir(job)
    md = out / "reply.md"
    md.write_text(f"# Prompt\n\n{prompt}\n\n---\n\n# Reply\n\n{reply}\n", encoding="utf-8")
    update_job(job["id"], output_path=str(md), progress=f"done ({len(reply)} chars)")
