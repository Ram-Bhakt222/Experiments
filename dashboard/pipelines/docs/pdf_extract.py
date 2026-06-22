"""
pipelines/docs/pdf_extract.py — PDF -> text + tables (CSV per table).

Text via pypdf, tables via pdfplumber. Falls back to text-only if tables fail.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict

from pipelines._common import first_input, job_output_dir
from queue_db import update_job


def run(job: Dict[str, Any]) -> None:
    src = first_input(job)
    out = job_output_dir(job)
    update_job(job["id"], progress="extracting text")

    try:
        from pypdf import PdfReader
        reader = PdfReader(str(src))
        text_pages = []
        for i, page in enumerate(reader.pages):
            try:
                text_pages.append(page.extract_text() or "")
            except Exception:
                text_pages.append("")
        text = "\n\n--- PAGE BREAK ---\n\n".join(text_pages)
    except Exception as exc:
        text = f"(pypdf failed: {exc})"
        text_pages = []

    text_path = out / f"{src.stem}.txt"
    text_path.write_text(text, encoding="utf-8")

    # Tables (optional, may fail on scanned PDFs)
    update_job(job["id"], progress="extracting tables")
    tables_dir = out / "tables"
    n_tables = 0
    try:
        import pdfplumber
        with pdfplumber.open(str(src)) as pdf:
            for page_idx, page in enumerate(pdf.pages, start=1):
                for t_idx, tbl in enumerate(page.extract_tables() or [], start=1):
                    if not tbl:
                        continue
                    tables_dir.mkdir(parents=True, exist_ok=True)
                    out_csv = tables_dir / f"page{page_idx:03d}_t{t_idx}.csv"
                    with out_csv.open("w", newline="", encoding="utf-8") as f:
                        csv.writer(f).writerows(tbl)
                    n_tables += 1
    except Exception as exc:
        update_job(job["id"], progress=f"tables skipped: {exc}")

    update_job(
        job["id"],
        output_path=str(text_path),
        progress=f"done ({len(text_pages)} pages, {n_tables} tables)",
    )
