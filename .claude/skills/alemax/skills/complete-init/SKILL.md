---
name: complete-init
description: "Project-side completion of a freshly-bootstrapped project — run from the NEW project's own Claude session after `/alemax:new-project` created and pushed it. `alemax init` refuses on the meta-repo, gates on freshness (complete-init finishes a fresh bootstrap; on a long-running clone its writes clobber choices the project now owns), lists every gap the bootstrap left, and applies the two safe ones. This session then does the rest: Keychain secrets, `origin/HEAD`, the settings reconcile, the ci.yml trim, the go-stack post-generate, verification, and the first real change through to a merged PR. Consumer half of `/alemax:new-project`."
license: MIT
compatibility: Requires git, gh, and `uv`. Runs in the project clone; refuses on a claude-meta clone and on a project that is no longer fresh (`--force` overrides).
context: project
argument-hint: "[--dry-run] [--force]"
allowed-tools: Bash(uv run --directory plugins/alemax alemax init *)
metadata:
  author: alemax
  reviewed_model: claude-5
  reviewed: 2026-10-07
---

## Wraps

`alemax init` — `context`, `fix`, `gaps`. Run it from the repo root as
`uv run --directory plugins/alemax alemax init <subcommand> …`. `--help` documents every flag.

Exit codes, branching and the reasoning behind each rule are in spec `project-side-completion`
and the module's own docstrings. This body carries what a session must decide, and what
to report — restating the code here is how the two drift.

## Before step 1

- **Is the CLI there?** If `plugins/alemax/pyproject.toml` is absent, stop: the bootstrap is
  incomplete, and every step below runs that CLI. Tell the operator it is a **meta-side
  bootstrap defect** to fix where `/alemax:new-project` ran — not a delivery, and not
  something this session copies in from a claude-meta clone.
- **Name the operator's step up front.** In auto mode the harness refuses a session writing
  `.claude/settings.local.json` (self-modification). Say at the start that step 3's `cp` line is
  the operator's to run, so it does not surprise them mid-flow. The hook and the settings floor
  are already in the bootstrap commit; there is nothing of theirs to commit.

## Steps

1. **`context`, then `gaps`.** `context` refusing means the meta-repo (use `/alemax:new-project`
   there), no `.meta-version` (retrofitting is meta-side), or a clone past a fresh bootstrap.
   **That last one is the real guard** — these writes are safe only on a fresh clone. Pass
   `--force` only when the operator says they mean it, and say what it will overwrite first.
2. **`fix --gap gitignore-settings`, then `fix --gap python-version`.** In that order:
   `.claude/settings.local.json` holds the operator's grants and must be ignored **before**
   anything writes to it.
3. **Reconcile the settings floor** — `bin/reconcile-settings.py check`, then `apply --stage`,
   which prints the `cp` line to hand the operator (a session writing that file is refused in
   auto mode; plain `apply` is for when it is not). Before the first PR, so step 7's
   `gh pr merge` does not hit a permission wall mid-flow.
4. **Close the advisory gaps** `gaps` listed — `claude-md-fill` with the operator, never by
   inventing what the project is — `git remote set-head origin --auto`,
   `pre-commit install`, the Keychain secrets under the service name `context` reports, and
   mirroring any CI needs with `bin/sync-secrets.py` (names only — values are never printed).
   Delete the `ci.yml` jobs for a stack this repo lacks: runtime gating stops them *running*, not
   Dependabot, which parses the workflow statically and opens bump PRs anyway.
5. **Go stack only:** `make manifests generate`, then guide the rename of the sample API. Domain
   modelling is the operator's — do not invent the resource. **Rust stack:** `bin/rust check`;
   if it warns that cargo is not rustup's proxy, point the operator at the `rust` machine
   profile rather than working around the pin. **Java stack:** `bin/jvm check`, then
   `bin/jvm lint`; if either reports no JDK, or a JDK older than `java/pom.xml`'s release, point the operator at
   the `java` machine profile (`init-machine.sh --profile java`, then `init-user.sh`).
6. **Verify.** Run the project's own tests and report pass or fail without auto-fixing. Propose,
   do not run, `/doctor`, `/test` and `/security`. A blocked run on a billing-capped org is not a
   failure.
7. **First real change, through to merged.** Not before `gaps` no longer lists
   `reconcile-settings` and `.claude/hooks/scope-guard.py` exists — work merged without the
   floor and the hook ran unguarded. The operator decides what the change is. Commit, push, open
   the PR, wait for `gh pr checks --watch` to go green, then merge. **Never `gh pr merge --auto`:**
   a fresh repo has no required checks, so it merges before CI runs. A check that never started
   is a billing-capped pool, not a red build — say so and let the operator decide.
8. **Then drop the nudge** — remove the `CLAUDE.md` bootstrap block, but only once a real change
   has merged. If nothing has landed, leave it: it is supposed to keep prompting.
9. **Summarise** — done, skipped or pending, with the exact command for anything outstanding.

## Not for

The meta-repo, or a repo with no `.meta-version` — both refused at step 1. A long-running clone:
the freshness gate is the point. Removing the nudge before a first change merges. Applying a meta
*delivery* — that is `/alemax:complete-update`.
