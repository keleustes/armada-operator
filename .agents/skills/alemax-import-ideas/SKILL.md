---
name: alemax-import-ideas
description: "Use after dictating ideas on mobile and wanting to triage them on the desktop. Import mobile-captured Obsidian ideas into the appropriate project backlog, with per-row decisions and source annotations after a PR exists."
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
     body at templates/claude/skills/import-ideas/SKILL.md has moved on, this has not.
     Reconcile the prose; do not re-derive the conversion. -->

<!-- twin: intentional pair — one extra summarise step the Claude twin folds into its last -->

## Working directory

Keep the working directory at the repository being operated on; every command below
runs from its root. `alemax` is the packaged CLI under `plugins/alemax/`.
User instructions and existing authorization take precedence over workflow defaults;
ask only for missing decisions or actions outside the authorized scope.

## Wraps

`alemax vault` — `vault`, `scan [--only <project>]`,
`annotate --file <path> --line <n> --summary "<text>"`, each with `--json`. Run from the repo root
as `uv run --directory plugins/alemax alemax vault <subcommand>`. The vault default is a literal `/Users/<u>/Library/Mobile
Documents/…` path per the system-path-rule — iCloud is a boot-disk service, so a `~` under
HOME-redirect mis-routes silently.

## Context

`claude-meta-only`, because a full run reads `projects.yaml` and routes to several repos.
`--only <project>` relaxes that: from a project clone it drains just that project's
`ideas-on-the-go-<project>.md` — the file `init-project.sh` seeds into the vault.

## Steps

1. **Resolve and scan.**

   ```
   uv run --directory plugins/alemax alemax vault scan --json
   ```

   Exit 3 means nothing pending — say so and stop. A missing vault exits 1 with the setup hint
   (`vault` alone prints it). Report every `warnings` entry: a legacy `ideas_on_the_go_path`
   field, two files routing to one target, and per file a `stale` flag — a file untouched for
   days may be waiting on iCloud rather than empty, which is worth saying before draining it.
2. **Read the route per file** — the filename decided it, not the row text.
   - `cross-cutting` (un-suffixed, or `-claude-meta`) → canonical `openspec/ideas.md` § Raw ideas.
   - `existing-project:<name>` → that project's own `openspec/ideas.md`.
   - `unknown:<name>` → **a concise question to the user**: bootstrap `<name>` via `$alemax-new-project`, route
     it as cross-cutting instead, skip the file (leave it untouched so a re-run re-asks), or
     cancel the session. A failed bootstrap annotates its rows `failed: <reason>` and moves on.
3. **Per row, one question** — import, or skip-personal. There is no per-row routing. A row that
   is really two ideas: skip it this run and split it in Obsidian.
4. **Land the kept rows** on a branch in the routed repo, then open the PR. Canonical content is
   canonical-only (Guardrail 2) — always a branch, never a commit on a fork's `main`.

   ```
   git checkout -b chore/import-ideas-<date>
   git commit -am "ideas: imported <n> captured idea(s) (<date>)"
   gh pr create --base main
   ```
5. **Annotate each consumed row, only after its PR exists.**

   ```
   uv run --directory plugins/alemax alemax vault annotate --file <vault file> --line <n> --summary "cross-cutting, PR #<num>"
   ```

   Summaries: `cross-cutting, PR #<n>` · `existing-project: <name>, PR #<n>` ·
   `new-project: <name>` · `skipped: personal` · `failed: <reason>`. The script refuses any line
   that is not a pending `- [ ]` row, so a re-run cannot double-stamp.
6. **Summarise** — per file, how many imported, skipped, failed, and the PR each landed in.

## Not for

Deleting or reorganising vault files — this only flips `- [ ]` to `- [x]` in place, and never
touches a row it did not import. Draining a project's file from meta and *applying* it there:
routing writes to that project's clone through its own PR, and nothing here commits to a
project's `main` (Guardrail 4). A row whose PR never opened stays pending — that is what makes a
re-run safe, so never stamp ahead of the PR.
