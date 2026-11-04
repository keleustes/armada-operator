---
name: alemax-archive-ideas
description: "Periodic reshape of this repo's `openspec/ideas.md` — snapshot it, then for each `[x]` entry in § Raw ideas classify it by the archived change's `proposal.md § Capabilities`, append a one-line bullet under each matching capability heading in § Archived ideas — by capability, and remove the full body from § Raw ideas. `alemax ideas archive` does all of it, dry-run by default; the per-entry confirmation is this body's. Run when § Raw ideas has accumulated `[x]` entries (weekly, after N archives, before a demo)."
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
     body at templates/claude/skills/archive-ideas/SKILL.md has moved on, this has not.
     Reconcile the prose; do not re-derive the conversion. -->

## Working directory

Keep the working directory at the repository being operated on; every command below
runs from its root. `alemax` is the packaged CLI under `plugins/alemax/`.
User instructions and existing authorization take precedence over workflow defaults;
ask only for missing decisions or actions outside the authorized scope.

## Wraps

`alemax ideas` — `list`, `archive`, `reprioritise`; one script for both
halves of `openspec/ideas.md`'s lifecycle (`$alemax-reprioritise-ideas` is the other half). From
the repo root: `uv run --directory plugins/alemax alemax ideas <subcommand> …`. `--help` documents every verb. The parse, classification,
snapshot and atomic write are the script's; confirmation and the PR are this body's. Specs:
`alemax-skills`, `spec-governance`.

## Steps

1. **See the plan.** `uv run --directory plugins/alemax alemax ideas archive`
   — dry-run by default: each `[x]` entry with the capability it resolved to and the tier it used
   (1 inline pointer · 2 body slug-mention · 3 operator), then what it could not classify.
2. **Confirm each row** (`y` / `skip` / `edit`) — with `--yes-all`, only the unresolved ones. `skip`
   → name the survivors with `--only <slug>`. `edit` or unresolved → ask which capability and pass
   `--capability <slug>=<capability>` (comma-separate several). Never guess one.
3. **Apply:** the same line plus `--apply` and step 2's flags. It snapshots to
   `openspec/ideas-snapshots/<today>-pre-reshape.md` (`--context <name>` for another suffix; `-2`,
   `-3` … on collision) first, and refuses conflict markers or an uncommitted file unless `--force`.
4. **Land it.** The script commits nothing. Branch `chore/reshape-ideas-<today>`, commit the file and
   the snapshot, push; in claude-meta open a PR with `gh pr create --base main` (Guardrail 2 — never
   a direct commit to a fork's `main`), else push to the project's own origin. **Report** the counts
   (reshaped · skipped · unresolved), the snapshot and the PR.

## Not for

- Flipping one `[ ]` to `[x]` — that is `$openspec-archive-change`, and this skill batches what it leaves.
- § Suggested next-up → `$alemax-reprioritise-ideas` (same script, `reprioritise`).
- Fewer than about three `[x]` entries — the reshape is a batch. § Archived ideas' capability one-liners are stable text: bullets go under them, never over them.
