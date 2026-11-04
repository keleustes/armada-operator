---
name: alemax-feedback
description: "Capture one finding — friction, a bug, an idea, or a harness quirk — as a row in this repo's `.local/feedback.md`, from any claude-meta-managed repo (meta or project). `alemax feedback add` writes the row `$alemax-collect-feedback` parses; `list` shows what is still uncollected. Use when the operator says \"note this\", \"feedback\", \"log that\", or wants something recorded without leaving the task."
license: MIT
metadata:
  author: alemax
  version: "2.0"
  source_reviewed_model: claude-5
  source_reviewed: 2026-09-04
---
<!-- The Codex CONVERSION is cloudison/photo-common's, taken verbatim: the
     $-invocations and the host-difference notes are
     hand-written work, not a transform of the Claude body.

     Its CONTENT is from alemax 2.0 (source_reviewed 2026-09-04), so where the Claude
     body at templates/claude/skills/feedback/SKILL.md has moved on, this has not.
     Reconcile the prose; do not re-derive the conversion. -->

## Working directory

Keep the working directory at the repository being operated on; every command below
runs from its root. `alemax` is the packaged CLI under `plugins/alemax/`.
User instructions and existing authorization take precedence over workflow defaults;
ask only for missing decisions or actions outside the authorized scope.

## Wraps

`alemax feedback` — `add` and `list`. From the repo root:
`uv run --directory plugins/alemax alemax feedback <subcommand> …`. `--help` documents both. The row shape (H3 heading, bold fields) is
the collector's contract; nothing else is written and nothing is committed.

## Steps

1. **Ask only what you cannot infer.** The finding is what the operator just said — one to three
   sentences in their words. The kind — `blocker` · `friction` · `idea` · `harness` (a Codex or other coding-agent
   defect, not this repo's) — from those words; ask only when genuinely ambiguous. The context is
   what they were doing: you know it, so pass a few words in `--context` instead of asking (the
   script's default is the branch and HEAD subject).
2. **Append:** `uv run --directory plugins/alemax alemax feedback add "<finding>" --kind <kind> --context "<…>"`
   — add `--diagnosis <path>` when a diagnosis directory already exists for it.
3. **Report** the row the script printed and the path. `.local/` is gitignored — nothing to commit.
   Non-zero exit → show its message and stop; never append by hand.

## Not for

- A full investigation → `$alemax-diagnose`. An idea that already has a change scoped →
  `openspec/ideas.md` by PR. In-progress work → the change's `tasks.md`.
- Collection is `$alemax-collect-feedback` (meta side); `… list` shows what it has not yet taken.
