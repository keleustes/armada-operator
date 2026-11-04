---
name: alemax-update-skills
description: "Use when the user asks to broadcast skill and template updates to the fleet. Stage upstream class-M deliveries to active projects from a claude-meta fork. Report complete versus partial payloads and Codex coverage; receiving projects apply their own deliveries."
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
     body at templates/claude/skills/update-skills/SKILL.md has moved on, this has not.
     Reconcile the prose; do not re-derive the conversion. -->

## Working directory

Keep the working directory at the repository being operated on; every command below
runs from its root. `alemax` is the packaged CLI under `plugins/alemax/`.
User instructions and existing authorization take precedence over workflow defaults;
ask only for missing decisions or actions outside the authorized scope.

## Wraps

`alemax broadcast` — `preflight`, `plan`, `run --message "<msg>"`, each with
`--json`. Run from the meta-repo root as
`uv run --directory plugins/alemax alemax broadcast <subcommand>`. It resolves the path set and hands it to
`meta/scripts/broadcast-update.sh`, which owns the staging.

The script sources the propagation libs under **bash**, never the caller's shell: in zsh
`prop_complete_class_m_set` under-reports the set — a handful of paths where bash finds ~70 — so a
PARTIAL delivery would be reported COMPLETE and the pin stamped on projects that never got the
files. Do not re-implement that lookup in the body.

## Steps

1. **Preflight.**

   ```
   uv run --directory plugins/alemax alemax broadcast preflight
   ```

   Exit 1 lists each blocker: not a claude-meta clone, origin is canonical, a dirty tree, or a
   `projects.yaml` with no active projects — an empty manifest means canonical or a PR branch, so
   there is no fleet and the broadcast would silently do nothing.
2. **Plan, and read COMPLETE vs PARTIAL.**

   ```
   uv run --directory plugins/alemax alemax broadcast plan --json
   ```

   Default is the complete class-M set, which is the only default that includes the class-M
   *templates* (`ci.yml`, `.gitignore`, `.pre-commit-config.yaml`, `dependabot.yml`, `bin/**`, the
   issue and PR templates). A glob over `scaffolding/claude/` omits them, and projects ran dead CI
   gates for months because of it. `--since <ref>` narrows to changed `.claude` artifacts;
   `--path <p>` adds one explicitly; the two combine.
3. **Say which it is, then confirm the concrete plan with the user.** COMPLETE advances every delivered
   project's `.meta-version`, which keeps the next broadcast's merge base fresh; PARTIAL leaves
   the pin alone and the base keeps ageing. Confirmation is non-negotiable — this stages a
   delivery on every active project. Offer `--dry-run` first for a large set.
4. **Run.**

   ```
   uv run --directory plugins/alemax alemax broadcast run --message "<what changed and why>" --dry-run
   ```

   Drop `--dry-run` to stage for real. `broadcast-update.sh` refuses class-P and
   placeholder-bearing paths itself, so a stray path fails fast rather than shipping garbage.
5. **Report per project** — which were staged, the branch and worktree left beside each, and that
   each project's own session must now run `$alemax-complete-update`. Leave every
   `../<project>-claude-meta` worktree in place until that project reports completion.

## Not for

Applying anything into a project — **Guardrail 4**. Meta stages the pair and writes the handoff;
it does not cherry-pick, resolve a conflict, re-lock deps, run a project's tests, or commit to a
project's `main`, **not even by driving that project's own skill from here**. The delivery is a
3-way merge whose whole point is that a class-M file may have been legitimately customised, and
only that project's session knows why; that is also why no PR is opened here — the review
checkpoint moved to the project. Running from canonical, or from a PR branch with empty
manifests, is refused at preflight rather than producing an empty broadcast.

## Codex payload boundary

The upstream propagation policy decides what is shipped. Inspect `plan` for
`AGENTS.md`, `.agents/skills/`, and the full `plugins/alemax/` tree; a COMPLETE
upstream delivery can still be Claude-only. Report missing Codex coverage before
staging. Do not relabel Claude paths or advance a pin to imply Codex delivery.
Updating the meta-repo propagation policy requires work in that repo.
