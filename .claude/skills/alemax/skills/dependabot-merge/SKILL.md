---
name: dependabot-merge
description: Use when the operator names a Dependabot PR they have already accepted. Unblock and squash-merge one stale Dependabot PR (`mergeStateStatus` UNKNOWN — GitHub stops recomputing mergeability after about a week) — `@dependabot rebase`, a bounded poll, merge — from any repo with a GitHub remote. `alemax dependabot` drives `gh`, dry-run by default; before it reports any red check it finds the workflow run and says whether a step ever executed, so an exhausted Actions pool is never diagnosed as code.
license: MIT
compatibility: Requires `gh` (authenticated), git, and `uv`. Posts a comment and merges a PR only with `--apply`.
context: either
argument-hint: "<pr-number> [--apply] | --checks-only <pr-number>"
allowed-tools: Bash(uv run --directory plugins/alemax alemax dependabot *)
metadata:
  author: alemax
  reviewed_model: claude-5
  reviewed: 2026-11-04
---

## Wraps

`alemax dependabot` — no subcommands — flags only. Run it from the repo root as
`uv run --directory plugins/alemax alemax dependabot <subcommand> …`. `--help` documents every flag.

Exit codes, branching and the reasoning behind each rule are in spec `alemax-dependabot-skills`
and the module's own docstrings. This body carries what a session must decide, and what
to report — restating the code here is how the two drift.

## Steps

1. **Dry run:** `uv run --directory plugins/alemax alemax dependabot $0`
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

- Several PRs → `/alemax:dependabot-merge-all` (same script, `--all` or a list in order).
- A bump the operator has not accepted yet — this is merge mechanics, not the review.
- A non-Dependabot PR: the script refuses; merge it by hand.
