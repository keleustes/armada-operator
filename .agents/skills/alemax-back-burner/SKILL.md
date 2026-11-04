---
name: alemax-back-burner
description: "End-of-session wind-down — write `.local/resume.md` (the checkpoint `$alemax-front-burner` reads next time) from git state and the operator's next step in their own words, then report the checkpoint for the next Codex task. `alemax burner down` does the writing; it deletes nothing, commits nothing, and never touches a settings file. Use when the operator says they are stopping, winding down, or wants a checkpoint for next time."
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
     body at templates/claude/skills/back-burner/SKILL.md has moved on, this has not.
     Reconcile the prose; do not re-derive the conversion. -->

## Working directory

Keep the working directory at the repository being operated on; every command below
runs from its root. `alemax` is the packaged CLI under `plugins/alemax/`.
User instructions and existing authorization take precedence over workflow defaults;
ask only for missing decisions or actions outside the authorized scope.

## Wraps

`alemax burner down` (PEP 723, stdlib) — writes `.local/resume.md` in schema 1 (spec
`back-burner-session-wind-down`): frontmatter (`recorded_at`, `branch`, `head_sha`,
`working_tree_clean`), `## Next step`, `## Open questions` (every uncommitted path, today's stashes,
anything passed as `--open`), `## Recent activity`. From the repo root:
`uv run --directory plugins/alemax alemax burner down …`. `up` is the same script's read half, `$alemax-front-burner`'s.

## Steps

1. **Draft the next step** from the session, one or two lines in the operator's words, and let them
   edit it. One question — not a phase per file. Add an `--open "<question>"` for anything they
   want to remember deciding.
2. **The working tree is the operator's call.** `git status --short`; anything worth committing
   before stopping is a normal commit now. Whatever stays uncommitted is recorded by the script as
   an open item — nothing is stashed or committed on their behalf.
3. **Write:** `uv run --directory plugins/alemax alemax burner down --note "<next step>"`
   — `--dry-run` prints the checkpoint instead. The script also counts today's `/tmp/codex-*`
   files and says so; removing them is the operator's, not yours.
4. **Report** the summary line and the path, say the checkpoint is ready and the user can end the Codex task when ready.
   Never close or archive the task automatically.

## Not for

- Session-scoped settings grants — `.claude/settings.local.json` is reconciled against the shipped
  `settings-template.json` floor (`bin/reconcile-settings.py`, spec `settings-template`), not here.
- Committing work — use `git`. Switching projects mid-session — `$alemax-front-burner` from the other clone.
