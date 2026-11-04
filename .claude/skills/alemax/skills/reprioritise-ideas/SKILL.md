---
name: reprioritise-ideas
description: Use when the operator asks to pick what comes next, often before a planning session. Curate § Suggested next-up of this repo's `openspec/ideas.md` — walk § Raw ideas for `[ ]` entries, present them with one-line summaries, let the operator pick 3–5, and write pointer-only entries (`- {slug} — {summary}`). Each run replaces the section; `--add` appends instead and `--clear` empties it. `alemax ideas reprioritise` does the writing, dry-run by default. Never touches § Archived ideas or § Raw ideas content.
license: MIT
compatibility: Requires git and `uv`; `gh` only for the PR at the end. Operates exclusively under `openspec/`. Context-adaptive — in claude-meta the curation lands by PR to canonical (Guardrail 2); in any other repo it lands against that repo's own origin.
context: either
argument-hint: "[--add] [--clear]"
allowed-tools: Bash(uv run --directory plugins/alemax alemax ideas *)
metadata:
  author: alemax
  reviewed_model: claude-5
  reviewed: 2026-11-04
---

## Wraps

`alemax ideas` — `archive`, `list`, `reprioritise`. Run it from the repo root as
`uv run --directory plugins/alemax alemax ideas <subcommand> …`. `--help` documents every flag.

Exit codes, branching and the reasoning behind each rule are in spec `alemax-skills`
and the module's own docstrings. This body carries what a session must decide, and what
to report — restating the code here is how the two drift.

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

- Moving `[x]` entries into § Archived ideas — `/alemax:archive-ideas` (same script, `archive`).
  This verb never edits § Raw ideas or § Archived ideas.
- Mirroring § Raw ideas: § Suggested next-up is a curated 3–5, not the whole backlog.
