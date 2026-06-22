# MYN Experiments

Top-level sandbox for **MyYogaNetwork** experimentation. Each subfolder is an isolated zone — prototypes, AI-generated work, research, integration trials.

## Zones

| Folder | Purpose |
|---|---|
| `whfm/` | Womb Health FM — fertility coaching, SOAP automation, client tooling |
| `hotel-ai/` | Hotel SaaS features and agent workflows |
| `wearables/` | Wearable device integrations |
| `sales-agents/` | Sales / CRM automation agents |

## Rules

1. Nothing in `/experiments` is production. Treat it as throwaway until proven.
2. One folder per Linear ticket or spike: `<TICKET-ID>-<short-slug>/`.
3. Every experiment folder gets a `README.md` with: what, why, status, Linear link, PR link.
4. When an experiment graduates, move it to the appropriate production path and remove or archive the experiment folder.

## Adding a new zone

1. Create `/experiments/<zone>/` with a `README.md` following the pattern in `whfm/README.md`.
2. Add the row to the table above.
