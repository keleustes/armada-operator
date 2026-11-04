---
name: lint-toolchain
description: Check this repo's language versions against claude-meta's minimum — every tracked requires-python, .python-version, go.mod, pom.xml and ruff target, every Rust crate's pin and the golangci-lint schema, wherever each sits. Use when asked what Python, Go, Java or Rust level a project is on, after a delivery, or before raising a version.
license: MIT
compatibility: Requires git and `uv`. Runs in a claude-meta clone or any bootstrapped project; the checker ships as class-M `bin/toolchain-check.py`, so a project that predates it is told to run `/alemax:complete-update` rather than failing.
context: either
argument-hint: "[--strict] [--repo <path>]"
allowed-tools: Bash(uv run --directory plugins/alemax alemax lint *)
metadata:
  author: alemax
  version: "1.0"
  reviewed_model: claude-5
  reviewed: 2026-11-03
---

## Wraps

`alemax lint toolchain`, run from the repo root as
`uv run --directory plugins/alemax alemax lint toolchain …`. It runs `bin/toolchain-check.py`
(`scaffolding/templates/bin/` in claude-meta). The minimum, what is read and the finding codes
are in spec `toolchain-versions` and the checker's docstring — not here, because a body that
restates them drifts from them.

## Steps

1. **Just run it.** Nothing to ask first; `--repo` only when the operator names another clone,
   and `/alemax:send-msg` is the way into a repo that has its own session.
2. **Report the level, then the findings.** Every declaration is listed `ok` or `below`, with
   its file and the minimum. Findings (T1–T6) are warnings unless `--strict`; report them
   whether or not the run exits non-zero.
3. **Fix nothing without asking.** Each finding prints its fix, but a version is the project's
   to move: propose the edits, then make the ones the operator picks. Raising
   `requires-python` means `uv lock`; raising a `go` directive means `go mod tidy`.

## Not for

- Documents and skills → `/alemax:lint-docs`, `/alemax:lint-skills`; all three →
  `/alemax:lint-all`.
- Changing claude-meta's minimum → a change to spec `toolchain-versions`, which moves the
  checker's table with it.
