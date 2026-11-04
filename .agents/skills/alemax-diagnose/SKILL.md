---
name: alemax-diagnose
description: "Scaffold a structured diagnosis in the current project or meta-repo from the user’s symptom, scope, and hypothesis. Use when a finding needs an investigation beyond a feedback row."
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
     body at templates/claude/skills/diagnose/SKILL.md has moved on, this has not.
     Reconcile the prose; do not re-derive the conversion. -->

## Working directory

Keep the working directory at the repository being operated on; every command below
runs from its root. `alemax` is the packaged CLI under `plugins/alemax/`.
User instructions and existing authorization take precedence over workflow defaults;
ask only for missing decisions or actions outside the authorized scope.

## Wraps

`alemax diagnose` — `new` and `list`. From the repo root:
`uv run --directory plugins/alemax alemax diagnose <subcommand> …`. `--help` documents both. The template, the slug rule, the
collision refusal and the `.local/` gitignore gate are the script's; the questions are this
body's. Spec: `alemax-skills`.

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

- A one-to-three-sentence finding → `$alemax-feedback`; a solution ready to scope → `$openspec-propose`.
- The convention itself, and the optional `forensics.md` / `smoke-tests.md` /
  `lessons-learned.md` siblings a long session adds by hand → `openspec/diagnosis/README.md`.
