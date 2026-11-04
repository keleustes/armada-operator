---
name: new-project
description: "Use when the operator asks to start or bootstrap a new project. Bootstrap a new project in the operator's fork-managed claude-meta workflow — `alemax newproj` validates the four required arguments and the three collisions (`projects.yaml`, `repos.yaml`, the destination directory), states the exact side effects, then runs `meta/bootstrap/init-project.sh`. Producer half of `/alemax:complete-init`: this creates a private GitHub repo, the local clone, the scaffolded stack and the manifest row; the new project's own session finishes it."
license: MIT
compatibility: Requires bash, git, an authenticated gh, and `uv`. Runs from a FORK claude-meta clone — the manifest row lands on your fork, not canonical.
context: claude-meta-only
argument-hint: "<name> <stack> <ghhandle> <description>"
allowed-tools: Bash(uv run --directory plugins/alemax alemax newproj *)
metadata:
  author: alemax
  reviewed_model: claude-5
  reviewed: 2026-11-04
---

## Wraps

`alemax newproj` — `plan`, `preflight`, `run`, `validate`. Run it from the repo root as
`uv run --directory plugins/alemax alemax newproj <subcommand> …`. `--help` documents every flag.

Exit codes, branching and the reasoning behind each rule are in spec `alemax-skills`
and the module's own docstrings. This body carries what a session must decide, and what
to report — restating the code here is how the two drift.

## Steps

1. **Gather only what cannot be inferred** — `name` (kebab-case), `stack` (repeatable, e.g.
   `go` + `rust`, `python` + `java`), `ghhandle`, and a one-line `description`, in one pass. Do not quiz the
   operator on anything the cwd, the manifests or the conversation already answer.
2. **`preflight`, then `validate`.** Read the collisions as real answers, not as errors to retry
   past: a `projects.yaml` hit means the project already exists — the operator probably wants
   `/alemax:complete-init`, or nothing. A `repos.yaml` hit under a *different* handle means the
   name is taken elsewhere in their universe; confirm the handle. **An existing destination
   directory is never something to delete** — stop and ask.
3. **`plan`, then confirm with AskUserQuestion.** Show every effect it lists: a **private** GitHub
   repo is created, a clone lands on disk, and `projects.yaml` is committed on this fork's
   per-volume branch. Nothing runs without an explicit yes — a repo created by mistake has to be
   deleted by hand.
4. **`run`.** `--drive NN` or `--volume PATH` targets another drive; add `--no-obsidian` and
   `--no-launcher` when stdin is not a terminal.
5. **Hand off.** Report the clone path and the repo URL, and say plainly that the next step runs
   **in the new project's own session** — `/alemax:complete-init`. Do not run it from here.

## Not for

Canonical — `init-project.sh` appends to the fork-divergent `projects.yaml`, and canonical's is
empty by design. Retrofitting a repo that already exists (`retrofit-*` covers that). Finishing the
new project from this session: Keychain secrets, the first change and the settings reconcile all
belong to that project's own session (Guardrail 4).
