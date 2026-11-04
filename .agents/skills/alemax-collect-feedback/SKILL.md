---
name: alemax-collect-feedback
description: "Use when the user asks to collect or drain feedback across the fleet. Drain `.local/feedback.md` from every active project in the operator's `projects.yaml` — plus the meta-repo itself, which is never a row in that file by design — and land the surviving findings as `[ ]` entries in `openspec/ideas.md` § Raw ideas via one canonical PR. `alemax collect` parses the rows, offers dedup candidates and a harness-vs-meta suggestion per row, writes the entries and stamps each consumed source row so a re-run skips it. The three classification stages are the operator's, not the script's. Closes the cluster `$alemax-feedback` opens."
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
     body at templates/claude/skills/collect-feedback/SKILL.md has moved on, this has not.
     Reconcile the prose; do not re-derive the conversion. -->

## Working directory

Keep the working directory at the repository being operated on; every command below
runs from its root. `alemax` is the packaged CLI under `plugins/alemax/`.
User instructions and existing authorization take precedence over workflow defaults;
ask only for missing decisions or actions outside the authorized scope.

## Wraps

`alemax collect` — `scan`, `emit --decisions <file>`,
`annotate --decisions <file> --pr <n>`, each with `--json`. Run from the meta-repo root as
`uv run --directory plugins/alemax alemax collect <subcommand>`. It refuses outside a claude-meta clone, parses only
uncollected rows, and decides nothing — the verdicts in the decisions file are this session's,
written after the operator confirms.

## Steps

1. **Scan.**

   ```
   uv run --directory plugins/alemax alemax collect scan --json
   ```

   Exit 3 means nothing uncollected — say so and stop. Each row carries `project`, `ts`, `kind`,
   `finding`, a proposed `slug`, `dedup_candidates` (changes sharing rare terms) and
   `suggested_class` (`harness` · `meta` · `ambiguous`). A missing project path becomes a
   `warnings` entry, never a failure.
2. **Stage 1 — dedup.** For each row with candidates, read the named `proposal.md` and ask the
   operator: same issue or different? Candidates are a keyword overlap, not a verdict — a row
   with none can still be a duplicate, and a row with three can be new.
3. **Stage 2 — harness vs meta.** `harness` rows are the relevant coding-agent provider's territory and do not belong in
   this backlog; `meta` rows do. Ask on every `ambiguous` row, and on any suggestion you doubt.
4. **Stage 3 — one table, then confirm.** Show KEEP (project, kind, one-liner, slug), OMIT —
   already shipped (with the change it shipped as), and OMIT — harness. Let the operator override
   any row. Nothing is written before an explicit yes.
5. **Write the decisions file** to `.local/collect-<date>.json` — `{"kept": [...], "omitted":
   [...]}` , each kept row carrying the `source` and `ts` `scan` reported (that pair is what
   Step 7 stamps). `.local/` is gitignored; it never rides the PR.
6. **Branch, append, PR.**

   ```
   git checkout -b chore/collect-feedback-<date>
   uv run --directory plugins/alemax alemax collect emit --decisions .local/collect-<date>.json
   git commit -am "ideas: collected feedback from <n> projects (<date>)"
   git push -u origin chore/collect-feedback-<date>
   gh pr create --base main --repo alemaxdesign/claude-meta
   ```

   The PR body carries the KEEP table and an **Intentionally omitted** table naming the reason
   per row — the omissions are the reviewable half.
7. **Stamp the sources, only after the PR exists.**

   ```
   uv run --directory plugins/alemax alemax collect annotate --decisions .local/collect-<date>.json --pr <number>
   ```

   Report which rows were stamped and any file that could not be written; those stay uncollected
   and simply resurface next run.

## Not for

Running from a project clone — it walks every project and opens a canonical PR; `scan` refuses.
Editing `openspec/ideas.md` § Archived or § Suggested next-up (that is `$alemax-archive-ideas` and
`$alemax-reprioritise-ideas`). Committing OpenSpec content to a fork's `main` — Guardrail 2, and
this always goes through a branch. Never stamp a source row before the PR exists: a failed
`gh pr create` leaves the branch for a retry, and unstamped rows are the thing that makes a
re-run safe.
