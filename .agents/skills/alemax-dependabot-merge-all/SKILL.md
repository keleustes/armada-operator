---
name: alemax-dependabot-merge-all
description: "Use when several Dependabot PRs are open against one repo. Merge several Dependabot PRs in sequence, re-rebasing each after the previous one lands — squash-merging one flips every other PR touching the same file to DIRTY (their diff used the now-changed line as context), so each needs its own `@dependabot rebase` round-trip. Same script as `$alemax-dependabot-merge`, run with `--all` or an ordered list; stops at the first PR that stops. Works from any repo with a GitHub remote."
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
     body at templates/claude/skills/dependabot-merge-all/SKILL.md has moved on, this has not.
     Reconcile the prose; do not re-derive the conversion. -->

## Working directory

Keep the working directory at the repository being operated on; every command below
runs from its root. `alemax` is the packaged CLI under `plugins/alemax/`.
User instructions and existing authorization take precedence over workflow defaults;
ask only for missing decisions or actions outside the authorized scope.

## Wraps

`alemax dependabot` — the per-PR loop, run over a
batch: it validates every author before acting on any, handles the PRs in order, and stops the batch
at the first `stopped:` (a conflict, a blocked or red check, a timeout) so nothing is merged onto an
unresolved base. `--all` takes every open Dependabot PR, oldest first. Spec: `alemax-dependabot-skills`.

## Steps

1. **Dry run:** `uv run --directory plugins/alemax alemax dependabot --all`
   (or the PR numbers in the order wanted) — confirm the list with the operator.
2. **Apply:** the same line with `--apply`. Each subsequent PR is rebased by the script after the
   previous merge; do not comment or poll by hand.
3. **Report** the summary block — which merged (sha), which stopped and why, which are untouched.
   On a stop the operator fixes the blocker and re-runs with the remaining numbers.

## Not for

- One PR → `$alemax-dependabot-merge <pr>`.
- PRs touching different files — they merge independently; batching adds nothing.
- Bumps the operator has not accepted — decide first, then batch.
