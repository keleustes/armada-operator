#!/usr/bin/env python3
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""home-volume-check.py — SessionStart hook: is `$HOME` on this project's volume?

Claude Code runs this once when a session starts, resumes or clears (the
`hooks.SessionStart` entry in `.claude/settings-template.json`, folded into
`settings.local.json` by `bin/reconcile-settings.py`). It is wired from the
project's settings, not from `$HOME/.claude/settings.json`, because a wrong
`$HOME` hides exactly that file (claude-meta spec `session-home-volume`).

The rule:
  - the project's volume is `/Volumes/<X>`, from the realpath of
    `$CLAUDE_PROJECT_DIR`, else the hook event's `cwd`;
  - a project that is not under `/Volumes/` is never checked;
  - `$HOME` must lie under the same `/Volumes/<X>/`, the expected home being
    `/Volumes/<X>/Users/<login name>`;
  - a folder that `$HOME`'s presence config claims is a deliberate
    cross-volume session, so it stays silent. An account claims the project
    when its `path` is the project directory or an ancestor of it
    (`$HOME/.config/claude-presence/config.json`, the `--extra` accounts).

On an unclaimed mismatch it prints one JSON object: `systemMessage` for the
operator and `hookSpecificOutput.additionalContext` for the session, both
naming the current `$HOME`, the expected one and the fix (set `HOME` or
`AIML_VOLUME`, relaunch). A missing or malformed presence config claims
nothing, so it still warns.

It never disrupts a session: it always exits 0, writes no file, and any error
it cannot handle ends it silently.

Self-check: `--self-test` runs the decision on built-in cases and prints a
pass/fail line per case.
"""

from __future__ import annotations

import json
import os
import pwd
import sys
from pathlib import Path

VOLUMES = "Volumes"
PRESENCE_CONFIG = Path(".config") / "claude-presence" / "config.json"


def volume_of(path: str) -> str | None:
    """`/Volumes/<X>` for a path under the Volumes mount root, else None."""
    parts = Path(path).parts
    if len(parts) > 2 and parts[0] == os.sep and parts[1] == VOLUMES:
        return os.path.join(os.sep, VOLUMES, parts[2])
    return None


def claimed(project: str, home: str) -> bool:
    """True when `$HOME`'s presence config has an account whose folder contains project."""
    try:
        cfg = json.loads((Path(home) / PRESENCE_CONFIG).read_text())
        accounts = cfg.get("accounts", [])
    except OSError, ValueError, AttributeError:
        return False
    here = Path(project)
    for a in accounts if isinstance(accounts, list) else []:
        raw = a.get("path") if isinstance(a, dict) else None
        if not raw:
            continue
        for root in {Path(raw), Path(os.path.realpath(raw))}:
            if here == root or root in here.parents:
                return True
    return False


def decide(project: str, home: str, user: str) -> str | None:
    """The warning text, or None when `$HOME` is right, the project is off-volume, or claimed."""
    project = os.path.realpath(project)
    home = os.path.realpath(home)
    vol = volume_of(project)
    if vol is None or volume_of(home) == vol:
        return None
    if claimed(project, home):
        return None
    expected = os.path.join(vol, "Users", user)
    return (
        f"home-volume-check: $HOME is {home}, but this project is on {vol}. "
        f"The expected $HOME is {expected}. Per-user state (~/.claude, presence, the "
        f"Keychain link) is being read from the wrong home. Fix: set HOME={expected} "
        f"(or AIML_VOLUME={vol}) and relaunch Claude."
    )


def project_dir(event: dict) -> str | None:
    return os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or None


def login_name() -> str:
    try:
        return pwd.getpwuid(os.getuid()).pw_name
    except KeyError:
        return os.environ.get("USER", "<user>")


def main() -> int:
    try:
        try:
            event = json.loads(sys.stdin.read() or "{}")
        except ValueError:
            event = {}
        if not isinstance(event, dict):
            event = {}
        project = project_dir(event)
        home = os.environ.get("HOME")
        if not project or not home:
            return 0
        msg = decide(project, home, login_name())
        if msg:
            print(
                json.dumps(
                    {
                        "systemMessage": msg,
                        "hookSpecificOutput": {
                            "hookEventName": "SessionStart",
                            "additionalContext": msg,
                        },
                    }
                )
            )
    except Exception:  # the hook must never disrupt a session
        return 0
    return 0


def self_test() -> int:
    v = lambda *p: os.path.join(os.sep, VOLUMES, *p)  # noqa: E731
    cases = [
        (
            "boot-disk $HOME warns",
            v("K8S01", "Users", "u", "repo"),
            os.path.join(os.sep, "Users", "u"),
            True,
        ),
        (
            "matching $HOME is silent",
            v("K8S01", "Users", "u", "repo"),
            v("K8S01", "Users", "u"),
            False,
        ),
        ("other drive warns", v("K8S01", "Users", "u", "repo"), v("IAC01", "Users", "u"), True),
        (
            "off-volume project is silent",
            os.path.join(os.sep, "tmp", "repo"),
            os.path.join(os.sep, "Users", "u"),
            False,
        ),
    ]
    failed = 0
    for name, project, home, warns in cases:
        got = decide(project, home, "u") is not None
        ok = got == warns
        failed += not ok
        print(f"{'pass' if ok else 'FAIL'}  {name}")
    print(f"home-volume-check self-test: {len(cases) - failed}/{len(cases)} pass")
    return 1 if failed else 0


if __name__ == "__main__":
    if sys.argv[1:] == ["--self-test"]:
        raise SystemExit(self_test())
    raise SystemExit(main())
