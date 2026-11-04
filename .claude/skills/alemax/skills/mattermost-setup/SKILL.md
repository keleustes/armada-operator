---
name: mattermost-setup
description: Use on a volume that has never used presence, after a resync that changed presence, or when `check` reports anything to fix. Set up — or bring up to date — optional Mattermost presence on this volume, from its claude-meta clone. `alemax presence check` lists what the volume has and lacks (admin token, provisioning, relay account, hooks, a leftover `uv tool` copy) with the fix for each; this skill walks those fixes in order, with the operator approving every change to the Mattermost server or to `~/.claude/settings.json`.
license: MIT
compatibility: Requires `uv`, a claude-meta clone on its per-volume branch, a reachable Mattermost server, and an admin personal access token in the Keychain for provisioning. Mattermost presence is optional.
context: claude-meta-only
argument-hint: ""
allowed-tools: Bash(uv run --directory plugins/alemax alemax presence *), Bash(uv run --directory plugins/alemax alemax msg self)
metadata:
  author: alemax
  reviewed_model: claude-5
  reviewed: 2026-10-04
---

## Wraps

`alemax presence check`, `provision`, `install` and `status`, run from the repo root as
`uv run --directory plugins/alemax alemax presence <subcommand>`. What each one does, and what
it refuses, is in specs `mattermost-presence` and `mattermost-relay` — not here.

## Steps

1. **Confirm the clone.** `uv run --directory plugins/alemax alemax msg self` must report
   `repo=claude-meta` on this volume's
   per-volume branch; anywhere else, refuse and name the volume's claude-meta clone.
2. **Read the checklist.** `alemax presence check`. Every `FIX` line carries its command; work
   them top to bottom. All `ok` → report and stop.
3. **Admin token missing** → the operator creates a personal access token on a Mattermost
   admin account and stores it with the `security` line `check` prints, typed with `!` so the
   token never enters this conversation. Never ask for the token itself.
4. **Provision** — first a dry run, always. On a first run ask the operator for the server URL,
   the team, their own Mattermost username (the relay trusts only it) and the channel
   (`rendezvous`), and add this clone as `--extra claude-meta=<root from msg self>`; later runs
   remember all of it. Show the plan. A `refused` name over 22 characters needs a short
   `--alias project=short` — propose one, the operator chooses. Only after the operator approves
   the plan: the same command with `--relay --apply`. It changes the Mattermost server.
5. **Hooks** → `alemax presence install --dry-run`, show the two hook entries, then `install`
   after the operator approves. It merges into `~/.claude/settings.json` and keeps a backup.
6. **Leftover `uv tool` copy** → after the hooks no longer use it, `uv tool uninstall alemax`,
   with the operator's OK.
7. **Re-check.** `alemax presence check` again; every line should read `ok`.
8. **Verify live.** The operator restarts one session in a provisioned folder (`/quit`, then
   `claude --continue`); `alemax presence status` then shows that account active. To relay posts,
   run `/alemax:mattermost-relay` next.

## Report

The final `check` (each item ok), the accounts created or kept, any alias chosen, and whether
the live verification showed the account active.
