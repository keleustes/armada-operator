---
name: front-burner
description: Use at session start, or when the operator asks "where was I?". Pick up where the last session left off — read `.local/resume.md` (written by `/alemax:back-burner`), report the drift since it (branch, HEAD, working tree, stashes; `--check-remote` for origin/main, `--check-openspec` for new changes and open PRs) with a staleness warning, and propose a concrete next step without executing it. `alemax burner up` does the reading; strictly read-only.
license: MIT
compatibility: Requires git and `uv`; `gh` only for `--check-openspec`. Read-only on the repo and on `.local/resume.md`.
context: either
argument-hint: "[--check-remote] [--check-openspec]"
allowed-tools: Bash(uv run --directory plugins/alemax alemax burner up *)
metadata:
  author: alemax
  reviewed_model: claude-5
  reviewed: 2026-11-04
---

## Wraps

`alemax burner` — `down`, `up`. Run it from the repo root as
`uv run --directory plugins/alemax alemax burner <subcommand> …`. `--help` documents every flag.

Exit codes, branching and the reasoning behind each rule are in spec `front-burner-session-resume`
and the module's own docstrings. This body carries what a session must decide, and what
to report — restating the code here is how the two drift.

## Steps

1. **Run:** `uv run --directory plugins/alemax alemax burner up $ARGUMENTS`
   Pass `--check-remote` and `--check-openspec` when the operator wants
   the remote signals; they cost a fetch and an API call.
2. **Read it in the order printed** — staleness and mode caveats first, then the recorded next step,
   the open questions, the drift block, recent activity. A checkpoint over a week old is a candidate
   for discarding, not a plan.
3. **Propose, never execute:** (a) the recorded next step as written, (b) the top drift signal
   (uncommitted work, commits on origin/main, a branch change), (c) something else. Stop after the
   operator picks — they run it in the next turn. No commit, no stash, no checkout, no slash command,
   no write to `.local/resume.md`.

## Not for

- Writing the checkpoint → `/alemax:back-burner`. Discarding it → `rm .local/resume.md` by hand.
- Another repo — current clone only; run it from the other clone's session.
