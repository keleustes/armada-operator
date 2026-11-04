#!/usr/bin/env python3
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""data-check.py — verify the data trees a project declares in `data.yaml`.

A claude-meta-managed project keeps code in git under `~/claude-code/<org>/<repo>`
and data OUTSIDE the clone — a Gitea-backed repo under `~/Documents/…`, a NAS mount,
or a plain local tree (spec `data-repo-convention`). The tracked `data.yaml` at the
repo root is the one declaration of those trees; this script checks it, and the
same file is what the environment guard (spec `project-environments`) reads to
refuse a write into a `prod` tree from a `dev` session.

  uv run --script bin/data-check.py                 # every entry
  uv run --script bin/data-check.py --env dev       # entries a dev session uses (env: dev | both)
  uv run --script bin/data-check.py --declared-only # schema + placement only, no filesystem
  uv run --script bin/data-check.py --json          # resolved entries, for another tool
  python3 bin/data-check.py … works too on Python 3.14+ (no uv needed)

Per entry (`- {name, kind, path, remote?, env}`):

  E1  schema — name; kind ∈ gitea|nas|local; env ∈ prod|dev|both; path; remote
      required when kind is gitea; unknown keys are a WARN (forward-compatible)
  E2  path resolves — `~` and `$VAR` / `${VAR}` expand; an unset variable is an
      ERROR ("unset — stop and ask"), never a guessed location
  E3  path exists and is a directory (skipped by --declared-only)
  E4  path is OUTSIDE the code repo — its real path is neither the repo's toplevel
      nor under it (always checked; a data tree inside the clone is the defect
      this file exists to refuse)
  E5  remote host is not a public forge (github.com, gitlab.com, bitbucket.org)
  W1  kind gitea|local but no `.git` at path (a data tree that is not versioned)

Exit 0 every entry passes · 1 any ERROR · 2 data.yaml missing or unparseable.
One line per finding: `ERROR <name>: …`, `WARN <name>: …`, `ok <name>: <path>`.

`data.yaml` is read with a deliberate YAML subset (stdlib only — no PyYAML in a
Go or bash repo): comments, `data:` holding `[]` or a list of flat maps, scalar
values optionally quoted. Anything else is reported as unsupported, with the line.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

KINDS = ("gitea", "nas", "local")
ENVS = ("prod", "dev", "both")
REQUIRED = ("name", "kind", "path", "env")
KNOWN = (*REQUIRED, "remote")
PUBLIC_HOSTS = ("github.com", "gitlab.com", "bitbucket.org")
VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)")
ITEM_INDENT = 2  # `  - name: …`
KEY_INDENT = 4  # `    kind: …`

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_FILE = 2


class ParseError(Exception):
    pass


# --- the YAML subset --------------------------------------------------------


def _strip_comment(line: str) -> str:
    """Drop a trailing ` # …` that is not inside quotes."""
    quote = None
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = None
        elif ch in ("'", '"'):
            quote = ch
        elif ch == "#" and (i == 0 or line[i - 1] in " \t"):
            return line[:i]
    return line


def _scalar(raw: str) -> str | None:
    value = raw.strip()
    if value in ("", "~", "null"):
        return None
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def parse_data_yaml(text: str) -> list[dict[str, str | None]]:
    """Return the `data:` list. Accepts only the documented subset."""
    entries: list[dict[str, str | None]] = []
    in_data = False
    current: dict[str, str | None] | None = None
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = _strip_comment(raw).rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        body = line.strip()
        if indent == 0:
            in_data = False
            current = None
            key, sep, rest = body.partition(":")
            if not sep:
                raise ParseError(f"line {lineno}: expected `key:`, got {body!r}")
            if key.strip() == "data":
                in_data = True
                rest = rest.strip()
                if rest in ("", "[]"):
                    continue
                raise ParseError(
                    f"line {lineno}: `data:` must be `[]` or a list of `- name: …` items"
                )
            # another top-level scalar (`version: 1`) is tolerated and ignored
            continue
        if not in_data:
            raise ParseError(f"line {lineno}: nested content outside `data:`")
        if body.startswith("- "):
            if indent != ITEM_INDENT:
                raise ParseError(
                    f"line {lineno}: list items must be indented {ITEM_INDENT} spaces under `data:`"
                )
            current = {}
            entries.append(current)
            body = body[2:].strip()
            if not body:
                continue
        elif current is None:
            raise ParseError(f"line {lineno}: expected `- ` list item under `data:`")
        elif indent != KEY_INDENT:
            raise ParseError(
                f"line {lineno}: nested collections are not supported "
                f"(entry keys are flat, indented {KEY_INDENT} spaces)"
            )
        key, sep, rest = body.partition(":")
        if not sep or not key.strip() or key.strip().startswith("-"):
            raise ParseError(f"line {lineno}: expected `key: value`, got {body!r}")
        if rest.strip() in ("[", "{") or rest.strip().startswith(("[", "{")):
            raise ParseError(f"line {lineno}: nested collections are not supported")
        current[key.strip()] = _scalar(rest)
    return entries


# --- resolution ---------------------------------------------------------------


def repo_toplevel(start: Path) -> Path:
    try:
        done = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(start),
            check=True,
            capture_output=True,
            text=True,
        )
        return Path(done.stdout.strip()).resolve()
    except OSError, subprocess.CalledProcessError:
        return start.resolve()


def expand(path: str) -> tuple[str, list[str]]:
    """Expand ~ and $VAR; return (expanded, [unset variables])."""
    unset: list[str] = []

    def sub(match: re.Match[str]) -> str:
        name = match.group(1) or match.group(2)
        value = os.environ.get(name)
        if value is None:
            unset.append(name)
            return match.group(0)
        return value

    expanded = VAR_RE.sub(sub, path)
    return os.path.expanduser(expanded), unset


def remote_host(remote: str) -> str:
    """Host of an ssh/https/scp-style git URL, lower-cased ('' when unknown)."""
    match = re.match(r"^[a-z+]+://(?:[^@/]+@)?([^/:]+)", remote)
    if match:
        return match.group(1).lower()
    match = re.match(r"^(?:[^@/]+@)?([^:/]+):", remote)
    if match:
        return match.group(1).lower()
    return ""


def is_inside(path: Path, toplevel: Path) -> bool:
    try:
        path.relative_to(toplevel)
        return True
    except ValueError:
        return False


# --- the check ------------------------------------------------------------------


def check_entries(
    entries: list[dict[str, str | None]],
    toplevel: Path,
    env_filter: str | None,
    declared_only: bool,
) -> tuple[list[str], list[dict[str, object]], bool]:
    lines: list[str] = []
    resolved: list[dict[str, object]] = []
    failed = False
    seen: set[str] = set()

    for index, entry in enumerate(entries, 1):
        name = entry.get("name") or f"<entry {index}>"
        errors: list[str] = []
        warns: list[str] = []

        for key in REQUIRED:
            if not entry.get(key):
                errors.append(f"missing `{key}`")
        for key in entry:
            if key not in KNOWN:
                warns.append(f"unknown key `{key}` (ignored)")
        kind = entry.get("kind")
        env = entry.get("env")
        if kind and kind not in KINDS:
            errors.append(f"kind `{kind}` not in {'|'.join(KINDS)}")
        if env and env not in ENVS:
            errors.append(f"env `{env}` not in {'|'.join(ENVS)}")
        if kind == "gitea" and not entry.get("remote"):
            errors.append("kind gitea needs `remote`")
        if name in seen:
            errors.append("duplicate name")
        seen.add(name)

        if env_filter and env not in (env_filter, "both"):
            continue

        path_str = entry.get("path") or ""
        real: Path | None = None
        if path_str:
            expanded, unset = expand(path_str)
            if unset:
                errors.append(
                    f"path uses unset variable(s) {', '.join(sorted(set(unset)))} — unset means stop and ask"
                )
            else:
                real = Path(expanded).resolve()
                if real == toplevel or is_inside(real, toplevel):
                    errors.append(f"path {real} is inside the code repo {toplevel}")
                if not declared_only:
                    if not real.exists():
                        errors.append(f"path {real} does not exist")
                    elif not real.is_dir():
                        errors.append(f"path {real} is not a directory")
                    elif kind in ("gitea", "local") and not (real / ".git").exists():
                        warns.append(f"no .git at {real} (kind {kind} — data is not versioned)")

        remote = entry.get("remote")
        if remote:
            host = remote_host(remote)
            if host in PUBLIC_HOSTS or any(host.endswith("." + h) for h in PUBLIC_HOSTS):
                errors.append(f"remote host {host} is a public forge — data never goes there")

        for msg in errors:
            lines.append(f"ERROR {name}: {msg}")
        for msg in warns:
            lines.append(f"WARN {name}: {msg}")
        if errors:
            failed = True
        else:
            lines.append(f"ok {name}: {real if real else path_str}")
        resolved.append(
            {
                "name": name,
                "kind": kind,
                "env": env,
                "path": path_str,
                "resolved": str(real) if real else None,
                "remote": remote,
                "ok": not errors,
            }
        )
    return lines, resolved, failed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="data-check.py",
        description="Verify the data trees declared in data.yaml (spec data-repo-convention).",
    )
    parser.add_argument(
        "--file",
        default="data.yaml",
        help="declaration file (default: data.yaml at the repo root / cwd)",
    )
    parser.add_argument(
        "--env",
        choices=ENVS[:2],
        help="check only the entries this environment uses (env: <value> | both)",
    )
    parser.add_argument(
        "--declared-only",
        action="store_true",
        help="schema, placement and remote checks only — do not touch the filesystem",
    )
    parser.add_argument(
        "--json", action="store_true", help="print the resolved entries as JSON (stdout)"
    )
    args = parser.parse_args(argv)

    file = Path(args.file)
    if not file.is_absolute():
        # default: the repo root of the cwd, falling back to the cwd itself
        file = repo_toplevel(Path.cwd()) / file if not file.exists() else file
    if not file.is_file():
        print(f"data-check: {file} not found (no data trees declared?)", file=sys.stderr)
        return EXIT_FILE
    try:
        entries = parse_data_yaml(file.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ParseError) as exc:
        print(f"data-check: {file}: {exc}", file=sys.stderr)
        return EXIT_FILE

    toplevel = repo_toplevel(file.parent)
    lines, resolved, failed = check_entries(entries, toplevel, args.env, args.declared_only)

    if args.json:
        print(
            json.dumps({"file": str(file), "toplevel": str(toplevel), "data": resolved}, indent=2)
        )
    else:
        if not entries:
            print(f"data-check: {file}: no data trees declared")
        for line in lines:
            print(line)
    return EXIT_ERROR if failed else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
