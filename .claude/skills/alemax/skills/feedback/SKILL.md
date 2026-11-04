---
name: feedback
description: Capture one finding — friction, a bug, an idea, or a harness quirk — as a row in this repo's `.local/feedback.md`, from any claude-meta-managed repo (meta or project). `alemax feedback add` writes the row `/alemax:collect-feedback` parses; `list` shows what is still uncollected. Use when the operator says "note this", "feedback", "log that", or wants something recorded without leaving the task.
license: MIT
compatibility: Requires git and `uv`. Honors `dot-local-scratch-convention` (`.local/` gitignored — the script refuses to write otherwise).
context: either
argument-hint: "<finding> [--kind blocker|friction|idea|harness] [--diagnosis <path>]"
allowed-tools: Bash(uv run --directory plugins/alemax alemax feedback *)
metadata:
  author: alemax
  reviewed_model: claude-5
  reviewed: 2026-11-04
---

## Wraps

`alemax feedback` — `add`, `list`. Run it from the repo root as
`uv run --directory plugins/alemax alemax feedback <subcommand> …`. `--help` documents every flag.

Exit codes, branching and the reasoning behind each rule are in spec `alemax-skills`
and the module's own docstrings. This body carries what a session must decide, and what
to report — restating the code here is how the two drift.

## Steps

1. **Ask only what you cannot infer.** The finding is what the operator just said — one to three
   sentences in their words. The kind — `blocker` · `friction` · `idea` · `harness` (a Claude Code
   defect, not this repo's) — from those words; ask only when genuinely ambiguous. The context is
   what they were doing: you know it, so pass a few words in `--context` instead of asking (the
   script's default is the branch and HEAD subject).
2. **Append:** `uv run --directory plugins/alemax alemax feedback add "<finding>" --kind <kind> --context "<…>"`
   — add `--diagnosis <path>` when a diagnosis directory already exists for it.
3. **Report** the row the script printed and the path. `.local/` is gitignored — nothing to commit.
   Non-zero exit → show its message and stop; never append by hand.

## Not for

- A full investigation → `/alemax:diagnose`. An idea that already has a change scoped →
  `openspec/ideas.md` by PR. In-progress work → the change's `tasks.md`.
- Collection is `/alemax:collect-feedback` (meta side); `… list` shows what it has not yet taken.
