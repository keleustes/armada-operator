---
name: archive-ideas
description: Run when § Raw ideas has accumulated `[x]` entries (weekly, after N archives, before a demo). Periodic reshape of this repo's `openspec/ideas.md` — snapshot it, then for each `[x]` entry in § Raw ideas classify it by the archived change's `proposal.md § Capabilities`, append a one-line bullet under each matching capability heading in § Archived ideas — by capability, and remove the full body from § Raw ideas. `alemax ideas archive` does all of it, dry-run by default; the per-entry confirmation is this body's.
license: MIT
compatibility: Requires git and `uv`; `gh` only for the PR at the end. Operates exclusively under `openspec/`. Context-adaptive — in claude-meta the reshape lands by PR to canonical (Guardrail 2); in any other repo it lands against that repo's own origin.
context: either
argument-hint: "[--context <snapshot-suffix>] [--yes-all]"
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

- Flipping one `[ ]` to `[x]` — that is `/opsx:archive`, and this skill batches what it leaves.
- § Suggested next-up → `/alemax:reprioritise-ideas` (same script, `reprioritise`).
- Fewer than about three `[x]` entries — the reshape is a batch. § Archived ideas' capability one-liners are stable text: bullets go under them, never over them.
