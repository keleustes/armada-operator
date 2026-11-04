---
name: check-leaves
description: Use before a broadcast, after editing a body under `plugins/`, or when a project reports a body meta already fixed. In a claude-meta clone, prove a plugin's meta leaf (`plugins/{name}/meta/.claude`, `.agents`) equals what ships (`scaffolding/.claude/skills/{name}`, `scaffolding/.agents/skills/{name}-*`) file for file — files present on one side only and byte differences — with the differences the plugin declares in `leaves.toml` (the governance preamble, the Codex manifest) reported as expected rather than drift.
license: MIT
compatibility: Requires `uv`. Meta clone only — canonical or a fork; refuses in a project, which has no scaffolding.
context: claude-meta-only
argument-hint: "check [--plugin <name>] [--strict] [--json]"
allowed-tools: Bash(uv run --directory plugins/alemax alemax leaves *)
metadata:
  author: alemax
  reviewed_model: claude-5
  reviewed: 2026-09-11
---

## Wraps

`alemax leaves` — `check`. Run it from the repo root as
`uv run --directory plugins/alemax alemax leaves check [--plugin <name>] [--strict]`.
`--help` documents every flag; spec `plugin-leaf-consistency` carries what `expected` and
`drift` mean and where a plugin declares its expected differences.

## Steps

1. **Run it:** `uv run --directory plugins/alemax alemax leaves check` — every plugin with a
   meta leaf, or `--plugin <name>` for one. Read `drift` first; `expected` is what
   `plugins/<name>/leaves.toml` declares and needs no action.
2. **Fix drift where the report says.** Each `drift` line names the place to edit — the
   plugin's template tree, or the meta leaf for a plugin that has none. Never copy the newer
   side over the other; the edit goes to the source and both leaves follow it.
3. **An expected difference nobody declared** is a `leaves.toml` change in that plugin — a
   `meta_only_blocks` entry for a spliced block, `meta_only_paths` / `project_only_paths` for
   a file — with one line saying why. Say so in the report rather than adding it silently.
4. **Report** the count line and the drift, grouped as printed. `--strict` exits non-zero on
   drift only; `meta/scripts/alemax-check.sh` runs it that way.

## Not for

- Whether the two harnesses' bodies of one skill agree → `/alemax:twin-skill`.
- Whether a leaf matches its templates → `build.py check` (run by `meta/scripts/alemax-check.sh`).
- Anything in a project clone: this verb refuses there by design.
