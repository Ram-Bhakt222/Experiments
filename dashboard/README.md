# Doc Dashboard

Local Flask doc-processing hub at `http://localhost:8900`. Drag files onto tiles, jobs queue up, results land in `storage/outputs/<job_id>/`. The doc-side counterpart to **AI Video Studio** (which handles video/avatar/music at `localhost:8780`) — anything video gets forwarded to Studio via the `studio` tile rather than reimplemented here.

```
Browser  ─►  Doc Dashboard  ─┬─►  Local pipelines (Whisper, PDF, DOCX, PPTX, video split)
   (8900)                    ├─►  Ollama  (LLM + embeddings, 11434)
                             ├─►  Qdrant  (vectors, 6333)
                             ├─►  AI Video Studio  (8780)
                             └─►  HALO  (8765)
```

---

## Why this exists

Three observations from looking at Ram's machine:

1. The `Programming Projects/audio_to_text/` folder has gigabytes of un-transcribed hotel and LAUSD audio. There's a transcription script but no convenient way to point it at a file and walk away.
2. There's a one-off `cut_clips.py` for video splitting that lived in `Downloads/`, doing exactly one mode (timestamps CSV). Useful but only ever runnable from a terminal.
3. AI Video Studio at `Desktop/AI video gen/studio/` already has the dashboard-shaped chassis (Flask + tiles + jobs) for everything video, avatar, and music. Doc work doesn't belong in there.

So this is a **boring local Flask dashboard** that puts the doc and local-AI work in one place, talks to Studio for video, and runs with the rest of the stack via the Cockpit bootstrap.

---

## Pipelines (the 12 tiles)

| Tile | Type | What goes in | What comes out |
|---|---|---|---|
| **Audio → Transcript** | docs | `.mp3 .m4a .wav .flac` | `<stem>.txt` (timestamped) + `.srt` + `.json` |
| **PDF → Text + Tables** | docs | `.pdf` | `<stem>.txt` + `tables/page###_t#.csv` |
| **DOCX → Markdown** | docs | `.docx` | `<stem>.md` + `tables/table_###.csv` |
| **PPTX → Outline** | docs | `.pptx` | `<stem>.md` with slides + speaker notes |
| **Session → SOAP + Actions** | docs | Fathom transcript `.txt` | Staged folder for the `wombhealth-session-processor` skill to finalize |
| **Portrait → HALO Report** | docs | `.jpg .png` | `halo_analysis.json` (posts to HALO at 8765) |
| **Local Chat (Ollama)** | ai | Prompt text | `reply.md` |
| **Batch LLM over Folder** | ai | Files + prompt template | `results.csv` (filename → response) |
| **RAG: index a folder** | ai | Folder path | `indexed.csv` manifest + vectors upserted into Qdrant |
| **LLM File Classifier** | ai | Files + bucket names | `classifications.csv` (filename → bucket → rationale) |
| **AI Video Studio Job** | video | Studio station + JSON inputs | Forwards to Studio at 8780, mirrors output |
| **Video → Clips** | video | Video + (optional) timestamps CSV | `clips/clip_##.mp4` + `_manifest.json` — 5 modes |

The **Video → Clips** tile is the rebuilt `cut_clips.py`. Five modes:

- `timestamps` — read a CSV of `type, start, end, label` (original behavior, preserved exactly)
- `equal` — N equal segments
- `fixed` — N-second consecutive windows (e.g. 60-sec reels)
- `scene` — ffmpeg scene-change detection
- `chapters` — run whisper, split at the largest silence gaps

Lossless `ffmpeg -c copy` by default; set `reencode=true` in inputs for frame-perfect cuts.

---

## Setup

### First-time install

1. Make sure **ffmpeg** is on PATH (`winget install Gyan.FFmpeg`, then restart the terminal).
2. (Optional) Pull Ollama models: `ollama pull llama3.1:8b-instruct-q4_K_M nomic-embed-text`
3. Double-click **`Run Dashboard.bat`**. The first launch:
   - Creates `.venv\` and installs `requirements.txt` (~2-3 min)
   - Copies `.env.example` to `.env` if missing
   - Starts Flask on port 8900
4. Edit `.env` and set `SHARED_SECRET=` to a password you like.
5. Open `http://localhost:8900`. Log in as user `admin` with that password.

### Subsequent launches

Just double-click `Run Dashboard.bat`, or once Cockpit's bootstrap has been run, the dashboard auto-starts as **Phase E6**.

### Multi-user

Generate a bcrypt hash:

```powershell
cd "C:\Users\ram\Desktop\programming projects (other)\Experiments\dashboard"
.\.venv\Scripts\python.exe -c "import auth; print(auth.hash_password('YOUR_PASSWORD'))"
```

Paste it into `users.json` per the `users.json.example` template:

```json
{
  "ram":      "$2b$12$....",
  "jeanelle": "$2b$12$...."
}
```

While `users.json` exists, the `admin` / `SHARED_SECRET` fallback is bypassed.

---

## Using the dashboard

There are two views in the browser:

- **`/`** — the working interface. Tile grid, drop zone in each dialog, live job table that polls every 2 seconds. When a job flips to **completed**, an **Open** link appears next to it that opens the primary output file.
- **`/how-to`** — a full how-to page with every tile explained, every input/output, recipe chains, and troubleshooting. Linked from the header as **How To →**.

Every job lives at `storage/outputs/<job_id>/`. The job table's **Open** points at whatever the pipeline marked as the primary output (the manifest, the markdown, the txt), but the sibling files are right next to it on disk.

Job state is persisted in `storage/jobs.db` (SQLite) — survives restarts.

---

## CLI mode (no dashboard required)

The video splitter is also a standalone CLI, useful for batch jobs or shell scripts:

```powershell
cd "C:\Users\ram\Desktop\programming projects (other)\Experiments\dashboard"
.\.venv\Scripts\python.exe pipelines\video\video_split.py `
  --video "C:\Users\ram\Downloads\clip maker\Muhammad Call original.mp4" `
  --csv   "C:\Users\ram\Downloads\clip maker\timestamps.csv" `
  --mode  timestamps `
  --out   "C:\Users\ram\Downloads\clip maker\clips"
```

Other modes:

```
--mode equal     --n 6
--mode fixed     --seconds 60
--mode scene     --scene-threshold 0.3 --n 12
--mode chapters  --n 8 --whisper-model base
--reencode       (any mode, frame-perfect cuts)
```

---

## Architecture

```
dashboard/
  server.py              # Flask app, basic-auth gated, routes /, /how-to,
                         # /api/pipelines, /api/jobs, /api/upload, /api/run/<p>, /outputs/...
  index.html             # Tile grid + job table (single-file vanilla JS)
  how_to.html            # /how-to page
  queue_db.py            # SQLite job queue + single worker thread (jobs serialize)
  auth.py                # HTTP basic auth, users.json + SHARED_SECRET fallback
  requirements.txt
  Run Dashboard.bat      # First-run + relaunch
  .env.example           # SHARED_SECRET, OLLAMA_URL, QDRANT_URL, STUDIO_URL, HALO_URL, ...
  users.json.example
  pipelines/
    _common.py           # job_output_dir, first_input, all_inputs helpers
    studio_proxy.py      # talks to AI Video Studio at 8780
    docs/
      transcribe.py      # faster-whisper, ports audio_to_text/transcribe_all.py
      pdf_extract.py     # pypdf text + pdfplumber tables
      docx_extract.py    # python-docx → markdown + table CSVs
      pptx_extract.py    # python-pptx → outline + speaker notes
      soap_note.py       # stages transcript for wombhealth-session-processor skill
      halo_proxy.py      # POSTs portrait to HALO server
    local_ai/
      ollama_client.py   # chat/embed/evict + run_chat pipeline
      batch_llm.py       # run prompt template over every file in a folder
      rag_index.py       # chunk + embed + upsert into Qdrant
      classifier.py      # LLM-based file classifier
    video/
      video_split.py     # 5-mode clip cutter (also a CLI)
      _original_clip_maker/   # the original cut_clips.py + timestamps.csv, preserved
  storage/
    jobs.db              # SQLite job table
    uploads/<job_id>/    # what got dragged in
    outputs/<job_id>/    # what came out
```

### Job lifecycle

1. UI uploads files + inputs to `POST /api/upload` (or `POST /api/run/<pipeline>` for no-file pipelines).
2. `queue_db.create_job` writes a `queued` row.
3. The background worker thread picks up the next queued job.
4. The pipeline function reads `job["input_path"]` and `job["inputs"]`, writes outputs under `storage/outputs/<job_id>/`, calls `update_job(...)` with progress.
5. When the function returns, status flips to `completed` (or `failed` on exception).
6. The UI's 2-second poll shows the **Open** link.

### Why a single worker thread

Most of the heavy pipelines (Whisper, ffmpeg, Studio forwards) are GPU- or CPU-saturating. Running them in sequence keeps VRAM/RAM contention out of the equation and makes failures easy to read. If you need parallelism, increase the worker count in `queue_db.start_worker()` — the per-job functions are already thread-safe.

### VRAM discipline

The Ollama client exposes an `evict()` helper that POSTs `keep_alive: 0` to unload a chat model. The Studio proxy is a network call so it doesn't fight Ollama for VRAM — but if you start running ComfyUI workflows through Studio on the same machine, call `evict()` from any local LLM tile before kicking off a video job. (Wire as a pre-step in your own pipeline if you want it automatic.)

---

## Integration with the rest of the stack

### Cockpit bootstrap

The dashboard auto-launches as **Phase E6** in `C:\Users\ram\Desktop\Strategy AGI\MYN-Cockpit\bootstrap.ps1`. The phase is idempotent: it skips if port 8900 is already bound or a matching `python.exe` is already running `server.py`. Logs go to `dashboard_stdout.log` and `dashboard_stderr.log` in the dashboard folder.

### Cockpit dashboards.json

The dashboard is listed in `MYN-Cockpit/dashboards.json` as `id: doc-dashboard`, category **Layer 2 - Ops**, pointing to `http://localhost:8900`. It appears in the Cockpit sidebar alongside ROI, GA4, etc.

### AI Video Studio

The **AI Video Studio Job** tile forwards any of Studio's stations (`ltx-t2v`, `kling-i2v`, `hedra-avatar`, `omnihuman`, `sonauto`, `silero-vad`, `ffmpeg-concat`, `topaz-upscale`, `rife-interp`, etc.) — submit station name + JSON inputs, the proxy POSTs `/api/generate/<station>`, polls `/api/jobs/<id>`, and mirrors the result back. Studio must be running at 8780 (launch from `Desktop\AI video gen\studio\Run Studio.bat`).

### HALO

The **Portrait → HALO Report** tile POSTs the image to HALO's `/upload-photo` + `/analyze`. HALO must be running at 8765 (launch from `Desktop\programming projects (other)\hair analysis\Run HALO.bat`).

### Ollama

Local LLM tiles speak to Ollama at `localhost:11434`. Models in use:

- `llama3.1:8b-instruct-q4_K_M` — chat workhorse (~5 GB VRAM)
- `qwen2.5:7b-instruct-q4_K_M` — better at structured output (~5 GB)
- `nomic-embed-text` — embeddings for RAG (~300 MB)

Pull them via `ollama pull <model>`. If Ollama isn't running, those tiles error gracefully — drop a job and you'll see a connection-refused message in the progress column.

### Qdrant

**RAG: index a folder** writes vectors to Qdrant at `localhost:6333`. The collection auto-creates with the right vector size on first upsert. Default collection is `dashboard_docs`, overridable per-job. Same Qdrant your Cockpit stack already runs.

---

## Recipes

### LAUSD / hotel audio backlog → searchable knowledge

1. Drag every `.mp3` from `Programming Projects/audio_to_text/hotels/` onto **Audio → Transcript**.
2. After they're all done, copy the `.txt` files into one folder.
3. Run **RAG: index a folder** pointed at that folder, collection name `hotel_calls`.
4. Query from Cockpit / Discourse / wherever you already use Qdrant.

### Fathom session → SOAP note + Gmail draft

1. Drop the Fathom transcript onto **Session → SOAP + Actions**. The job stages the transcript.
2. Have Claude run the `wombhealth-session-processor` skill against the output folder. It produces `*_action_steps.docx`, `*_soap_note.docx`, and the Gmail draft.

### Muhammad Call → 60-sec reels for IG

1. Drop the `.mp4` onto **Video → Clips**.
2. Mode `fixed`, seconds `60`. Wait.
3. Every clip lands in `storage/outputs/<job>/clips/`.

### Long interview → chapter-split clips → polished b-roll

1. **Video → Clips**, mode `chapters`, n `8`. Whisper splits at the largest silence gaps.
2. For each chapter worth polishing, open Studio and run `silero-vad` (jump-cut silence).
3. `ffmpeg-concat` in Studio to stitch them back.
4. (Optional) `topaz-upscale` for 4K.

---

## Troubleshooting

### "Port 8900 in use"

```powershell
Get-NetTCPConnection -LocalPort 8900 | Select-Object OwningProcess
Stop-Process -Id <PID> -Force
```

### "401 Auth required"

Username is `admin`. Password is your `SHARED_SECRET` from `.env` (unless you've created a `users.json` with bcrypt hashes).

### Ollama tiles say "connection refused"

```powershell
ollama serve
# In another terminal:
ollama pull llama3.1:8b-instruct-q4_K_M
ollama pull nomic-embed-text
```

### Studio tile says "no job id" or polling never finishes

AI Video Studio isn't running at 8780. Launch:

```powershell
cd "C:\Users\ram\Desktop\Strategy AGI\AI video gen\studio"
.\"Run Studio.bat"
```

### RAG tile says "folder not found"

The path must exist on the host machine running the dashboard. Type it from the address bar of File Explorer to be sure — backslashes and spaces are fine in the dialog.

### Whisper: "no module named faster-whisper"

The first-run pip install failed somewhere (usually a transient network blip). Rerun:

```powershell
cd "C:\Users\ram\Desktop\programming projects (other)\Experiments\dashboard"
.\.venv\Scripts\activate
pip install -r requirements.txt
```

### `Video → Clips` fails with "ffmpeg not found"

```powershell
winget install Gyan.FFmpeg
# Restart the terminal so PATH refreshes, then relaunch the dashboard.
```

### Phase E6 logs "Doc Dashboard .venv not present yet"

Cockpit's bootstrap won't create the venv for you. Run `Run Dashboard.bat` manually once — that builds the venv. Then `bootstrap.ps1` will pick it up cleanly on every subsequent run.

---

## Adding a new pipeline

1. Write a function in `pipelines/<group>/<name>.py` with this signature:

   ```python
   def run(job: dict) -> None:
       # job["input_path"], job["inputs"], job["id"]
       # Write outputs under storage/outputs/<job_id>/...
       # Call update_job(job["id"], output_path=..., progress=..., cost_usd=...)
   ```

2. Import it in `server.py` and add a row to the `PIPELINES` dict with a label and a kind tag (`docs`, `ai`, `video`, `audio`, `image`).
3. (Optional) Add an entry to `KIND_TO_INPUTS` in `index.html` if your pipeline needs custom form fields.
4. Restart Flask. The tile auto-renders.

Pipelines that take no file uploads (pure-text like `ollama-chat`, or path-based like `rag-index`) just need to be in the `filesNeeded = !["..."].includes(...)` list in `index.html`.

---

## File map of related folders

| Folder | What it is |
|---|---|
| `pipelines/video/_original_clip_maker/` | The original `cut_clips.py` and `timestamps.csv`, preserved for reference |
| `..\..\Programming Projects\audio_to_text\` | The audio backlog and the source transcribe script |
| `..\..\hair analysis\` | HALO — the running portrait-analysis app the dashboard proxies |
| `..\AI video gen\studio\` | AI Video Studio — every video/avatar/music station |
| `..\MYN-Cockpit\` | Cockpit — runs bootstrap.ps1, hosts dashboards.json, links to this from `:8787` |
| `..\Local AI\` | Catalog of where every docker-compose project lives on this machine |

---

## Status

Working. As of 2026-05-11:

- All 12 pipelines registered and import-clean
- Health check at `/health` reports all 12
- Phase E6 wired into Cockpit's `bootstrap.ps1`
- `doc-dashboard` entry in `dashboards.json` (Layer 2 - Ops)
- How-to page at `/how-to`
- 1,656 lines of Python across 15 files; one 11 KB HTML for the main UI, one 16 KB HTML for the how-to

Things deliberately NOT included:

- ComfyUI workflow tiles — those route through the Studio proxy, not reimplemented here
- Voice cloning (XTTS) — would land in Studio if added
- Long-form (>60 sec) video chunking — not needed for current reel use-case
- Wan-14B / CogVideoX-5B — won't fit your 8-12 GB VRAM
