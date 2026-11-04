---
name: alemax-mattermost-presence
description: "Use when asking who is live, or when an account still shows active after its session died. Show the live and stale presence registrations on every volume of this Mac, and with the user’s approval sweep this volume’s stale ones so their Mattermost accounts go offline."
license: MIT
metadata:
  author: alemax
  version: "2.0"
  source_reviewed_model: claude-5
  source_reviewed: 2026-10-04
---

## Working directory

Keep the working directory at the repository being operated on; every command below runs from
its root. `alemax` is the packaged CLI under `plugins/alemax/`.

## Wraps

`alemax presence who` (read-only) and `alemax presence sweep`, run as
`uv run --directory plugins/alemax alemax presence <subcommand>`. Specs `mattermost-presence`
and `mattermost-relay` define live, stale and the sweep.

## Steps

1. **Look.** `alemax presence who` lists every registration on this Mac, `live` with its socket
   or `STALE` when its process is gone; other volumes are for reference only.
2. **Sweep only this volume, only with approval.** Offer `alemax presence sweep` when `who` shows
   `STALE` lines for this volume. A stale line elsewhere is that volume's to clear.
3. **To reach a live session,** use `$alemax-mattermost-send-msg`.

## Report

Live sessions per volume, stale ones, and what the sweep cleared.
