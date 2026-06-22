# HALO — Current Status

**As of 2026-05-14.**

## Product state

- **Closed beta** on Windows + macOS. Manual key setup per tester.
- iOS starter exists in `ios/HALO/` but is not yet TestFlight-distributed.
- Web frontend (`index.html`) is the primary surface for beta testing.
- 6 demo presets work end-to-end without uploading a photo.
- Camera capture works in-browser on laptops; mobile-browser path tested.
- Lead capture writes to `leads.csv` server-side.

## What's been built

- `/analyze` endpoint — full vision + JSON pipeline
- Face-preserving image generation (FAL.AI)
- Image-to-video preview (FAL.AI)
- Editable analysis fields with re-render
- PNG / PDF / Instagram Portrait (1080×1350) exports
- Clipboard-copy summary
- Email + opt-in form → `leads.csv`
- macOS PyInstaller build script

## What's NOT built yet

- Public landing page
- Stripe / payments
- User accounts / persistence
- TestFlight iOS distribution
- Per-IP rate limiting
- Daily spend circuit-breaker
- Email nurture sequence (just leads capture, no drip)
- Referral mechanic
- HALO creator Discord / community

## Marketing state

- **Playbook drafted, not executed.** See `halo-marketing-playbook` memory.
- No micro-influencer recruiting started.
- No TikTok / IG / Pinterest accounts seeded.
- No Meta Ads running.
- No team-photo or co-founder-with-stylist shoot scheduled.

## Immediate next moves (per playbook §12)

1. Pick 5 hook templates from §3, shoot 5 founder TikToks
2. DM 20 micro-influencers with "paid promo?" line
3. Open HALO creator Discord
4. Write 5-email nurture, wire into existing `leads.csv` pipe
5. Add "share with a friend" button to existing PNG / PDF export
6. Book "AI builder + master stylist" photo + video shoot
7. Seed Pinterest with 200 pins across 12 demo presets
8. Set up per-IP rate limit + daily spend ceiling before opening past closed beta

## Open questions / decisions needed

- Who is the **named credentialed stylist** for the co-founder team shot?
- Where does payment + persistence land — Stripe + Supabase, or simpler?
- TestFlight distribution timeline for iOS — gate behind beta, or release publicly?
- Does HALO get its own domain + brand, or stay under Ram's personal site for v1?
