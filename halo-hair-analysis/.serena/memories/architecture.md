# HALO — Architecture

## Three surfaces, one backend

```
┌─────────────────────────┐   ┌─────────────────────────┐   ┌─────────────────────────┐
│  Web (index.html)       │   │  macOS app (.app)       │   │  iOS app (SwiftUI)      │
│  - vanilla JS           │   │  - PyInstaller bundled  │   │  - native UI            │
│  - calls localhost:8765 │   │  - WebKit window        │   │  - calls deployed API   │
└─────────────┬───────────┘   └─────────────┬───────────┘   └─────────────┬───────────┘
              │                             │                             │
              └─────────────────────────────┴─────────────────────────────┘
                                            │
                                  ┌─────────▼──────────┐
                                  │  Flask server.py   │
                                  │  OpenAI + FAL keys │
                                  │  stay server-side  │
                                  └─────────┬──────────┘
                                            │
                          ┌─────────────────┼─────────────────┐
                          │                 │                 │
                  ┌───────▼──────┐  ┌───────▼──────┐  ┌───────▼──────┐
                  │ OpenAI Vision│  │ FAL image    │  │ FAL image-   │
                  │ + JSON       │  │ edit (face-  │  │ to-video     │
                  │ /analyze     │  │ preserving)  │  │              │
                  └──────────────┘  └──────────────┘  └──────────────┘
```

## Credential boundary

- **Server-side only:** `OPENAI_API_KEY`, `FAL_API_KEY`, any Supabase service key
- **Client never holds keys.** iOS app calls the HALO backend; backend calls OpenAI / FAL.
- `.env` lives in project root during dev. On macOS app builds, secrets read from `~/Library/Application Support/HALO/.env` (not bundled).

## Endpoints (server.py)

| Method | Path | Purpose |
|---|---|---|
| POST | `/analyze` | Vision + JSON: hair/face/color analysis from photo |
| POST | `/upload-photo` | Photo upload |
| POST | `/generate-image` | Face-preserving image edit (single style) |
| GET | `/image-status/<id>` | Poll image generation |
| GET | `/image-result/<id>` | Retrieve completed image |
| POST | `/generate-video` | Image → video (hair motion preview) |
| GET | `/video-status/<id>` | Poll video generation |
| GET | `/video-result/<id>` | Retrieve completed video |
| POST | `/save-lead` | Append email + opt-in to leads.csv |
| GET | `/health` | Liveness |

## State

- **No database in v1.** Leads are appended to `leads.csv` (gitignored).
- **No user accounts in v1.** Analyses are session-bound on the client.
- Server-side: in-memory job tracking for async image/video generation.

## Why no build step on the frontend

Single-file `index.html` with vanilla JS keeps the surface area small for beta. Avoids Vite/Webpack maintenance burden. Trades dev ergonomics for shippability — appropriate for a closed beta consumer app where the magic moment, not the codebase, sells the product.
