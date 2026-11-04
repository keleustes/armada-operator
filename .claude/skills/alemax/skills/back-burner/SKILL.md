---
name: back-burner
description: Use when the operator says they are stopping, winding down, or wants a checkpoint for next time. End-of-session wind-down — write `.local/resume.md` (the checkpoint `/alemax:front-burner` reads next time) from git state and the operator's next step in their own words, then hand off to `/compact` + `/quit`. `alemax burner down` does the writing; it deletes nothing, commits nothing, and never touches a settings file.
license: MIT
compatibility: Requires git and `uv`. Honors `dot-local-scratch-convention` (`.local/` gitignored — the script refuses to write otherwise). Never invokes `/compact` or `/quit`.
context: either
argument-hint: "[--dry-run]"
allowed-tools: Bash(uv run --directory plugins/alemax alemax burner *) Bash(git status *)
metadata:
  author: alemax
  reviewed_model: claude-5
  reviewed: 2026-11-04
---

## Wraps

`alemax burner` — `down`, `up`. Run it from the repo root as
`uv run --directory plugins/alemax alemax burner <subcommand> …`. `--help` documents every flag.

Exit codes, branching and the reasoning behind each rule are in spec `back-burner-session-wind-down`
and the module's own docstrings. This body carries what a session must decide, and what
to report — restating the code here is how the two drift.

## Steps

1. **Draft the next step** from the session, one or two lines in the operator's words, and let them
   edit it. One question — not a phase per file. Add an `--open "<question>"` for anything they
   want to remember deciding.
2. **The working tree is the operator's call.** `git status --short`; anything worth committing
   before stopping is a normal commit now. Whatever stays uncommitted is recorded by the script as
   an open item — nothing is stashed or committed on their behalf.
3. **Write:** `uv run --directory plugins/alemax alemax burner down --note "<next step>"`
   — `--dry-run` prints the checkpoint instead. The script also counts today's `/tmp/claude-*`
   files and says so; removing them is the operator's, not yours.
4. **Report** the summary line and the path, then exactly: "Wind-down complete. Run /compact, then
   /quit when ready." Never run those yourself; this is the last action.

## Not for

- Session-scoped settings grants — `.claude/settings.local.json` is reconciled against the shipped
  `settings-template.json` floor (`bin/reconcile-settings.py`, spec `settings-template`), not here.
- Committing work — use `git`. Switching projects mid-session — `/alemax:front-burner` from the other clone.
