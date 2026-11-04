---
name: lint-all
description: Run all three audits — documents, skills and the toolchain level — over this repo and print one summary; non-zero if any refuses. The one to invoke when the question is simply "is this repo still consistent with itself?", and the one to run before a broadcast or a release.
license: MIT
compatibility: Requires git and `uv`. Runs in a claude-meta clone or any bootstrapped project; the checkers ship as class-M `bin/**`, so a project that predates them is told to run `/alemax:complete-update` rather than failing.
context: either
argument-hint: "[--strict] [--include-specs] [--repo <path>] [--list]"
allowed-tools: Bash(uv run --directory plugins/alemax alemax lint *)
metadata:
  author: alemax
  version: "1.0"
  reviewed_model: claude-5
  reviewed: 2026-11-04
---

## Wraps

`alemax lint` — `all`, `docs`, `skills`, `toolchain`. Run it from the repo root as
`uv run --directory plugins/alemax alemax lint <subcommand> …`. `--help` documents every flag.

Exit codes, branching and the reasoning behind each rule are in spec `claude-consistency-lint`
and the module's own docstrings. This body carries what a session must decide, and what
to report — restating the code here is how the two drift.

## Steps

1. **Just run it**, from the repo the operator is in. `--repo` only when they name another
   clone; a repo with its own session is reached by `/alemax:send-msg`, never audited from here.
2. **Lead with the summary table**, then the refusals grouped by cause. A checker that is not
   installed is reported and skipped, never a failure — a project gets it on its next class-M
   delivery.
3. **Say what is new.** Nothing gates without `--strict`, and every finding is printed either
   way, so report the warning count as well as the exit status — the number that matters is the
   change since the last run. `--strict` before a broadcast or a release.
4. **Fix nothing without asking**, then hand back to the half that owns the fix —
   `/alemax:lint-docs`, `/alemax:lint-skills` or `/alemax:lint-toolchain` carries the per-rule
   guidance.

## Not for

- One audit only → `/alemax:lint-docs` · `/alemax:lint-skills` · `/alemax:lint-toolchain`.
- Whether a project is stale on the class-M set → ask the meta-repo session to run its
  status check; a delivery → `/alemax:update-skills` then, in the project's own session,
  `/alemax:complete-update`.
- A finding worth keeping rather than fixing now → `/alemax:feedback`.
