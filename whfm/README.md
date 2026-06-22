# WHFM Experiments

Experimentation zone for **Womb Health FM** work inside the MyYogaNetwork (MYN) umbrella.

This folder is isolated from production code so AI-generated work, prototypes, and research can move fast without polluting the main app.

## What lives here

- Prototypes (one-off features, UI explorations, agent flows)
- Test scripts and harnesses
- Codex-generated branches and spike work
- Linear-linked implementation notes
- Research, validation experiments, and data exploration
- Integration trials (Practice Better, Fullscript, GHL, Klaviyo, etc.)

## Conventions

```
/experiments/whfm/
    /<ticket-id>-<short-slug>/    <- one folder per Linear ticket / spike
        README.md                  <- what, why, status, links to Linear + PR
        notes.md                   <- running notes
        ...code/data...
```

Examples:
- `WHFM-12-fertility-reset-onboarding/`
- `WHFM-18-soap-note-pipeline/`
- `WHFM-23-fullscript-supplement-sync/`

## Sibling experiment zones (MYN umbrella)

```
/experiments
    /whfm          <- this folder
    /hotel-ai
    /wearables
    /sales-agents
```

Each is an isolated AI experimentation zone with its own README and conventions.

## Workflow

1. New idea -> open Linear ticket in the MYN project, prefix `WHFM-`.
2. Assign to `@Codex` (or work locally) — Codex creates a branch and PR.
3. Code lives under `/experiments/whfm/<ticket-id>-<slug>/`.
4. When something graduates from experiment to product, move it out of `/experiments` into the appropriate production path and delete or archive the experiment folder.

## Status

Initialized: 2026-05-12
Owner: Ram (WombHealthFM is one of his companies under the MYN umbrella)
