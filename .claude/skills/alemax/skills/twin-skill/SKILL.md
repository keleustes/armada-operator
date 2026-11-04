---
name: twin-skill
description: Use when a plugin gains a skill on one harness, when a Codex or Claude body was edited and the twin may be behind, or as the project's pre-commit gate in place of a render script. Author and check a skill's other-harness twin. `alemax twin draft {SKILL.md}` writes a first draft of the Codex body from a Claude one (or the reverse), converting frontmatter and vocabulary by a printed rule table and never overwriting an existing twin; `alemax twin check --family {name}` reports skills missing a twin, twins that run different programs, foreign vocabulary, dangling script paths and step drift.
license: MIT
compatibility: Requires git and `uv`. Runs in any repo on the plugins pattern — `.claude/skills/<family>/skills/<verb>/` beside `.agents/skills/<family>-<verb>/`. Writes only a draft to a path that does not exist.
context: either
argument-hint: "draft <path/to/SKILL.md> [--to claude|codex] [--force] | check [--family <name>] [--strict] | rules"
allowed-tools: Bash(uv run --directory plugins/alemax alemax twin *)
metadata:
  author: alemax
  reviewed_model: claude-5
  reviewed: 2026-09-11
---

## Wraps

`alemax twin` — `draft`, `check`, `rules`. Run it from the repo root as
`uv run --directory plugins/alemax alemax twin <subcommand> …`. `--help` documents every flag.

Behaviour — what a draft converts and what it leaves for the author, each finding kind and
its exit code — is in spec `skill-twin-authoring` and the module docstrings. This body
carries what a session must decide, and what to report.

## Steps

1. **Draft only when the twin does not exist.** `draft <path>` infers the direction from the
   path; the draft lands at the other harness's conventional path with a `DRAFT twin` comment.
   It refuses over an existing twin — never pass `--force` on a body someone reviewed unless
   the operator says so; the diff is printed first.
2. **Read the rule log and the "still reads as the other harness" lines the draft printed.**
   Those lines are the author's work: rewrite them in the harness's own terms. The draft is a
   starting point, not a rendered file — review it before committing it.
3. **Check:** `uv run --directory plugins/alemax alemax twin check --family <name>` (or no
   `--family` for every family). Report the findings grouped as printed; `intentional` is a
   record, not a defect.
4. **Fix in the source, not the leaf.** A missing twin: draft it. Different programs: make both
   bodies invoke the packaged command. Foreign vocabulary or a dangling script: edit that body.
   Step drift: align the steps, or mark a deliberate difference — `<!-- twin: intentional -->`
   on one step, `<!-- twin: intentional pair — <why> -->` for a pair whose shape differs by design.
5. **Gate it** where the project wants one: `… twin check --strict` in pre-commit or CI exits
   non-zero on any finding. Say that a `render_codex.py --check` it replaces can go.

## Not for

- Meta-versus-shipped consistency of a plugin's leaves → `/alemax:check-leaves` (meta clone only).
- Frontmatter keys and links of a Codex body on its own → `/alemax:lint-skills` (its Codex twin runs `codex_lint.py`).
- Rendering a body from another: nothing here generates a committed file.
