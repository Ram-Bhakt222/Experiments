"""
pipelines/docs/transcribe.py — Audio -> timestamped TXT/SRT/JSON via faster-whisper.

Ports the logic from Programming Projects/audio_to_text/hotels/transcribe_all.py.
CPU int8 by default for stability; override via env or job inputs.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

from pipelines._common import first_input, job_output_dir, relative_output
from queue_db import update_job


def _format_ts(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",")


def run(job: Dict[str, Any]) -> None:
    from faster_whisper import WhisperModel  # local import: heavy

    input_path = first_input(job)
    out_dir = job_output_dir(job)
    inputs = job.get("inputs") or {}

    model_name = inputs.get("model") or os.environ.get("WHISPER_MODEL", "base")
    device = inputs.get("device") or os.environ.get("WHISPER_DEVICE", "cpu")
    compute = inputs.get("compute") or os.environ.get("WHISPER_COMPUTE", "int8")

    update_job(job["id"], progress=f"loading whisper:{model_name} on {device}")
    model = WhisperModel(model_name, device=device, compute_type=compute)

    update_job(job["id"], progress="transcribing")
    segments, info = model.transcribe(str(input_path))

    stem = input_path.stem
    txt_path = out_dir / f"{stem}.txt"
    srt_path = out_dir / f"{stem}.srt"
    json_path = out_dir / f"{stem}.json"

    segs_serialized = []
    with txt_path.open("w", encoding="utf-8") as f_txt, srt_path.open("w", encoding="utf-8") as f_srt:
        f_txt.write(f"Language: {info.language}\nDuration: {info.duration:.2f} sec\n\n")
        for i, seg in enumerate(segments, start=1):
            line = f"[{seg.start:.2f} → {seg.end:.2f}] {seg.text}\n"
            f_txt.write(line)
            f_srt.write(f"{i}\n{_format_ts(seg.start)} --> {_format_ts(seg.end)}\n{seg.text.strip()}\n\n")
            segs_serialized.append(
                {"start": seg.start, "end": seg.end, "text": seg.text}
            )

    json_path.write_text(
        json.dumps(
            {
                "language": info.language,
                "duration": info.duration,
                "segments": segs_serialized,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    update_job(
        job["id"],
        output_path=str(txt_path),
        progress=f"done ({len(segs_serialized)} segments)",
    )
