---
name: alemax-check-leaves
description: "In a claude-meta clone, prove a plugin's meta leaf (`plugins/{name}/meta/.claude`, `.agents`) equals what ships (`scaffolding/.claude/skills/{name}`, `scaffolding/.agents/skills/{name}-*`) file for file — files present on one side only and byte differences — with the differences the plugin declares in `leaves.toml` reported as expected rather than drift. Meta clone only; refuses in a project. Use before a broadcast, after editing a body under `plugins/`, or when a project reports a body meta already fixed."
license: MIT
metadata:
  author: alemax
  version: "2.1"
  reviewed_model: claude-5
  reviewed: 2026-09-11
---
<!-- AUTHORED for Codex, 2026-09-11, beside the Claude body at
     templates/claude/skills/check-leaves/SKILL.md. Same verb, same command; the prose is
     this harness's. This skill is legal only in a claude-meta clone. -->

## Working directory

Keep the working directory at the repository being operated on; every command below
runs from its root. `alemax` is the packaged CLI under `plugins/alemax/`.
User instructions and existing authorization take precedence over workflow defaults;
ask only for missing decisions or actions outside the authorized scope.

## Wraps

`alemax leaves` — `check`. From the repo root:
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

- Whether the two harnesses' bodies of one skill agree → `$alemax-twin-skill`.
- Whether a leaf matches its templates → `build.py check` (run by `meta/scripts/alemax-check.sh`).
- Anything in a project clone: this verb refuses there by design.
