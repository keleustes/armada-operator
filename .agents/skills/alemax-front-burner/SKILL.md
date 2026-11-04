---
name: alemax-front-burner
description: "Pick up where the last session left off — read `.local/resume.md` (written by `$alemax-back-burner`), report the drift since it (branch, HEAD, working tree, stashes; `--check-remote` for origin/main, `--check-openspec` for new changes and open PRs) with a staleness warning, and propose a concrete next step without executing it. `alemax burner up` does the reading; strictly read-only. Use at session start, or when the operator asks \"where was I?\"."
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
     body at templates/claude/skills/front-burner/SKILL.md has moved on, this has not.
     Reconcile the prose; do not re-derive the conversion. -->

## Working directory

Keep the working directory at the repository being operated on; every command below
runs from its root. `alemax` is the packaged CLI under `plugins/alemax/`.
User instructions and existing authorization take precedence over workflow defaults;
ask only for missing decisions or actions outside the authorized scope.

## Wraps

`alemax burner up` — the read half of the pair (spec
`front-burner-session-resume`). No checkpoint → standalone mode from `git merge-base HEAD origin/main`;
a newer schema → best-effort with a warning; no frontmatter → malformed, synthetic snapshot. Its only
side effects are the opt-in `git fetch --no-write-fetch-head origin main` and `gh pr list`.

## Steps

1. **Run:** `uv run --directory plugins/alemax alemax burner up <requested-options>`
   Pass `--check-remote` and `--check-openspec` when the operator wants
   the remote signals; they cost a fetch and an API call.
2. **Read it in the order printed** — staleness and mode caveats first, then the recorded next step,
   the open questions, the drift block, recent activity. A checkpoint over a week old is a candidate
   for discarding, not a plan.
3. **Propose, never execute:** (a) the recorded next step as written, (b) the top drift signal
   (uncommitted work, commits on origin/main, a branch change), (c) something else. Stop after the
   operator picks — they run it in the next turn. No commit, no stash, no checkout, no slash command,
   no write to `.local/resume.md`.

## Not for

- Writing the checkpoint → `$alemax-back-burner`. Discarding it → `rm .local/resume.md` by hand.
- Another repo — current clone only; run it from the other clone's session.
