---
name: alemax-dependabot-merge
description: "Unblock and squash-merge one stale Dependabot PR (`mergeStateStatus` UNKNOWN — GitHub stops recomputing mergeability after about a week) — `@dependabot rebase`, a bounded poll, merge — from any repo with a GitHub remote. `alemax dependabot` drives `gh`, dry-run by default; before it reports any red check it finds the workflow run and says whether a step ever executed, so an exhausted Actions pool is never diagnosed as code. Use when the operator names a Dependabot PR they have already accepted."
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
     body at templates/claude/skills/dependabot-merge/SKILL.md has moved on, this has not.
     Reconcile the prose; do not re-derive the conversion. -->

## Working directory

Keep the working directory at the repository being operated on; every command below
runs from its root. `alemax` is the packaged CLI under `plugins/alemax/`.
User instructions and existing authorization take precedence over workflow defaults;
ask only for missing decisions or actions outside the authorized scope.

## Wraps

`alemax dependabot` — the whole loop: inspect, refuse a non-Dependabot
author, skip the rebase when already CLEAN, post `@dependabot rebase`, poll up to three minutes,
squash-merge with `--delete-branch`, and never merge from UNKNOWN, BLOCKED or past a red check. From
the repo root: `uv run --directory plugins/alemax alemax dependabot …`. `--help` has every flag. Spec: `alemax-dependabot-skills`.

## Steps

1. **Dry run:** `uv run --directory plugins/alemax alemax dependabot <pr-number>`
   — one line per state, ending `would merge` / `would post @dependabot rebase` / `stopped: <reason>`.
2. **Apply:** the same line with `--apply`. It polls the bot itself; do not poll by hand.
3. **Report** the last line — `merged <sha>` or `stopped: <reason>`. On `stopped`, say what the
   operator can do (resolve the conflict, satisfy the check, wait for the Actions reset, re-run);
   do not retry with other flags and do not merge past a red check by hand.

A red check is a code failure only after the run executed. The script prints the verdict per run
— `NEVER EXECUTED` (no job completed a step: an exhausted Actions pool or disabled workflows; wait
for the monthly reset, touch no code) or `executed — job … failed at step …` (diagnose). For any PR,
Dependabot or not: `… --checks-only <pr>`.

## Not for

- Several PRs → `$alemax-dependabot-merge-all` (same script, `--all` or a list in order).
- A bump the operator has not accepted yet — this is merge mechanics, not the review.
- A non-Dependabot PR: the script refuses; merge it by hand.
