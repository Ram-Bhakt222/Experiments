# HALO iPhone App

Native SwiftUI client for the HALO backend.

## Credential Model

Do not put OpenAI, FAL, or Supabase service credentials in the iOS app. The app
only talks to the HALO backend. The backend owns provider keys, rate limits,
storage, and job persistence.

## Local Simulator Run

On macOS:

```bash
brew install xcodegen
cd ios/HALO
xcodegen generate
open HALO.xcodeproj
```

Run the Flask backend separately:

```bash
cd ../..
python server.py
```

The simulator can use `http://127.0.0.1:8765`. For a physical iPhone, replace
`HALO_API_BASE_URL` in `HALO/Info.plist` with a deployed backend URL or a LAN
URL that the phone can reach.

## Current Scope

- Pick a portrait from Photos.
- Send portrait + style preferences to `POST /analyze`.
- Render the returned hair profile, color season, tips, and palette.

Next iOS milestones are camera capture, saved consultations, image/video job
polling, anonymous sessions in Keychain, and hosted backend auth/rate limits.
