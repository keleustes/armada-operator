---
name: alemax-reprioritise-ideas
description: "Use when the user asks to pick what comes next, often before a planning session. Curate the Suggested next-up section of openspec/ideas.md from the user’s selected raw ideas. Preview changes before applying; preserve raw and archived sections."
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
     body at templates/claude/skills/reprioritise-ideas/SKILL.md has moved on, this has not.
     Reconcile the prose; do not re-derive the conversion. -->

## Working directory

Keep the working directory at the repository being operated on; every command below
runs from its root. `alemax` is the packaged CLI under `plugins/alemax/`.
User instructions and existing authorization take precedence over workflow defaults;
ask only for missing decisions or actions outside the authorized scope.

## Wraps

`alemax ideas` — the same script `$alemax-archive-ideas`
wraps: § Suggested next-up and § Archived ideas are two halves of one file's lifecycle and one
parser serves both. From the repo root:
`uv run --directory plugins/alemax alemax ideas reprioritise …`. `--help` documents every verb. The picking is this body's; the
parse, rewrite and atomic write are the script's. Spec: `alemax-skills`.

## Steps

1. **Show the backlog.** `uv run --directory plugins/alemax alemax ideas reprioritise`
   with no `--pick` prints the numbered `[ ]` entries (slug + one-line summary) and what
   § Suggested next-up holds today. Zero `[ ]` entries → it says so; nothing to curate.
2. **Ask for 3–5**, by index or slug. An unknown slug is refused by name — re-ask, never
   substitute. If the section is already populated, ask replace / add / skip: replace is the
   default and the spec's rule (each run is a fresh curation), `--add` appends, skip ends the
   run unchanged. `--clear` empties the section outright.
3. **See the plan, then apply:** the same line plus one `--pick <slug|index>` per choice —
   dry-run first, then `--apply`. Over ten pointers warns, never refuses. The script refuses a
   file carrying conflict markers, and uncommitted changes to `openspec/ideas.md` unless `--force`.
4. **Land it.** The script commits nothing. Branch `chore/reprioritise-ideas-<today>`, commit,
   push; in claude-meta open a PR with `gh pr create --base main` (Guardrail 2), in a project
   push to its own origin. **Report** what was replaced by what, and the PR.

## Not for

- Moving `[x]` entries into § Archived ideas — `$alemax-archive-ideas` (same script, `archive`).
  This verb never edits § Raw ideas or § Archived ideas.
- Mirroring § Raw ideas: § Suggested next-up is a curated 3–5, not the whole backlog.
