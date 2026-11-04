---
name: alemax-complete-init
description: "Use in a freshly bootstrapped project's own Codex session, after `$alemax-new-project` created and pushed it. Complete a fresh claude-meta project bootstrap from Codex: inspect gaps, finish applicable setup, verify Codex discovery, and carry the user’s first change through the project’s PR workflow."
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
     body at templates/claude/skills/complete-init/SKILL.md has moved on, this has not.
     Reconcile the prose; do not re-derive the conversion. -->

<!-- twin: intentional pair — a condensed port: six steps where the Claude twin walks nine; same verb, same gates -->

## Working directory

Keep the working directory at the repository being operated on; every command below
runs from its root. `alemax` is the packaged CLI under `plugins/alemax/`.
User instructions and existing authorization take precedence over workflow defaults;
ask only for missing decisions or actions outside the authorized scope.

## Workflow

This completes an upstream claude-meta bootstrap from the project's own Codex
session. If `plugins/alemax/pyproject.toml` is absent, stop before the first
command: the bootstrap is incomplete, a meta-side defect to fix where it ran,
not something to copy in from a claude-meta clone. The upstream scaffold can contain both agent surfaces. The helper's
Claude settings findings describe real Claude files, not Codex permissions.

```bash
uv run --directory plugins/alemax alemax init context
uv run --directory plugins/alemax alemax init gaps --json
```

1. Respect the context and freshness checks. `.meta-version` names a meta-repo
   commit, not a commit in this project. Use `--force` only for an explicitly
   requested fresh-bootstrap override, after describing the affected files.
2. Fix a missing `.python-version` with `fix --gap python-version`. If Claude
   files are present and maintained, apply `fix --gap gitignore-settings` before
   reconciling their local grants. Skip that gap in a Codex-only project.
3. Read `AGENTS.md` and check `.agents/skills` discovery. Missing Codex instructions
   require an actual conversion; copying Claude JSON permissions does not supply
   them. Preserve Codex approval and sandbox settings. Run
   `bin/reconcile-settings.py` only when the user requests maintaining the Claude
   settings floor as part of the bootstrap; report it separately.
4. Address applicable gaps: set `origin/HEAD`, install pre-commit, trim CI jobs for
   absent stacks, and set the specified Keychain/CI secrets without printing values.
   On Go projects generate manifests once the required tooling is installed. On Rust
   projects run `bin/rust check`; a warning that cargo is not rustup's proxy means the
   machine needs the `rust` profile, not a workaround. On Java projects run `bin/jvm check`
   and `bin/jvm lint`; a missing JDK, or one older than `java/pom.xml`'s release, means the machine needs
   the `java` profile.
5. Run the project's tests and report failures. For the user's first real change,
   use `$openspec-propose` when warranted and land work through the project's PR
   process. Do not invent a feature merely to exercise the pipeline. Merge only
   when authorized, after `gh pr checks --watch` is green — never `gh pr merge
   --auto`: a fresh repo has no required checks, so it merges before CI runs.
6. Remove a bootstrap nudge from the appropriate instruction document only after
   a real change has merged. Report each completed or pending gap and its command.
