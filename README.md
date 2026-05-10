# HALO — AI Hair & Color Analysis

A local web app that takes a portrait photo and returns a personalized salon-style consultation: hair type, face shape, recommended cuts (with photorealistic preview images), styles to avoid, color season, palette, and short hair-motion videos so you can see each cut in action.

## Features

- **Hair analysis** — texture, density, color, face shape, best part, key goals, quick tips, and a stylist-tone bottom line.
- **Photorealistic style previews** — face-preserving image edits for every recommended and avoided cut. Your face, skin tone, outfit, and background stay locked; only the hair changes.
- **"See it move" video** — generate a short clip per style card showing natural head turn so you can evaluate the cut in motion.
- **Color season analysis** — Soft Summer / True Autumn / Bright Winter etc., with an 18-color palette, neutrals, metals, and reference hex codes for your hair and eyes.
- **6 demo presets** — try the full report flow without uploading (Curly salt-and-pepper, Straight wavy, Fine, Thick, Executive, Low-maintenance).
- **Camera capture** — take a photo with your laptop or phone webcam directly in the browser.
- **Editable analysis** — tweak any field after generation and re-render images.
- **Exports** — Download as PNG, PDF, Instagram Portrait (1080×1350), or copy the summary to clipboard.
- **Lead capture** — optional email + opt-in form, saved to `leads.csv`.

## Quick start

1. Install Python 3.9+ (https://www.python.org/downloads/) — make sure "Add to PATH" is checked.
2. Copy `.env.example` to `.env` and fill in your `OPENAI_API_KEY` and `FAL_API_KEY`.
3. Double-click `Run HALO.bat` (or `start-server.bat`). First run installs dependencies.
4. Browser opens at `http://localhost:8765`.

## For testers (closed beta)

Welcome — you're one of a handful of people I trust to break this.

**Prereqs**
- Windows 10/11 (the `.bat` launchers are Windows-only; macOS / Linux runs fine via `python server.py`).
- Python 3.9 or newer with "Add to PATH" checked at install time.
- Git: https://git-scm.com/download/win
- An OpenAI API key (https://platform.openai.com/api-keys) and a FAL key (https://fal.ai/dashboard/keys). If I told you I'd cover keys for this round, I'll send them separately — never commit them anywhere.

**Setup (5 min)**
```
git clone <repo-url>
cd halo-hair-analysis
copy .env.example .env
notepad .env       # paste your two keys, save
Run HALO.bat       # first run installs deps, then opens the browser
```

**What to try**
- Upload a clear front-facing portrait, good lighting, hair fully visible.
- Try a couple of the 6 demo presets first so you can see the full report flow before spending on your own analysis.
- Try the camera capture if you're on a laptop.
- Edit a field in the analysis and re-render — does the image regen feel snappy?

**Cost guardrails**
A full analysis with all images + one video runs ~$0.69 on the underlying APIs. If you're using my keys, please cap yourself to ~3 full runs unless we've talked about more.

**Where to report bugs / weird behavior**
Open an issue on GitHub or text me directly. Screenshots are gold.

## Manual run

```bash
pip install flask openai httpx fal-client
python server.py
```

## Architecture

- `server.py` — Flask backend. Endpoints: `/analyze` (vision + JSON), `/upload-photo`, `/generate-image` (face-preserving image edit), `/generate-video` (image-to-video), `/image-status/<id>`, `/image-result/<id>`, `/video-status/<id>`, `/video-result/<id>`, `/save-lead`, `/health`.
- `index.html` — single-file frontend. Plain HTML + vanilla JS, no build step.
- `Run HALO.bat`, `start-server.bat`, `Create Desktop Shortcut.bat` — Windows convenience launchers.
- `.env` — secret keys (gitignored).
- `leads.csv` — captured lead emails (gitignored, generated at runtime).

## Costs (approximate, per analysis)

| Action | Cost |
|---|---|
| Hair + color analysis | ~$0.01 |
| 13 face-preserving style images | ~$0.50 |
| One video preview | ~$0.18 |

## Disclaimer

AI-generated style guidance. Not a professional salon diagnosis. Use as a starting point for a conversation with your stylist.
