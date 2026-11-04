---
name: diagnose
description: Use when a finding is bigger than a feedback row and warrants a multi-section investigation. Scaffold a diagnosis directory with the standardized 10-section template, from any claude-meta-managed repo. `alemax diagnose new` writes `{location}/diagnosis.md` from topic slug + scope + symptom + starting hypothesis; `list` shows the diagnoses this repo already has. The location is always asked — `openspec/diagnosis/YYYY-MM-DD-{slug}/` (committed, cross-project) or `.local/diagnosis/{slug}/` (operator-local) — with the smart default for the current repo highlighted.
license: MIT
compatibility: "Requires git and `uv`. Honors `dot-local-scratch-convention` (spec `scaffolding-boundary`: `.local/` gitignored — the script refuses to write there otherwise)."
context: either
argument-hint: "[<topic-slug>] [--local | --committed]"
allowed-tools: Bash(uv run --directory plugins/alemax alemax diagnose *)
metadata:
  author: alemax
  reviewed_model: claude-5
  reviewed: 2026-11-04
---

## Wraps

`alemax diagnose` — `list`, `new`. Run it from the repo root as
`uv run --directory plugins/alemax alemax diagnose <subcommand> …`. `--help` documents every flag.

Exit codes, branching and the reasoning behind each rule are in spec `alemax-skills`
and the module's own docstrings. This body carries what a session must decide, and what
to report — restating the code here is how the two drift.

## Steps

1. **Always ask where it lives** — the default is highlighted, never taken silently:
   `openspec/diagnosis/YYYY-MM-DD-<slug>/` (committed, cross-project; default in a claude-meta
   clone) or `.local/diagnosis/<slug>/` (operator-local, gitignored; default elsewhere). The
   answer is `--location openspec|local`; `--committed` / `--local` are the operator's spelling.
2. **Ask only what you cannot infer** — topic slug (kebab-case, or the script refuses), one-line
   scope, the symptom (it becomes the H1), the starting hypothesis (skippable; the rest are not).
3. **Scaffold:** `uv run --directory plugins/alemax alemax diagnose new --slug <slug> --symptom "<…>" --scope "<…>" --hypothesis "<…>" --location <openspec|local>`
   — `--dry-run` prints the file instead of writing it. An existing directory is refused by
   name: confirm, then pick another slug or pass `--force` (it overwrites that directory's
   `diagnosis.md` and nothing else).
4. **Report the path**, then fill the sections in conversationally — the scaffold is a skeleton;
   `… list` shows what this repo already has. Landing it is separate: the script commits nothing
   and creates no branch. A `.local/` diagnosis stays put; an `openspec/diagnosis/` one is
   canonical content and lands by branch + PR (Guardrail 2).

## Not for

- A one-to-three-sentence finding → `/alemax:feedback`; a solution ready to scope → `/opsx:propose`.
- The convention itself, and the optional `forensics.md` / `smoke-tests.md` /
  `lessons-learned.md` siblings a long session adds by hand → `openspec/diagnosis/README.md`.
