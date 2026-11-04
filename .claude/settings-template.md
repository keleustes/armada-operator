# settings-template.json — the floor for this clone's settings.local.json

**What it is.** The tracked floor of Claude Code settings every session of this repo needs:
the allow rules the fleet's sessions actually used, `outputStyle`, and the `hooks` block.
Claude Code never reads this file — it reads the gitignored `.claude/settings.local.json`
(yours) and, if one existed, a tracked `.claude/settings.json`, which this repo never carries:
every session would change it and git would carry every grant (claude-meta spec `settings-template`).

**Reconcile.** `uv run --script bin/reconcile-settings.py check` (exit 1 = floor entries
missing), then `apply`. Floor entries are appended to your local file; nothing local is ever
removed — local-only entries are listed as candidates to promote. Promote one by adding it to
this file in a claude-meta PR, never by tracking `settings.json`. `.claude/` is a protected
path: the harness prompts for the write or routes it to the auto-mode classifier whatever the
allow rules say; a refused `apply` becomes `apply --stage`, which writes
`.local/settings.local.proposed.json` and prints the one `cp` line for the operator.

**Why these entries.** `git`, `gh`, `openspec`, `uv run` (the thin-skill wrapper), `uv
lock`/`uv sync` (the re-lock after an update), `pre-commit run`, and the read-only text tools
are what every studied project session needed; `Edit(.local/**)` and `Read(//tmp/**)` are the
scratch surfaces; `SendMessage`/`ListAgents`/`Agent`/`ToolSearch` are the session tools.
`outputStyle: Concise` is the only documented control that shortens replies (study S17); your
local value wins. No `deny` rows: those live in `~/.claude/settings.json`, and a user-level
deny outranks any project allow. No `Write(path)` rules: Claude Code accepts a `Write`, `NotebookEdit`,
`MultiEdit` or `Glob` path rule but never consults it — only `Edit(path)` and `Read(path)` are checked.

**The hook.** `hooks.PreToolUse` runs `.claude/hooks/scope-guard.py` before every file tool and
Bash call: a session acts only inside this repo (root, `.local/`, worktrees, scratch, toolchains,
`~/.claude`); a sibling's checkout or a data root is refused with the `/alemax:send-msg` address
of its session; a `dev` clone (`.local/env`) never writes prod. `.local/scope-allow.txt` is the
only exception list. It runs as `uv run --quiet --script`, so its `requires-python` holds; reconcile
replaces an older entry for the same hook file rather than keeping both.

**The session-start check.** `hooks.SessionStart` (matcher `startup|resume|clear`) runs
`.claude/hooks/home-volume-check.py` once per session: when the project is on `/Volumes/<X>` and
`$HOME` is not, the operator and the session both get one warning naming the current `$HOME`, the
expected `/Volumes/<X>/Users/<user>` and the fix (set `HOME` or `AIML_VOLUME`, relaunch). A folder
that `$HOME`'s presence config claims, an `--extra` account from another volume, stays silent. It
never blocks a session and writes nothing. It is wired here, not in `~/.claude/settings.json`,
because a wrong `$HOME` hides that file (spec `session-home-volume`).
