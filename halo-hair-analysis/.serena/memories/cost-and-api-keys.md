# HALO — Cost guardrails & API-key boundary

## The boundary

- **All keys server-side.** OpenAI, FAL.AI, and any future Supabase service key live in `.env` on the server or in `~/Library/Application Support/HALO/.env` on macOS app installs.
- **Client never holds keys.** The iOS app, the web frontend, and the macOS WebKit window all call the HALO backend. The backend is the only thing that talks to OpenAI / FAL.
- **`.env` is gitignored.** Never commit. Never paste into chat. Never include in support DMs or bug reports.

## Cost per full run (~$0.69)

| Action | ~Cost |
|---|---|
| Hair + color analysis (vision + JSON) | $0.01 |
| 13 face-preserving style images | $0.50 |
| One video preview | $0.18 |

## Beta tester cap

Closed-beta testers using shared keys are capped at **~3 full runs** unless explicitly extended.

## Operational guardrails to consider before scaling

- **Per-IP rate limit** on `/analyze`, `/generate-image`, `/generate-video` — prevents single-user runaway spend
- **Daily spend budget** with circuit-breaker that returns a friendly error past the cap (prevents a viral spike from emptying the FAL balance)
- **Email-gated full report** is already wired (`leads.csv`) — leverage as a soft rate limit pre-payment
- **Move to per-user payment / metered billing** before opening past closed beta. Stripe + simple per-run charge keeps the cost model honest.

## Anti-patterns

- Embedding the OpenAI / FAL key in the iOS bundle to "speed up" requests — never. Backend stays in the loop.
- Logging full prompts or full image bytes to plain text logs — keep job IDs only.
- Hardcoding keys in `.env.example` — that file ships in the repo. Keys go in `.env`, only.
