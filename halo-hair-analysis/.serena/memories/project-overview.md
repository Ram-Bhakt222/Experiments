# HALO — Project Overview

**What it is:** Local web app + iOS starter that takes a portrait photo and returns a personalized salon-style consultation. Hair type, face shape, recommended cuts (with photorealistic preview images), styles to avoid, color season, palette, and short hair-motion videos.

**Status (2026-05-14):** Closed beta. Marketing playbook drafted but not yet executed.

## Category positioning

HALO sits in the **consumer-AI-app lane** with Cal AI, Landed AI, and Cluely. The magic moment — "same face, same outfit, same background, twelve haircuts in 60 seconds" — IS the marketing hook. The moat is momentum + distribution speed, not technical novelty (OpenAI or FAL could ship a competing primitive overnight).

## Key files

- `server.py` — Flask backend. Endpoints: `/analyze`, `/upload-photo`, `/generate-image`, `/generate-video`, `/image-status`, `/image-result`, `/video-status`, `/video-result`, `/save-lead`, `/health`.
- `index.html` — single-file frontend (plain HTML + vanilla JS, no build step).
- `Run HALO.bat`, `start-server.bat` — Windows convenience launchers.
- `script/build_and_run.sh` — macOS desktop build (PyInstaller + WebKit window).
- `ios/HALO/` — SwiftUI starter for iPhone app. Credentials stay server-side; iOS only calls the HALO backend.
- `docs/SYSTEM_CHANGES.md` — full system diagram + credential boundary.
- `HALO_MARKETING_PLAYBOOK.md` — canonical marketing playbook (see `halo-marketing-playbook` memory).
- `leads.csv` — captured lead emails (gitignored, runtime-generated).

## Stack

- **Backend:** Flask, OpenAI vision + JSON, FAL.AI (face-preserving image edits + image-to-video)
- **Frontend:** Plain HTML + vanilla JS
- **Desktop (macOS):** PyInstaller + WebKit
- **iOS:** SwiftUI (calls backend; no on-device keys)
- **Optional infra:** Supabase (mentioned in iOS notes; service keys server-side only)

## Cost surface (per analysis)

| Action | ~Cost |
|---|---|
| Hair + color analysis | $0.01 |
| 13 face-preserving style images | $0.50 |
| One video preview | $0.18 |
| **Full run** | **~$0.69** |

## How to run

Set `OPENAI_API_KEY` and `FAL_API_KEY` in `.env`, then double-click `Run HALO.bat` (Windows) or `./script/build_and_run.sh` (macOS) or `python server.py`. Browser opens at `http://localhost:8765`.
