"""
pipelines/video/video_split.py — Cut one video into multiple clips.

Drop-in replacement for the original cut_clips.py at
  C:\\Users\\ram\\Downloads\\clip maker\\cut_clips.py

That original took a CSV of (type, start, end, label) and ran ffmpeg -c copy
per row. We preserve that exact behavior as `mode=timestamps`, and add four
more modes:

  timestamps    -- (default if a CSV is uploaded) read CSV of start/end/label
  equal         -- N evenly-spaced segments
  fixed         -- consecutive segments of fixed duration (e.g. 60s reels)
  scene         -- ffmpeg scene-detect, then keep top-N scene-change boundaries
  chapters      -- run faster-whisper, group segments into N pseudo-chapters by gap

Uses ffmpeg -c copy (lossless, fast) when start/end are not key-frame-aligned
this can drift by ~1s; switch to re-encode with inputs["reencode"]=true for
exact frame-perfect cuts.

CLI:
  python video_split.py --video INPUT.mp4 --mode equal --n 6 --out clips/
  python video_split.py --video INPUT.mp4 --mode timestamps --csv timestamps.csv --out clips/
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pipelines._common import all_inputs, first_input, job_output_dir
from queue_db import update_job


# ---------- ffmpeg helpers ----------

def _ffprobe_duration(video: Path) -> float:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(video),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def _parse_ts(value) -> float:
    """Accept '90', '1:30', '1:30:45', '00:01:30.500' -> seconds."""
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s:
        return 0.0
    parts = s.split(":")
    parts = [float(p) for p in parts]
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    raise ValueError(f"unparseable timestamp: {value}")


def _safe_name(s: str) -> str:
    s = s.strip()
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", s)
    return s.strip("._-") or "clip"


def _cut(video: Path, start: float, end: float, out_path: Path, reencode: bool = False) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if reencode:
        cmd = [
            "ffmpeg", "-y",
            "-ss", f"{start:.3f}",
            "-to", f"{end:.3f}",
            "-i", str(video),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k",
            str(out_path),
        ]
    else:
        cmd = [
            "ffmpeg", "-y",
            "-ss", f"{start:.3f}",
            "-to", f"{end:.3f}",
            "-i", str(video),
            "-c", "copy",
            str(out_path),
        ]
    subprocess.run(cmd, check=True, capture_output=True)


# ---------- Mode handlers ----------

def _mode_timestamps(video: Path, csv_path: Path, out_dir: Path, reencode: bool, progress) -> List[Path]:
    clips: List[Path] = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    for i, row in enumerate(rows, start=1):
        clip_type = (row.get("type") or "clip").strip() or "clip"
        label = _safe_name(row.get("label") or f"clip_{i}")
        start = _parse_ts(row.get("start"))
        end = _parse_ts(row.get("end"))
        out_path = out_dir / f"{clip_type}_{i:02d}_{label}.mp4"
        progress(f"cut {i}/{len(rows)} {label} [{start:.1f}-{end:.1f}]")
        _cut(video, start, end, out_path, reencode=reencode)
        clips.append(out_path)
    return clips


def _mode_equal(video: Path, n: int, out_dir: Path, reencode: bool, progress) -> List[Path]:
    duration = _ffprobe_duration(video)
    seg = duration / max(1, n)
    clips: List[Path] = []
    for i in range(n):
        start = i * seg
        end = duration if i == n - 1 else (i + 1) * seg
        out_path = out_dir / f"equal_{i+1:02d}.mp4"
        progress(f"cut {i+1}/{n} equal [{start:.1f}-{end:.1f}]")
        _cut(video, start, end, out_path, reencode=reencode)
        clips.append(out_path)
    return clips


def _mode_fixed(video: Path, seconds: float, out_dir: Path, reencode: bool, progress) -> List[Path]:
    duration = _ffprobe_duration(video)
    n = max(1, math.ceil(duration / seconds))
    clips: List[Path] = []
    for i in range(n):
        start = i * seconds
        end = min(duration, (i + 1) * seconds)
        out_path = out_dir / f"fixed_{i+1:03d}.mp4"
        progress(f"cut {i+1}/{n} fixed [{start:.1f}-{end:.1f}]")
        _cut(video, start, end, out_path, reencode=reencode)
        clips.append(out_path)
    return clips


def _detect_scenes(video: Path, threshold: float, progress) -> List[float]:
    """Return list of scene-change timestamps using ffmpeg's `select` filter."""
    cmd = [
        "ffmpeg", "-i", str(video),
        "-filter:v", f"select='gt(scene,{threshold:.3f})',showinfo",
        "-f", "null", "-",
    ]
    progress(f"scene detect (t={threshold})")
    r = subprocess.run(cmd, capture_output=True, text=True)
    # Scene timestamps appear in stderr as "pts_time:XX.XX"
    times = [float(m.group(1)) for m in re.finditer(r"pts_time:([0-9.]+)", r.stderr)]
    return sorted(set(round(t, 2) for t in times))


def _mode_scene(video: Path, threshold: float, max_clips: int, out_dir: Path, reencode: bool, progress) -> List[Path]:
    duration = _ffprobe_duration(video)
    cuts = _detect_scenes(video, threshold, progress)
    boundaries = [0.0] + cuts + [duration]
    # Cap to max_clips, prefer evenly distributed picks
    if max_clips and len(boundaries) - 1 > max_clips:
        step = (len(boundaries) - 1) / max_clips
        picked = [boundaries[int(i * step)] for i in range(max_clips)] + [boundaries[-1]]
        boundaries = sorted(set(picked))
    clips: List[Path] = []
    for i in range(len(boundaries) - 1):
        start, end = boundaries[i], boundaries[i + 1]
        if end - start < 0.5:
            continue
        out_path = out_dir / f"scene_{i+1:03d}.mp4"
        progress(f"cut {i+1}/{len(boundaries)-1} scene [{start:.1f}-{end:.1f}]")
        _cut(video, start, end, out_path, reencode=reencode)
        clips.append(out_path)
    return clips


def _mode_chapters(video: Path, n: int, whisper_model: str, out_dir: Path, reencode: bool, progress) -> List[Path]:
    """Run whisper, group segments by largest pauses into N pseudo-chapters."""
    from faster_whisper import WhisperModel

    progress(f"whisper:{whisper_model} (cpu/int8)")
    model = WhisperModel(whisper_model, device="cpu", compute_type="int8")
    segs, info = model.transcribe(str(video))
    seg_list = [(s.start, s.end, s.text) for s in segs]
    if not seg_list:
        return []

    # Find largest inter-segment gaps and cut there
    gaps = []
    for i in range(len(seg_list) - 1):
        gap = seg_list[i + 1][0] - seg_list[i][1]
        gaps.append((gap, i))
    gaps.sort(reverse=True)
    cut_indices = sorted({i for _g, i in gaps[: max(0, n - 1)]})

    duration = _ffprobe_duration(video)
    boundaries = [0.0]
    for ci in cut_indices:
        boundaries.append(seg_list[ci][1])
    boundaries.append(duration)
    boundaries = sorted(set(boundaries))

    # Drop a transcript next to the clips for reference
    transcript_path = out_dir / "transcript.txt"
    transcript_path.write_text(
        "\n".join(f"[{a:.2f}-{b:.2f}] {t}" for a, b, t in seg_list),
        encoding="utf-8",
    )

    clips: List[Path] = []
    for i in range(len(boundaries) - 1):
        start, end = boundaries[i], boundaries[i + 1]
        # Try to pull a short label from the first few words of this chapter
        label_words = []
        for a, b, t in seg_list:
            if a >= start and label_words == []:
                label_words = (t or "").strip().split()[:4]
            if a >= end:
                break
        label = _safe_name("_".join(label_words) or f"chapter_{i+1}")
        out_path = out_dir / f"chapter_{i+1:02d}_{label}.mp4"
        progress(f"cut chapter {i+1} [{start:.1f}-{end:.1f}] {label}")
        _cut(video, start, end, out_path, reencode=reencode)
        clips.append(out_path)
    return clips


# ---------- Job entrypoint ----------

def run(job: Dict[str, Any]) -> None:
    inputs = job.get("inputs") or {}
    files = all_inputs(job)
    if not files:
        update_job(job["id"], error="no video uploaded", progress="missing video")
        return

    # Auto-detect: if a .csv is in the upload set, default to timestamps mode
    video_candidates = [p for p in files if p.suffix.lower() in (".mp4", ".mov", ".mkv", ".webm", ".m4v")]
    csv_candidates = [p for p in files if p.suffix.lower() == ".csv"]
    if not video_candidates:
        update_job(job["id"], error="no video file in upload", progress="no video")
        return
    video = video_candidates[0]

    mode = (inputs.get("mode") or ("timestamps" if csv_candidates else "equal")).strip().lower()
    reencode = bool(inputs.get("reencode"))
    out_dir = job_output_dir(job) / "clips"
    out_dir.mkdir(parents=True, exist_ok=True)

    def progress(msg: str) -> None:
        update_job(job["id"], progress=msg)

    progress(f"mode={mode} video={video.name}")

    if mode == "timestamps":
        if not csv_candidates:
            update_job(job["id"], error="timestamps mode needs a .csv upload", progress="missing csv")
            return
        clips = _mode_timestamps(video, csv_candidates[0], out_dir, reencode, progress)
    elif mode == "equal":
        n = int(inputs.get("n") or 6)
        clips = _mode_equal(video, n, out_dir, reencode, progress)
    elif mode == "fixed":
        seconds = float(inputs.get("seconds") or 60.0)
        clips = _mode_fixed(video, seconds, out_dir, reencode, progress)
    elif mode == "scene":
        threshold = float(inputs.get("scene_threshold") or 0.3)
        max_clips = int(inputs.get("n") or 0)
        clips = _mode_scene(video, threshold, max_clips, out_dir, reencode, progress)
    elif mode == "chapters":
        n = int(inputs.get("n") or 6)
        whisper_model = (inputs.get("whisper_model") or "base").strip()
        clips = _mode_chapters(video, n, whisper_model, out_dir, reencode, progress)
    else:
        update_job(job["id"], error=f"unknown mode: {mode}", progress="bad mode")
        return

    # Manifest
    manifest = out_dir / "_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "source_video": str(video),
                "mode": mode,
                "reencode": reencode,
                "clips": [str(c) for c in clips],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    # Point output_path at the manifest so the dashboard can link directly
    update_job(
        job["id"],
        output_path=str(manifest),
        progress=f"done ({len(clips)} clips, {mode})",
    )


# ---------- CLI (for back-compat with the original cut_clips.py) ----------

def _cli() -> int:
    p = argparse.ArgumentParser(description="Cut a video into clips (replaces cut_clips.py).")
    p.add_argument("--video", required=True, help="Input video file")
    p.add_argument("--out", default="clips", help="Output directory")
    p.add_argument("--mode", default="timestamps", choices=["timestamps", "equal", "fixed", "scene", "chapters"])
    p.add_argument("--csv", help="Timestamps CSV (mode=timestamps)")
    p.add_argument("--n", type=int, default=6, help="N segments / max scene clips / N chapters")
    p.add_argument("--seconds", type=float, default=60.0, help="Per-clip seconds (mode=fixed)")
    p.add_argument("--scene-threshold", type=float, default=0.3)
    p.add_argument("--whisper-model", default="base")
    p.add_argument("--reencode", action="store_true")
    args = p.parse_args()

    video = Path(args.video).expanduser().resolve()
    out_dir = Path(args.out).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    def progress(msg: str) -> None:
        print(msg, flush=True)

    if args.mode == "timestamps":
        if not args.csv:
            print("--csv required for timestamps mode", file=sys.stderr)
            return 2
        _mode_timestamps(video, Path(args.csv).resolve(), out_dir, args.reencode, progress)
    elif args.mode == "equal":
        _mode_equal(video, args.n, out_dir, args.reencode, progress)
    elif args.mode == "fixed":
        _mode_fixed(video, args.seconds, out_dir, args.reencode, progress)
    elif args.mode == "scene":
        _mode_scene(video, args.scene_threshold, args.n, out_dir, args.reencode, progress)
    elif args.mode == "chapters":
        _mode_chapters(video, args.n, args.whisper_model, out_dir, args.reencode, progress)
    print(f"done: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
