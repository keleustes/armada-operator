---
name: alemax-lint-toolchain
description: "Use when asked what Python, Go, Java or Rust level a repository is on, after a delivery, or before raising a version. Lists every tracked language-version declaration against claude-meta's minimum and reports each one below it with its fix; edits nothing."
license: MIT
metadata:
  author: alemax
  version: "1.0"
  source_reviewed_model: claude-5
  source_reviewed: 2026-11-03
---

## Working directory

Keep the working directory at the repository being operated on; every command below
runs from its root. `alemax` is the packaged CLI under `plugins/alemax/`.
User instructions and existing authorization take precedence over workflow defaults;
ask only for missing decisions or actions outside the authorized scope.

## Run

```bash
uv run --directory plugins/alemax alemax lint toolchain
```

It runs `bin/toolchain-check.py` (`scaffolding/templates/bin/` in claude-meta), which
reads every tracked `pyproject.toml`, `ruff.toml`, `.python-version`, inline script header,
`go.mod`, `pom.xml`, Rust crate and `.golangci.yml`, wherever it sits. The minimum and
the finding codes are in spec `toolchain-versions` and the checker's docstring.

## Steps

1. **Just run it.** `--repo <path>` only when the user names another repository.
2. **Report the level, then the findings.** Every declaration is listed `ok` or `below`
   with its file and the minimum. Findings are warnings unless `--strict`; report each
   `below` line and its fix whatever the exit code.
3. **Fix nothing without asking.** The command edits nothing, and a version is the
   project's to move: propose each edit, apply only the ones requested, then re-lock
   (`uv lock`, `go mod tidy`).
