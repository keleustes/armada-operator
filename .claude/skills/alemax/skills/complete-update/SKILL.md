---
name: complete-update
description: "Project-side completion of a meta delivery — run from the PROJECT's own Claude session. Reads the meta side's `.local/HANDOFF.md`, finds the update branch, says whether to cherry-pick or merge, reports the bootstrap collision, the `ci.yml` jobs belonging to a stack this project does not have, and the paths the delivery says meta no longer ships. This session then does what meta cannot: resolve conflicts with local context, re-lock, reconcile settings, run the tests, push. The project never clones the meta-repo. Consumer half of `/alemax:update-skills`. Use when `.local/HANDOFF.md` names a delivery for this project."
license: MIT
compatibility: Requires git, gh, and `uv`. Runs in the project clone; refuses on a claude-meta clone.
context: project
allowed-tools: Bash(uv run --directory plugins/alemax alemax update *) Bash(uv run --directory plugins/alemax alemax lint toolchain *)
metadata:
  author: alemax
  reviewed_model: claude-5
  reviewed: 2026-11-04
---

## Wraps

`alemax update <subcommand>` — `context`, `handoff`, `locate`, `citrim`, `stale`, each
with `--json`. Run it from the project root as
`uv run --directory plugins/alemax alemax update <subcommand> …`. It reads and reports; every
mutation below is a `git` line this session runs deliberately.

Behaviour — exit codes, what each subcommand decides, why — is in
`openspec/specs/alemax-plugin-package/spec.md` and the module's own docstrings. This body
does not restate it, because the two copies drift and the restatement is what a session
reads first.

## What you are looking at

The delivered branch shares no history with your `main` on purpose. A broadcast branch is
`[base @ your pin] <- [update @ meta current]`: cherry-picking the tip makes its parent the
3-way merge base, so a class-M file you never customised applies cleanly and one you
genuinely edited raises real conflict markers. **A conflict here is a question, not a
failure** — meta cannot know why your copy differs, which is why it opens no PR and
resolves nothing. `.meta-version` is a pointer into the meta repo, not yours.

**Two things a 3-way cannot see, and only you can:** a customization that is an *absence*
(an `exclude:` you added — meta appending below it is luck, not protection), and a path
meta *stopped* shipping (propagation adds, never deletes).

## Steps

1. **Orient.** Run `context`, then `handoff`. `context` refusing means you are in the meta
   clone — stop. A missing handoff is not a stop.
2. **Locate**, and apply with the verb it names — cherry-pick a broadcast, merge a sync.
   Never merge a broadcast: it takes meta's version wholesale and drops your edits. If it
   reports several refs, use the one the handoff names; two refs can have identical trees
   and different pins, so guessing applies a stale pin with no conflict to warn you.
3. **Clear the bootstrap collision first** if `locate` reports one — `git add` and commit
   those paths, never delete them and never force the pick.
4. **Resolve**, keeping your customisation *and* folding in the update. Never auto-resolve
   a substantive conflict; that judgement is the whole reason this runs here. After a
   config-file conflict, re-read the lines *after* the closing marker — git can move a
   shared trailing line outside the markers and silently reattach it to one side.
5. **Finish per the handoff.** Re-lock if a manifest moved (`uv lock` · `go mod tidy` ·
   `cargo generate-lockfile` in each crate folder; a Maven project has no lockfile), and give a
   crate folder with no `cargo` entry, or a Maven folder with no `maven` entry, in
   `.github/dependabot.yml` one (`directory:` that folder) — a delivery can remove an
   ecosystem but never add yours. Then `reconcile-settings check`, then `citrim` and `stale` —
   each prints the lines to run; run them and commit.
   `stale` removes only what the handoff's § Superseded paths names. Then
   `uv run --directory plugins/alemax alemax lint toolchain`: relay each `below` line and its
   fix (spec `toolchain-versions`).
   Raising a version is this project's call, but a v1 `.golangci.yml` fails the delivered CI
   lint job until `golangci-lint migrate` runs, and a ruff target below the minimum fails
   pre-commit on the delivered Python.
6. **Test, push, verify, clean up.** Your own checks, then push and confirm CI — on a
   billing-capped org a red run may never have executed, which is not a code failure.
   Delete the merged branch, remove the staged worktree (it lives in *your* repo), and
   name anything meta must re-broadcast.

## When no human is watching

`context` prints `autonomous=yes` when `alemax agent deliver` started this session (spec
`agent-launcher`; the runner also appends these rules, so an older body still gets them).
Then the steps above run as written, with these changes:
- **Never ask.** Where a step would ask, stop instead.
- **Below the Python floor, exclude first, bump last** (before step 2). The delivered Python
  runs under `uv run --script`, so only your linters meet the floor. If they already skip the
  delivered paths (`.agents/`, `plugins/`, `.claude/`, the delivered `bin/` files), change
  nothing. Otherwise exclude those paths in every tool that walks the tree (ruff
  `extend-exclude`, the pre-commit `exclude:`, mypy, pyright, pytest) and commit that alone.
  Raise `requires-python`, `.python-version` and the ruff target, then `uv lock`, only when
  your CI or Makefile runs a delivered script with its own python. A failing `uv lock` or
  check stops the run, naming the package. No `.python-version` is a note, not a stop.
- **Anything you would have asked about stops the run.** That covers a substantive conflict,
  a failing check, refs you cannot choose between, or a command you are refused. Leave the
  branch and the worktree as they are, and end with
  `uv run --directory plugins/alemax alemax update result needs-operator <the question>`.
- **Never edit `.claude/settings*.json`.** Run `reconcile-settings.py apply --stage` and pass
  the `cp` line it prints as `--step "<line>"` to `update result`.
- **A file you may not edit** (`.pre-commit-config.yaml`): keep git's clean merge, or take
  the delivered copy with git when yours equals the delivery's base. A conflict in it stops
  the run, naming the file; never resolve it with Edit.
- **Your linters flag a new top-level folder** the delivery added (`.agents/`, `plugins/`):
  exclude it in your linter config; never edit the delivered files.
- **A clean delivery lands by PR**, never by a push to `main`: push the delivery branch to
  `origin`, `gh pr create --repo <origin's owner/name>`, then one
  `gh pr checks <pr> --watch --fail-fast` with a 10-minute Bash timeout, then `gh pr merge`.
  Checks still pending after that, or never started, stop the run as
  `needs-operator: checks pending <names>`; never wait twice. Then step 6's clean-up, and end
  with `… alemax update result done <pin> <merge sha> <pr url>`.

When `locate` finds nothing, or the handoff's branch is gone, end with
`… alemax update result nothing-to-apply <why>`. Make the lines it prints your last reply,
exactly as printed: the runner reads them.

## Not for

Running from the meta-repo — refused at step 1. Fetching class-M content from a meta clone
by hand: the payload is in the branch, and a still-missing artifact is a meta-side
re-broadcast.
