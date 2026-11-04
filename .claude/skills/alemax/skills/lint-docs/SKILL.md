---
name: lint-docs
description: Audit this repo's documents — the three-doc set (CLAUDE.md · README.md · architecture.md), the startup context budget, and intent · spec · plan on every in-flight change. Use when asked whether the docs are still consistent, before a broadcast, or after editing CLAUDE.md.
license: MIT
compatibility: Requires git and `uv`. Runs in a claude-meta clone or any bootstrapped project; the checkers ship as class-M `bin/**`, so a project that predates them is told to run `/alemax:complete-update` rather than failing.
context: either
argument-hint: "[--strict] [--repo <path>]"
allowed-tools: Bash(uv run --directory plugins/alemax alemax lint *)
metadata:
  author: alemax
  version: "1.0"
  reviewed_model: claude-5
  reviewed: 2026-11-04
---

## Wraps

`alemax lint` — `all`, `docs`, `skills`, `toolchain`. Run it from the repo root as
`uv run --directory plugins/alemax alemax lint <subcommand> …`. `--help` documents every flag.

Exit codes, branching and the reasoning behind each rule are in spec `claude-consistency-lint`
and the module's own docstrings. This body carries what a session must decide, and what
to report — restating the code here is how the two drift.

## Steps

1. **Just run it.** The runner finds the checkers (`bin/` in a project,
   `scaffolding/templates/bin/` in claude-meta) and decides the CLAUDE.md budget itself —
   200 lines in canonical, 120 in a project. There is nothing to ask first; `--repo` only when
   the operator names another clone, and `/alemax:send-msg` is the way into a repo that has its
   own session.
2. **Read the verdict, not the volume.** The summary block names each checker and its counts.
   Every finding is printed; `--strict` is what makes one FAIL. Without it a clean repo passes
   and the counts still say what was found — report the warnings, not only the exit status.
3. **Report by cause, in the operator's terms** — which document, which rule, and the one-line
   fix each checker already printed. Refusals are R1/R2 (placement, the routing paragraph),
   R1/R2 (a fence or a fat `@import` in the startup set) and C1/C2/C3 (a change missing its
   intent, its plan, or a spec delta with no `skip_specs: true`).
4. **Fix nothing without asking.** Every finding is somebody's document; a budget overrun is a
   relocation decision, not a deletion. Propose, then edit what the operator picks.

## Not for

- Skills, command stubs and resolved absolute paths → `/alemax:lint-skills`; all three audits →
  `/alemax:lint-all`.
- OpenSpec's own delta and scenario rules → `openspec validate --strict`, which owns them and
  says it better. C3 warns only so the triad is reported in one place.
