---
name: alemax-new-project
description: "Use when the user asks to start or bootstrap a new project. Bootstrap a private project through the upstream claude-meta fork workflow. Validate arguments and collisions, show the concrete effects, then hand completion to the new project’s session."
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
     body at templates/claude/skills/new-project/SKILL.md has moved on, this has not.
     Reconcile the prose; do not re-derive the conversion. -->

<!-- twin: intentional pair — one extra hand-off step the Claude twin folds into its last -->

## Working directory

Keep the working directory at the repository being operated on; every command below
runs from its root. `alemax` is the packaged CLI under `plugins/alemax/`.
User instructions and existing authorization take precedence over workflow defaults;
ask only for missing decisions or actions outside the authorized scope.

## Wraps

`alemax newproj` — `preflight`, `validate`, `plan`, `run`, each with
`--json`. Run from the meta-repo root as
`uv run --directory plugins/alemax alemax newproj <subcommand> --name … --stack … --ghhandle … --description "…"`. `run` invokes `meta/bootstrap/init-project.sh`, which owns
the bootstrap itself.

## Steps

1. **Gather only what cannot be inferred** — `name` (kebab-case lowercase), `stack`
   (`python` · `bash` · `go` · `xcode` · `rust` · `java`; repeat `--stack` to combine, e.g. `go` + `rust`), `ghhandle` (the GitHub org or user that will own it), and a
   one-line `description`. Ask for these in one pass; do not quiz the operator on anything the
   cwd, the manifests or the conversation already answer.
2. **Preflight.**

   ```
   uv run --directory plugins/alemax alemax newproj preflight
   ```

   Exit 1 names each blocker: not a claude-meta clone, origin is canonical (the row belongs on
   your fork, so canonical is the wrong clone), a dirty tree, or `gh` missing or unauthenticated.
3. **Validate, and read the collisions as real answers.**

   ```
   uv run --directory plugins/alemax alemax newproj validate --name <n> --stack <s> --ghhandle <h> --description "<d>"
   ```

   A `projects.yaml` hit means the project already exists — the operator probably wants
   `$alemax-complete-init` or nothing at all. A `repos.yaml` hit under a *different* handle means
   the name is taken elsewhere in their universe; confirm the handle before continuing. An
   existing destination directory is never something to delete — stop and ask.
4. **Plan, then confirm the concrete plan with the user.**

   ```
   uv run --directory plugins/alemax alemax newproj plan --name <n> --stack <s> --ghhandle <h> --description "<d>"
   ```

   Show every effect it lists — a **private** GitHub repo is created, a clone lands on disk, and
   `projects.yaml` is committed on this fork's per-volume branch. Nothing runs without an explicit
   yes; a repo created by mistake has to be deleted by hand.
5. **Run.**

   ```
   uv run --directory plugins/alemax alemax newproj run --name <n> --stack <s> --ghhandle <h> --description "<d>" --no-obsidian
   ```

   `--drive NN` or `--volume PATH` targets another drive; `--no-obsidian` and `--no-launcher`
   suppress the two interactive extras. Add them when stdin is not a terminal.
6. **Hand off.** Report the clone path and the repo URL, and say plainly that the next step runs
   **in the new project's own session**: `$alemax-complete-init`. Do not run it from here.

## Not for

Canonical — `init-project.sh` appends to the fork-divergent `projects.yaml`, and canonical's is
empty by design. Retrofitting a repo that already exists (`retrofit-*` covers that). Finishing the
new project from this session: Keychain secrets, the first change and the settings reconcile all
belong to that project's own session (Guardrail 4).

## Codex handoff

The upstream bootstrap controls the emitted files. Verify that the new clone has
`AGENTS.md` and `.agents/skills` before claiming it is ready for Codex. If it only
emits Claude artifacts, identify the missing conversion in the handoff. Claude
settings reconciliation does not grant Codex permission to merge or write files.
