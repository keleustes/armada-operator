---
name: alemax-tidy-aiml
description: "Use when `git log origin/main..{branch}` has drifted — several commits per yaml, mixed-file commits, merge commits from sync rounds. Reshape an operator’s per-volume claude-meta fork branch into one commit per manifest plus preserved local changes. Preview the history rewrite and verify tree equivalence."
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
     body at templates/claude/skills/tidy-aiml/SKILL.md has moved on, this has not.
     Reconcile the prose; do not re-derive the conversion. -->

<!-- twin: intentional pair — this body names the fork-sync line and a final report step the Claude twin leaves to the operator -->

## Working directory

Keep the working directory at the repository being operated on; every command below
runs from its root. `alemax` is the packaged CLI under `plugins/alemax/`.
User instructions and existing authorization take precedence over workflow defaults;
ask only for missing decisions or actions outside the authorized scope.

## Wraps

`alemax tidy` — `preflight`, `preview`, `apply [--push]`, each with
`--json`. Run from the repo root as
`uv run --directory plugins/alemax alemax tidy <subcommand>`. It drives `meta/scripts/fork-tidy-aiml.sh`, which owns the
classification, the temp-branch build, the tree-equivalence check and the force-push. This body
decides nothing the script can decide.

## Steps

1. **Preflight.**

   ```
   uv run --directory plugins/alemax alemax tidy preflight
   ```

   Exit 0 proceed; exit 1 prints every blocker with its fix and **stops** — canonical origin, a
   non-per-volume branch, a dirty tree, `origin/main` ahead, fork `main` behind canonical (the
   reshape would land on a stale base), or commits already upstream under other SHAs.
2. **Duplicates are a stop sign, and the order matters.** When preflight lists `-` commits, your
   work is already on canonical under different SHAs. Reset below the lowest one, cherry-pick back
   any `+` above it, *then* `./meta/scripts/fork-sync.sh --non-interactive --push`, then start
   again. Sync first and Step 4 replays them as permanent no-op commits. A `-` you did not expect
   means content you think is fork-local is already upstream — read it before resetting.
3. **Preview.**

   ```
   uv run --directory plugins/alemax alemax tidy preview
   ```

   Exit 3 already tidy — say so and stop. Exit 1 a mixed yaml + non-yaml commit, named by SHA:
   split it (`git rebase -i origin/main`) and start again. Exit 0 prints the plan.
4. **Confirm, then apply.** Present the plan — the commits, the merge commits to be dropped, the
   force-push — and get an explicit yes with a concise question to the user; positional `--push` is intent,
   not consent. Then:

   ```
   uv run --directory plugins/alemax alemax tidy apply --push
   ```

   Drop `--push` to eyeball `git log` first; the script then prints the manual push line.
5. **Report the new shape**, and name any non-yaml commit preserved on top so the operator can
   decide whether it belongs in a canonical PR.

## Not for

Canonical (`alemaxdesign/claude-meta` has no per-volume branches), fork `main`, or a feature
branch — preflight refuses each. Not a substitute for `fork-sync.sh`: sync is merge-only and
additive, this is a history rewrite, and the two are deliberately separate tools. A failed
tree-equivalence check is a bug in the reshape, never something to force — the temp branch is
left for diffing; capture it with `$alemax-feedback`.
