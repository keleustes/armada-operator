---
name: collect-feedback
description: Use when the operator asks to collect or drain feedback across the fleet. Drain `.local/feedback.md` from every active project in the operator's `projects.yaml` — plus the meta-repo itself, which is never a row in that file by design — and land the surviving findings as `[ ]` entries in `openspec/ideas.md` § Raw ideas via one canonical PR. `alemax collect` parses the rows, offers dedup candidates and a harness-vs-meta suggestion per row, writes the entries and stamps each consumed source row so a re-run skips it. The three classification stages are the operator's, not the script's. Closes the cluster `/alemax:feedback` opens.
license: MIT
compatibility: Requires git, gh, and `uv`. No yq. Runs from the meta-repo clone; honors the canonical-only governance rule.
context: claude-meta-only
allowed-tools: Bash(uv run --directory plugins/alemax alemax collect *)
metadata:
  author: alemax
  reviewed_model: claude-5
  reviewed: 2026-11-04
---

## Wraps

`alemax collect` — `annotate`, `emit`, `scan`. Run it from the repo root as
`uv run --directory plugins/alemax alemax collect <subcommand> …`. `--help` documents every flag.

Exit codes, branching and the reasoning behind each rule are in spec `alemax-skills`
and the module's own docstrings. This body carries what a session must decide, and what
to report — restating the code here is how the two drift.

## Steps

1. **`scan --json`.** Nothing uncollected → say so and stop. Each row carries a proposed slug,
   `dedup_candidates` and a `suggested_class`. A missing project path is a warning, never a
   failure — but say which project went unread, because a project nobody can reach is invisible
   to every sweep, not just this one.
2. **Dedup, with the operator.** Read each named `proposal.md` and ask: same issue or different?
   **Candidates are a keyword overlap, not a verdict** — a row with none can still be a duplicate,
   and a row with three can be new.
3. **Harness vs meta.** `harness` rows are Anthropic's territory and do not belong in this
   backlog. Ask on every `ambiguous` row, and on any suggestion you doubt.
4. **One table, then confirm.** KEEP, OMIT — already shipped (naming what shipped it), OMIT —
   harness. The operator may override any row. **Nothing is written before an explicit yes.**
5. **Write the decisions file** to `.local/collect-<date>.json`, each kept row carrying the
   `source` and `ts` that `scan` reported — that pair is what step 7 stamps.
6. **Branch, `emit`, PR** to `alemaxdesign/claude-meta` (Guardrail 2 — never a fork's `main`).
   The PR body carries the KEEP table **and** an *Intentionally omitted* table with a reason per
   row: the omissions are the reviewable half, and the only record that a judgement was made.
7. **`annotate --pr <n>`, only after the PR exists.** Report what was stamped and any file that
   could not be written — those stay uncollected and resurface next run, which is the correct
   failure mode.

## Not for

Running from a project clone — it walks every project and opens a canonical PR; `scan` refuses.
Editing `openspec/ideas.md` § Archived or § Suggested next-up (that is `/alemax:archive-ideas` and
`/alemax:reprioritise-ideas`). Committing OpenSpec content to a fork's `main` — Guardrail 2, and
this always goes through a branch. Never stamp a source row before the PR exists: a failed
`gh pr create` leaves the branch for a retry, and unstamped rows are the thing that makes a
re-run safe.
