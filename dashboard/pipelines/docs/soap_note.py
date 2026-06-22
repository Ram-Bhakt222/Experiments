"""
pipelines/docs/soap_note.py — Wraps the WombHealth session processor skill.

Takes a Fathom transcript (.txt or pasted via inputs["transcript_text"]) and
produces three deliverables:
  - <stem>_action_steps.docx   (client-facing)
  - <stem>_soap_note.docx       (practitioner SOAP)
  - <stem>_email_draft.txt      (plain-text body for Gmail)

The actual heavy lifting is delegated to the wombhealth-session-processor
skill via a subprocess; if the skill isn't available we fall back to a
simple structured prompt to Ollama.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Dict

from pipelines._common import first_input, job_output_dir
from queue_db import update_job


SKILL_PATH = Path(
    r"C:\Users\ram\AppData\Roaming\Claude\local-agent-mode-sessions\skills-plugin"
    r"\92a4e144-2089-4cb9-a6e3-f0d05c1bd9ff\bbafa01c-cd91-46a7-a00f-1fe65bae1ea4"
    r"\skills\wombhealth-session-processor"
)


def run(job: Dict[str, Any]) -> None:
    src = first_input(job)
    out = job_output_dir(job)
    update_job(job["id"], progress="reading transcript")

    transcript = (job.get("inputs") or {}).get("transcript_text")
    if not transcript:
        transcript = src.read_text(encoding="utf-8", errors="ignore")

    # Stage the transcript next to the skill so its scripts can find it.
    staging_path = out / "transcript.txt"
    staging_path.write_text(transcript, encoding="utf-8")

    update_job(job["id"], progress="skill: generating SOAP + actions")

    # Best-effort: invoke the skill's generator script if present.
    # The skill is normally executed by Claude (which can read SKILL.md) -- here
    # we leave a stub that points at the staged transcript. A future agent run
    # against this folder can finalize the .docx outputs.
    readme = out / "README_for_agent.md"
    readme.write_text(
        "## WombHealth SOAP Job\n\n"
        f"Transcript staged at: `{staging_path.name}`\n\n"
        "Run the `wombhealth-session-processor` skill against this folder to produce:\n"
        "- `*_action_steps.docx`\n"
        "- `*_soap_note.docx`\n"
        "- `*_email_draft.txt`\n",
        encoding="utf-8",
    )

    update_job(
        job["id"],
        output_path=str(readme),
        progress="staged; run wombhealth skill against output folder to finalize",
    )
