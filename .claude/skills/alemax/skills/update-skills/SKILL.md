---
name: update-skills
description: "Use when the operator asks to broadcast skill and template updates to the fleet. Meta-side fleet broadcast of the class-M artifact set — `alemax broadcast` computes the COMPLETE set from `scaffolding/propagation-policy.yaml` (or a `--since {ref}` delta, or explicit `--path`s), says whether the delivery is COMPLETE or PARTIAL — which is what decides whether each project's `.meta-version` advances — and drives `meta/scripts/broadcast-update.sh`. It stages one unresolved `[base @ pin <- update]` branch per active project plus a persistent `../{project}-claude-meta` worktree and a short handoff, and opens NO PR. Meta never merges and never resolves: every delivered project finishes from its own session via `/alemax:complete-update`."
license: MIT
compatibility: Requires bash, git, gh, and `uv`. No yq. Runs from a FORK claude-meta clone on its per-volume branch — the manifest it reads is fork-divergent.
context: claude-meta-only
argument-hint: "[--dry-run] [--since <ref>] [--path <p>]"
allowed-tools: Bash(uv run --directory plugins/alemax alemax broadcast *)
metadata:
  author: alemax
  reviewed_model: claude-5
  reviewed: 2026-11-04
---

## Wraps

`alemax broadcast` — `plan`, `preflight`, `run`. Run it from the repo root as
`uv run --directory plugins/alemax alemax broadcast <subcommand> …`. `--help` documents every flag.

Exit codes, branching and the reasoning behind each rule are in spec `alemax-scaffolding-sync`
and the module's own docstrings. This body carries what a session must decide, and what
to report — restating the code here is how the two drift.

## Steps

1. **`preflight`.** It refuses on canonical, on a dirty tree, and on a `projects.yaml` with no
   active projects — an empty manifest means canonical or a PR branch, so there is no fleet and
   the broadcast would silently do nothing.
2. **`plan --json`, and read COMPLETE vs PARTIAL.** The default is the complete class-M set, and
   it is the only default that includes the class-M **templates** — `ci.yml`, `.gitignore`,
   `.pre-commit-config.yaml`, `dependabot.yml`, `bin/**`, the issue and PR templates. A glob over
   `scaffolding/claude/` omits them, and projects ran dead CI gates for months because of it.
3. **Say which it is, then confirm with AskUserQuestion.** COMPLETE advances every delivered
   project's `.meta-version`, keeping the next merge base fresh; PARTIAL leaves the pin alone and
   the base keeps ageing. Confirmation is non-negotiable — this stages a delivery on every active
   project. Offer `--dry-run` first for a large set.
4. **`run --message "<what changed and why>"`.** Say what the superseded-path manifest carries: a
   delivery can only ADD, so anything meta has stopped shipping is removed project-side or not at
   all.
5. **Report per project** — staged or not, the branch and worktree beside each, and that each
   project's own session must now run `/alemax:complete-update`. The worktree lives in the
   project's repo; it stays until that project reports completion.

## Not for

Applying anything into a project — **Guardrail 4**. Meta stages the pair and writes the handoff;
it does not cherry-pick, resolve a conflict, re-lock deps, run a project's tests, or commit to a
project's `main`, **not even by driving that project's own skill from here**. The delivery is a
3-way merge whose whole point is that a class-M file may have been legitimately customised, and
only that project's session knows why; that is also why no PR is opened here — the review
checkpoint moved to the project. Running from canonical, or from a PR branch with empty
manifests, is refused at preflight rather than producing an empty broadcast.
