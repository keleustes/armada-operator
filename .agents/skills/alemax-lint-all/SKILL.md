---
name: alemax-lint-all
description: "Use when asking whether the repository is still consistent with itself, or before a broadcast or a release. Audit Codex documents and skills in the current or named repository. Checks discoverability, metadata, local references, and plugin structure; reports findings without editing files."
license: MIT
metadata:
  author: alemax
  version: "1.0"
  source_reviewed_model: claude-5
  source_reviewed: 2026-09-04
---
<!-- The Codex CONVERSION is cloudison/photo-common's, taken verbatim: the
     $-invocations and the host-difference notes are
     hand-written work, not a transform of the Claude body.

     Its CONTENT is from alemax 2.0 (source_reviewed 2026-09-04), so where the Claude
     body at templates/claude/skills/lint-all/SKILL.md has moved on, this has not.
     Reconcile the prose; do not re-derive the conversion. -->

<!-- twin: intentional pair — this body runs codex_lint.py, a Codex-only linter; the Claude twin runs `alemax lint` -->

## Working directory

Keep the working directory at the repository being operated on; every command below
runs from its root. `alemax` is the packaged CLI under `plugins/alemax/`.
User instructions and existing authorization take precedence over workflow defaults;
ask only for missing decisions or actions outside the authorized scope.

## Run

```bash
uv run --script .agents/skills/alemax-lint-all/scripts/codex_lint.py all --strict
```

The bundled runner reads Codex artifacts directly. It checks YAML skill metadata,
duplicate names, discovery links, referenced helpers, and Codex plugin manifests.
The docs pass checks `AGENTS.md`, README, and architecture documentation and their
local Markdown links. It does not apply Claude startup budgets, command-stub
rules, or provider review-model requirements to Codex.

`--repo <path>` selects a user-named repository; otherwise it uses the current git
root. `--list` previews checks without running them. Without `--strict`, findings
are advisory and the exit code is zero; always report the count. The script edits
nothing. Report each finding with its path and proposed correction; apply fixes
only when requested. OpenSpec semantic validation remains `openspec validate`'s
responsibility. This audit is structural, not a claim of complete prose consistency.
