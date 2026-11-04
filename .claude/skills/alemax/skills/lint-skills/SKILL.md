---
name: lint-skills
description: Audit this repo's skills and command stubs — the thin-skill contract, the Agent Skills name and description limits, provenance, live script paths, a stub that doubles or restates its own skill, and absolute paths written out where a variable belongs. Use when asked whether the skills are still consistent, or after adding one.
license: MIT
compatibility: Requires git and `uv`. Runs in a claude-meta clone or any bootstrapped project; the checkers ship as class-M `bin/**`, so a project that predates them is told to run `/alemax:complete-update` rather than failing.
context: either
argument-hint: "[--strict] [--include-specs] [--repo <path>]"
allowed-tools: Bash(uv run --directory plugins/alemax alemax lint *)
metadata:
  author: alemax
  version: "1.0"
  reviewed_model: claude-5
  reviewed: 2026-10-05
---

## Wraps

`alemax lint` — `all`, `docs`, `skills`, `toolchain`. Run it from the repo root as
`uv run --directory plugins/alemax alemax lint <subcommand> …`. `--help` documents every flag.

Every rule and its reason is in its checker's header (`skill-check.py`, `path-literal-check.py`);
spec `claude-consistency-lint` (in-flight change `alemax-claude-lint`) covers D1, D2 and P1. This
body carries what a session must decide, and what to report — restating the code here is how
the two drift.

## Steps

1. **Just run it.** The runner finds the checkers (`bin/` in a project,
   `scaffolding/templates/bin/` in claude-meta). `--repo` only when the operator names another
   clone — a repo with its own session is reached by `/alemax:send-msg`, never audited from here.
2. **Read the verdict, not the volume.** Every finding is printed; `--strict` is what makes one
   FAIL, and is what to pass before a broadcast.
3. **Report by cause.** Frontmatter: F1 a missing field, F2 missing provenance, F3 outside the
   Agent Skills limits (a `<placeholder>` in a description is an XML tag — write `{placeholder}`).
   Body: B1 a fence doing the script's work, L1 a script path that does not exist, E1 exit codes
   restated. Command stubs, only where `.claude/commands/` exists: S1 a dangling delegation, D1
   one capability listed twice (the fix is a plugin and a deleted stub), D2 a stub paraphrasing
   its skill. P1 is a path that names one machine. The commonest warning is `metadata.reviewed`
   older than the last commit: the body changed after its review — re-review it, then restamp the
   date; `--fix-dates` only fills a missing one.
4. **A P1 is a fix or a stated exception, never a silent one.** Where the literal is deliberate —
   `$HOME` redirected, so the boot-disk path IS the real one — the answer is a line in
   `.claude/path-literal-allow.txt` with a trailing `# <reason>`; the checker refuses an entry
   that has no reason. Where the line is the rule's own example or a test fixture, the answer is
   a same-line `path-literal-ok` / `path-literal-docs`. Ask the operator which; never quieten it.
5. **Fix nothing without asking.** A skill body is somebody's contract.

## When a finding is in doubt

Ask `/skill-craft:reviewing-skills <skill>`: the platform guide *Skill authoring best practices*
as a plugin, installed per volume at user scope from claude-meta's `marketplace/`. It is a
second opinion, never a gate. F3 and the missing-trigger warning are its `frontmatter-name`,
`frontmatter-description` and `description-trigger`, copied here; the 120-line body warning is
this repo's thin contract, stricter than the guide's 500 on purpose. It adds what no regex here
decides — naming, voice, references, scripts, the judgment criteria. If the two disagree on an
overlap, the guide has moved: `skill-check.py`'s header says which side to update. Not
installed → say so, and report this lint's verdict alone.

## Not for

- The documents and the change triad → `/alemax:lint-docs`; all three audits → `/alemax:lint-all`.
- Authoring a new skill → from a meta clone, follow its `ALEMAX-SKILLS.md` section
  "Adding a new `/alemax:*` skill"; `/skill-craft:reviewing-skills` with no target names the
  guide's practices that apply.
- `$HOME/Library/…` inside a skill body — the opposite rule (`system-path-rule`), <!-- system-path-rule-docs -->
  enforced by the meta repository's system-path rule checker. The two agree at the account name.
