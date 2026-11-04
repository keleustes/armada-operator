---
name: mattermost-presence
description: "Use when asking who is live, or when an account still shows active after its session died. Show which Claude sessions are live on every volume of this Mac — account, folder, socket — and which registrations are stale (the session died without a clean exit, so its Mattermost account still shows active). `alemax presence who` reads every volume's presence registry; `alemax presence sweep` clears this volume's stale ones and marks their accounts offline. The volume's relay also sweeps once a minute. Optional: needs Mattermost presence on this volume."
license: MIT
compatibility: Requires `uv` and Mattermost presence provisioned on this volume (optional).
context: either
argument-hint: ""
allowed-tools: Bash(uv run --directory plugins/alemax alemax presence who), Bash(uv run --directory plugins/alemax alemax presence sweep)
metadata:
  author: alemax
  reviewed_model: claude-5
  reviewed: 2026-10-04
---

## Wraps

`alemax presence who` (read-only) and `alemax presence sweep`, run from the repo root as
`uv run --directory plugins/alemax alemax presence <subcommand>`. What counts as live and how
a sweep marks accounts offline are in specs `mattermost-presence` and `mattermost-relay`.

## Steps

1. **Look.** `alemax presence who` lists every registration on this Mac: `live` with its socket,
   or `STALE` when its process is gone. Other volumes are shown for reference only.
2. **Sweep only this volume, only with the operator's OK.** If `who` shows `STALE` lines for this
   volume, offer `alemax presence sweep`; it removes them and marks their accounts offline. A
   stale line on another volume is that volume's to clear — its relay does it within a minute,
   or its own `/alemax:mattermost-presence`.
3. **To reach a live session,** use `/alemax:mattermost-send-msg <account>`, or `/alemax:send-msg`
   on this Mac.

## Report

The live sessions per volume, any stale ones, and what the sweep cleared.
