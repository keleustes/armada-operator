---
name: alemax-complete-update
description: "Use when `.local/HANDOFF.md` names a delivery for this project. Complete a meta delivery from the receiving project’s Codex session: locate the branch, preserve customizations, verify Codex skills, run checks, and follow the project’s PR process."
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
     body at templates/claude/skills/complete-update/SKILL.md has moved on, this has not.
     Reconcile the prose; do not re-derive the conversion. -->

## Working directory

Keep the working directory at the repository being operated on; every command below
runs from its root. `alemax` is the packaged CLI under `plugins/alemax/`.
User instructions and existing authorization take precedence over workflow defaults;
ask only for missing decisions or actions outside the authorized scope.

## Workflow

Run in the receiving project, never from the meta-repo. The helper locates a
broadcast or sync delivery; it does not apply, commit, or push it.

```bash
uv run --directory plugins/alemax alemax update context
uv run --directory plugins/alemax alemax update handoff
uv run --directory plugins/alemax alemax update locate --json
```

1. Read the handoff and respect the context check. Multiple refs require selection;
   no handoff or ref means inspect remaining gaps before reporting current.
2. Preserve untracked bootstrap files listed by `locate` before applying a delivery
   that would overwrite them. Review and commit only those intended files; never
   delete them or force the application. Follow the project's branch/PR policy.
3. Use the reported verb: cherry-pick a broadcast tip, merge a sync. A broadcast's
   parent is its three-way base; merging that unrelated branch would lose local
   customizations. Resolve conflicts using project context and preserve edits.
4. Follow the actual payload: re-lock changed manifests (`uv lock`, `go mod tidy`,
   `cargo generate-lockfile` in each crate folder; Maven has no lockfile), give a crate folder
   without a `cargo` Dependabot entry, or a Maven folder without a `maven` one, that entry, and inspect `citrim` for foreign-stack CI jobs. Then run
   `uv run --directory plugins/alemax alemax lint toolchain` and report each `below` line
   with its fix: a v1 `.golangci.yml` fails the delivered lint job until
   `golangci-lint migrate`, and a ruff target below the minimum fails pre-commit on the
   delivered Python; any other version is the project's to raise. Claude settings reconciliation, if requested, still uses
   the upstream Claude floor; it does not configure Codex permissions. Verify
   `AGENTS.md`, `.agents/skills`, and the Codex plugin separately.
5. Run `stale` to inspect Codex discovery entries. Links to the delivered plugin are
   the intended repository surface, not obsolete duplicates. Divergent real skill
   directories need review before replacement. This helper removes nothing and
   does not mark Claude skills or command stubs for deletion.
6. Run the project's checks, commit on its delivery branch, push and open a PR.
   Merge only within existing authorization after required checks pass. Clear
   completed handoff items after verifying the result. Once the merge lands, delete the
   delivery branch and remove the staged worktree: it lives in this repo, and meta never
   removes it. Report missing Codex artifacts as
   a propagation-policy gap; do not fetch unrelated meta files by hand.

## When no human is watching

`context` prints `autonomous=yes` when `alemax agent deliver` started this session; the
runner also appends these rules. Then run the workflow as written, with these changes:
- Never ask. Where a step would ask, stop instead.
- Below the Python floor, exclude first and bump last, before the pick. The delivered
  Python runs under `uv run --script`, so only your linters meet the floor. If they
  already skip the delivered paths (`.agents/`, `plugins/`, `.claude/`, the delivered
  `bin/` files), change nothing. Otherwise exclude those paths in every tool that walks
  the tree (ruff `extend-exclude`, the pre-commit `exclude:`, mypy, pyright, pytest) and
  commit that alone. Raise `requires-python`, `.python-version` and the ruff target, then
  `uv lock`, only when your CI or Makefile runs a delivered script with its own python.
  A failing `uv lock` or check stops the run, naming the package. No `.python-version`
  is a note, not a stop.
- Stop at anything you would have asked about: a substantive conflict, a failing check,
  refs you cannot choose between, or a refused command. Leave the branch and worktree as
  they are and end with
  `uv run --directory plugins/alemax alemax update result needs-operator <the question>`.
- Never edit `.claude/settings*.json`: run `reconcile-settings.py apply --stage` and pass
  the printed `cp` line as `--step "<line>"` to `update result`.
- A file you may not edit (`.pre-commit-config.yaml`): keep git's clean merge, or take
  the delivered copy with git when yours equals the delivery's base. A conflict in it
  stops the run, naming the file; never resolve it with Edit.
- Your linters flag a new top-level folder the delivery added (`.agents/`, `plugins/`):
  exclude it in your linter config; never edit the delivered files.
- Land a clean delivery by PR, never by a push to `main`: push the delivery branch to
  `origin`, `gh pr create --repo <origin's owner/name>`, one
  `gh pr checks <pr> --watch --fail-fast` with a 10-minute timeout, then `gh pr merge`.
  Checks still pending after that, or never started, stop the run as
  `needs-operator: checks pending <names>`; never wait twice. Then step 6's clean-up, and
  end with
  `uv run --directory plugins/alemax alemax update result done <pin> <merge sha> <pr url>`.

When `locate` finds nothing, or the handoff's branch is gone, end with
`uv run --directory plugins/alemax alemax update result nothing-to-apply <why>`. Make
the printed lines your final reply, exactly as printed; the runner reads them.
