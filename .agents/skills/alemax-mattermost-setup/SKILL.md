---
name: alemax-mattermost-setup
description: "Set up or update optional Mattermost presence on this volume from its claude-meta clone: run `alemax presence check`, then walk each reported fix — admin token, provisioning, relay account, hooks, a leftover uv tool copy — with the user approving every change to the server or to the Claude settings file."
license: MIT
metadata:
  author: alemax
  version: "2.0"
  source_reviewed_model: claude-5
  source_reviewed: 2026-10-04
---
<!-- twin: intentional pair — the live verification restarts a Claude Code session, which this host may not run; the setup steps and the program are the same -->

## Working directory

Keep the working directory at the volume's claude-meta clone; every command below runs from its
root. `alemax` is the packaged CLI under `plugins/alemax/`.

## Wraps

`alemax presence check`, `provision`, `install` and `status`, run as
`uv run --directory plugins/alemax alemax presence <subcommand>`. Behaviour and refusals are in
specs `mattermost-presence` and `mattermost-relay`.

## Steps

1. **Confirm the clone.** `uv run --directory plugins/alemax alemax msg self` must report
   `repo=claude-meta` on the per-volume branch; otherwise refuse.
2. **Read the checklist.** `alemax presence check`; work each `FIX` line top to bottom. All `ok`
   → report and stop.
3. **Admin token missing** → the user stores a Mattermost admin personal access token with the
   `security` command `check` prints. Never ask for the token.
4. **Provision** — dry run first. On a first run ask for the server URL, team, the user's own
   Mattermost username and the channel, and add this clone as
   `--extra claude-meta=<root from msg self>`. Show the plan; propose short `--alias` values for
   refused names; apply with `--relay --apply` only after the user approves. It changes the
   Mattermost server.
5. **Hooks** → `install --dry-run`, show it, then `install` after approval.
6. **Leftover `uv tool` copy** → `uv tool uninstall alemax` after approval.
7. **Re-check** with `alemax presence check`; every line should read `ok`.
8. **Verify live** when the host runs Claude Code sessions: restart one in a provisioned folder
   and confirm with `alemax presence status`. Otherwise say the live check is left to the user.

## Report

The final checklist, accounts created or kept, aliases chosen, and the live verification
result.
