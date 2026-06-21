# HALO System Changes

This document describes the product shift from a local browser app to an
iPhone-first app with a server-owned API. The main change is the credential
boundary: the mobile app is treated as public and untrusted, while the backend
keeps all paid provider keys and service credentials.

## Current Direction

HALO now has three client surfaces:

- `index.html` - local web app for development, demos, and admin workflows.
- `mac_app.py` - macOS desktop wrapper that runs the Flask app locally in a
  native WebKit window.
- `ios/HALO` - native SwiftUI iPhone starter app that calls the HALO backend.

The iPhone app is the intended product direction. The web app remains useful as
a fast iteration surface and the macOS wrapper remains useful for desktop demos,
but neither should own OpenAI, FAL, or Supabase service credentials.

## Architecture Diagram

```mermaid
flowchart TB
    subgraph Clients["Client Surfaces"]
        Web["Local Web App<br/>index.html"]
        Mac["macOS Wrapper<br/>mac_app.py + pywebview"]
        iOS["iPhone App<br/>SwiftUI in ios/HALO"]
    end

    subgraph Backend["HALO Backend"]
        Flask["Flask API<br/>server.py"]
        Env["Server Environment<br/>.env / hosted secrets"]
        Limits["Rate Limits + Sessions<br/>planned mobile guardrail"]
        Jobs["Job Tracking<br/>analysis_id + request_id"]
    end

    subgraph Providers["Private Provider Services"]
        OpenAI["OpenAI Vision Analysis"]
        FAL["FAL Image + Video Jobs"]
        Supabase["Supabase DB + Storage"]
    end

    Web -->|HTTP localhost or hosted API| Flask
    Mac -->|local WebKit -> localhost| Flask
    iOS -->|HTTPS API only| Flask

    Flask --> Env
    Flask --> Limits
    Flask --> Jobs
    Flask -->|OPENAI_API_KEY stays server-side| OpenAI
    Flask -->|FAL_API_KEY stays server-side| FAL
    Flask -->|SUPABASE_SERVICE_KEY stays server-side| Supabase

    OpenAI --> Flask
    FAL --> Flask
    Supabase --> Flask
    Flask -->|analysis JSON, asset URLs, job status| iOS
```

## Credential Boundary

Never ship these credentials in the iPhone app:

- `OPENAI_API_KEY`
- `FAL_API_KEY` or `FAL_KEY`
- `SUPABASE_SERVICE_KEY`
- Any future Stripe, email, admin, or service-role secrets

The iPhone app can safely contain:

- Public backend base URL
- App bundle identifier
- Non-secret feature flags
- A user/session token issued by the HALO backend or auth provider

For local development, the iOS app uses:

```text
HALO_API_BASE_URL = http://127.0.0.1:8765
```

For TestFlight or App Store builds, replace that with a hosted HTTPS backend:

```text
HALO_API_BASE_URL = https://api.your-halo-domain.com
```

## Request Flow

```mermaid
sequenceDiagram
    participant User
    participant iPhone as iPhone App
    participant API as HALO Backend
    participant OpenAI
    participant FAL
    participant Store as Supabase

    User->>iPhone: Select or capture portrait
    iPhone->>API: POST /analyze with photo + preferences
    API->>OpenAI: Analyze portrait with server API key
    OpenAI-->>API: Hair and color JSON
    API->>Store: Save analysis and optional source photo
    Store-->>API: analysis_id
    API-->>iPhone: Analysis JSON + analysis_id

    iPhone->>API: POST /generate-image with analysis_id
    API->>FAL: Start image job with server API key
    FAL-->>API: request_id
    API-->>iPhone: request_id
    iPhone->>API: GET /image-status/request_id
    API->>FAL: Poll provider job
    FAL-->>API: Status/result
    API->>Store: Mirror final asset
    API-->>iPhone: Stable asset URL
```

## Backend Responsibilities

The backend owns the expensive and private work:

- Load secrets from `.env` locally or hosted secret storage in production.
- Validate upload size and image type.
- Call OpenAI for analysis.
- Call FAL for generated images and videos.
- Persist analyses and generated assets.
- Enforce rate limits, credits, and abuse controls.
- Return stable IDs and URLs to clients.

## iPhone App Responsibilities

The iPhone app owns the user experience:

- Pick or capture a portrait.
- Collect style preferences.
- Upload to the HALO backend.
- Show progress while analysis/jobs run.
- Render results, palettes, generated images, and videos.
- Store only safe app state, such as session token and saved analysis IDs.

## Suggested Mobile API Shape

The current SwiftUI scaffold calls the existing `POST /analyze` endpoint. The
next backend cleanup should make the mobile API more explicit:

```text
POST /mobile/session
POST /mobile/analyze
GET  /mobile/analysis/<analysis_id>
POST /mobile/generate-image
POST /mobile/generate-video
GET  /mobile/job/<request_id>
```

This gives the app resumable state. If the app is closed during image or video
generation, it can reopen with `analysis_id` and continue polling jobs instead
of spending money on duplicate provider calls.

## Build Surfaces

| Surface | Path | Purpose |
|---|---|---|
| Web app | `index.html` | Fast local development and demo UI |
| Backend | `server.py` | Server-owned API and provider integration |
| macOS app | `mac_app.py` | Desktop wrapper around local Flask app |
| iPhone app | `ios/HALO` | Native SwiftUI mobile client |

## Open Work

- Deploy the Flask backend to a stable HTTPS host.
- Add mobile session creation and server-side rate limits.
- Store session/user token in iOS Keychain.
- Add camera capture to the SwiftUI app.
- Add image/video job polling UI.
- Add saved consultations and share/export flows.
