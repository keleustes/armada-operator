---
name: tidy-aiml
description: Use when `git log origin/main..{branch}` has drifted — several commits per yaml, mixed-file commits, merge commits from sync rounds. Reshape the current per-volume operator branch (aiml0NN, app01, k8s01, iac01, …) into the canonical operator-state shape — origin/main + one commit per manifest yaml + any fork-divergent non-yaml commits cherry-picked on top. `alemax tidy` carries the preflight, the duplicate-commit classification a fork session must read before syncing, and the plan; `meta/scripts/fork-tidy-aiml.sh` does the reshape, the tree-equivalence check and the force-push-with-lease.
license: MIT
compatibility: Requires bash, git, `uv`, and a claude-meta fork clone with an `upstream` remote.
context: claude-meta-only
argument-hint: "[--dry-run|--push]"
allowed-tools: Bash(uv run --directory plugins/alemax alemax tidy *)
metadata:
  author: alemax
  reviewed_model: claude-5
  reviewed: 2026-11-04
---

## Wraps

`alemax tidy` — `apply`, `preflight`, `preview`. Run it from the repo root as
`uv run --directory plugins/alemax alemax tidy <subcommand> …`. `--help` documents every flag.

Exit codes, branching and the reasoning behind each rule are in spec `alemax-tidy-aiml-skill`
and the module's own docstrings. This body carries what a session must decide, and what
to report — restating the code here is how the two drift.

## Steps

1. **`preflight`.** It refuses on canonical, on `main`, on a dirty tree, and when the branch is
   behind. Duplicates already upstream are listed, not dropped silently — read them before
   continuing.
2. **`preview`.** This is the reviewable moment: it names every commit that will be dropped as a
   duplicate and every fork-local commit that will be replayed on top. A commit you do not
   recognise in that list is a reason to stop, not a rounding error.
3. **Confirm with AskUserQuestion, then `apply`.** The reshape rewrites this branch's history.
   `--push` force-pushes with lease; without it the push line is printed for the operator to run.
4. **Report the resulting shape** — origin/main, one commit per manifest yaml, then any non-yaml
   commits — and whether it was pushed.

## Not for

Canonical (`alemaxdesign/claude-meta` has no per-volume branches), fork `main`, or a feature
branch — preflight refuses each. Not a substitute for `fork-sync.sh`: sync is merge-only and
additive, this is a history rewrite, and the two are deliberately separate tools. A failed
tree-equivalence check is a bug in the reshape, never something to force — the temp branch is
left for diffing; capture it with `/alemax:feedback`.
