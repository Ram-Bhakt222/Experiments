#!/usr/bin/env python3
"""
Flatten a directory tree into a single folder to make bulk ingestion into Qdrant easier.

The script walks a source directory, copies or moves every file into a destination
folder, and optionally writes a manifest describing the original and new paths.
File name collisions are avoided by appending numeric suffixes.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Flatten a directory tree into a single folder by copying or moving each file "
            "into the destination directory. A manifest can be generated to track "
            "the mapping between original and flattened paths for Qdrant ingestion."
        )
    )
    parser.add_argument("source", type=Path, help="Root directory containing files to flatten")
    parser.add_argument(
        "destination",
        type=Path,
        help="Directory where flattened files will be written (created if missing)",
    )
    parser.add_argument(
        "--mode",
        choices=["copy", "move"],
        default="copy",
        help="Copy files (default) or move them into the destination directory",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        help=(
            "Optional path to a JSONL manifest. Each line will contain the "
            "original path, the flattened path, and the relative path for ingestion."
        ),
    )
    return parser.parse_args()


def ensure_destination(destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    if not destination.is_dir():
        raise ValueError(f"Destination '{destination}' is not a directory")


def build_dest_name(rel_path: Path, used_names: Dict[str, int]) -> str:
    """Generate a collision-safe destination filename from a relative path."""
    base_name = "__".join(rel_path.parts)
    candidate = base_name
    counter = 0

    while candidate in used_names:
        counter += 1
        candidate = f"{base_name}_{counter}"

    used_names[candidate] = counter
    return candidate


def flatten_files(
    source: Path, destination: Path, mode: str = "copy"
) -> Tuple[List[Tuple[Path, Path]], List[str]]:
    """
    Flatten the directory by copying or moving files.

    Returns a tuple containing a list of (source, destination) path pairs and a list of
    error messages encountered during processing.
    """
    used_names: Dict[str, int] = {}
    moves: List[Tuple[Path, Path]] = []
    errors: List[str] = []

    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue

        try:
            rel_path = path.relative_to(source)
            dest_name = build_dest_name(rel_path, used_names)
            dest_path = destination / dest_name

            if mode == "copy":
                shutil.copy2(path, dest_path)
            else:
                shutil.move(path, dest_path)

            moves.append((path, dest_path))
        except Exception as exc:  # noqa: BLE001 - surfacing any unexpected issue
            errors.append(f"Failed to process {path}: {exc}")

    return moves, errors


def write_manifest(moves: Iterable[Tuple[Path, Path]], manifest_path: Path, source: Path) -> None:
    """Write a JSONL manifest that records the original and flattened paths."""
    manifest_entries = []
    for original, flattened in moves:
        manifest_entries.append(
            {
                "original": str(original.resolve()),
                "flattened": str(flattened.resolve()),
                "relative": str(original.relative_to(source)),
            }
        )

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", encoding="utf-8") as manifest_file:
        for entry in manifest_entries:
            manifest_file.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main() -> None:
    args = parse_args()
    ensure_destination(args.destination)
    moves, errors = flatten_files(args.source, args.destination, args.mode)

    if args.manifest:
        write_manifest(moves, args.manifest, args.source)

    print(f"Processed {len(moves)} file(s) into {args.destination}")
    if args.manifest:
        print(f"Manifest written to {args.manifest}")
    if errors:
        print("Encountered errors:")
        for error in errors:
            print(f" - {error}")


if __name__ == "__main__":
    main()
