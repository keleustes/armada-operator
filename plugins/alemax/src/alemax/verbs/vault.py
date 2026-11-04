"""ideas.py — the deterministic half of /alemax:import-ideas.

Walks the operator's Obsidian vault for `ideas-on-the-go(-<project>)?.md`,
routes each file by its filename, and lists the rows still pending. The
filename decides the route; the operator decides every row.

Subcommands
  vault      resolve and report the vault folder and where the path came from.
             Exit 0 found, 1 missing.
  scan       every matching file, its route, its pending rows and their line
             numbers, plus freshness and duplicate-target warnings.
             `--only <project>` restricts to that project's file (the escape
             that lets a project clone drain its own capture file).
             Exit 0 rows found, 3 none.
  annotate   rewrite one row as collected, atomically (tempfile + rename —
             iCloud Drive does not reliably take an in-place write).
             Exit 0 written, 1 refused.

Path note: the vault default is literal `/Users/<u>/Library/Mobile Documents/…`
per the system-path-rule. Under HOME-redirect `$HOME` is the SSD, but iCloud is
a macOS service rooted on the boot disk — a `~` here silently mis-routes.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from datetime import date, datetime
from pathlib import Path

from .. import git as gitmod
from ..io import die
from ..repo import require_meta

FILE_RE = re.compile(r"^ideas-on-the-go(?:-(?P<project>.+))?\.md$")
PENDING_RE = re.compile(r"^(?P<indent>\s*)- \[ \] (?P<text>.*)$")
USER_RE = re.compile(r"^  - username: (?P<name>\S+)\s*$")
FIELD_RE = re.compile(r"^    (?P<key>[a-z_]+): (?P<val>.*?)\s*$")
NAME_RE = re.compile(r"^  - name: (?P<name>\S+)\s*$")
DEFAULT_VAULT = "/Users/{user}/Library/Mobile Documents/iCloud~md~obsidian/Documents/AlemaxIdeas"
STALE_DAYS = 3


def repo_root() -> Path:
    top = gitmod.probe(Path.cwd(), "rev-parse", "--show-toplevel")
    if not top:
        die("not a git repository")
    return Path(top)


def scalar_list(path: Path, head: re.Pattern[str]) -> list[dict]:
    """The YAML subset users.yaml and projects.yaml actually use."""
    out, cur = [], None
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if m := head.match(line):
            if cur:
                out.append(cur)
            cur = {"name": m["name"]}
        elif cur and (m := FIELD_RE.match(line)):
            cur[m["key"]] = m["val"].strip('"')
    if cur:
        out.append(cur)
    return out


def resolve_vault(root: Path) -> dict:
    user = os.environ.get("USER") or Path.home().name
    row = next((u for u in scalar_list(root / "users.yaml", USER_RE) if u["name"] == user), {})
    vault, source, warning = (
        row.get("ideas_on_the_go_vault", ""),
        "users.yaml ideas_on_the_go_vault",
        None,
    )
    if not vault and (legacy := row.get("ideas_on_the_go_path", "")):
        vault, source = legacy, "users.yaml ideas_on_the_go_path (legacy)"
        warning = (
            "users.yaml uses the legacy field 'ideas_on_the_go_path'; rename it to "
            "'ideas_on_the_go_vault' (folder semantics) — spec mobile-capture"
        )
        if Path(vault).is_file():
            vault = str(Path(vault).parent)
    if not vault:
        vault, source = (
            DEFAULT_VAULT.format(user=user),
            "default (obsidian-as-canonical-markdown-surface)",
        )
    vault = vault.rstrip("/")
    return {"vault": vault, "source": source, "warning": warning, "exists": Path(vault).is_dir()}


def route_for(project: str | None, known: set[str]) -> str:
    if not project or project == "claude-meta":
        return "cross-cutting"
    return f"existing-project:{project}" if project in known else f"unknown:{project}"


def pending_rows(path: Path) -> list[dict]:
    rows = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if m := PENDING_RE.match(line):
            rows.append({"line": n, "text": m["text"]})
    return rows


def cmd_vault(a) -> int:
    info = resolve_vault(repo_root())
    if a.json:
        print(json.dumps(info, indent=2))
        return 0 if info["exists"] else 1
    if info["warning"]:
        print(f"warn: {info['warning']}")
    print(f"vault: {info['vault']}  (source: {info['source']})")
    if not info["exists"]:
        print("  not found. Create it in Obsidian (Settings → Files → Vault location) on iPhone")
        print("  or Mac; the folder appears in iCloud Drive once Obsidian writes to it.")
        print("  Override with users.yaml ideas_on_the_go_vault.")
        return 1
    return 0


def cmd_scan(a) -> int:
    root = repo_root()
    # A full scan reads projects.yaml and routes to several repos: claude-meta only.
    # `--only <project>` is the documented consumer exception (drain one project's file).
    # Found by Codex in the app01 clone (2026-09-10): the body stated the rule, nothing enforced it.
    if not a.only:
        require_meta(root)
    info = resolve_vault(root)
    if not info["exists"]:
        die(f"vault folder not found at {info['vault']} — run `vault` for the setup hint")
    known = {
        p["name"]
        for p in scalar_list(root / "projects.yaml", NAME_RE)
        if p.get("status") == "active"
    }

    files, warnings, seen = [], [], {}
    if info["warning"]:
        warnings.append(info["warning"])
    for path in sorted(Path(info["vault"]).glob("ideas-on-the-go*.md")):
        m = FILE_RE.match(path.name)
        if not m:
            continue
        project = m["project"]
        if a.only and project != a.only:
            continue
        route = route_for(project, known)
        target = project or "claude-meta"
        if target in seen:
            warnings.append(
                f"vault has two files routing to '{target}': {seen[target]} and {path.name} — consolidate"
            )
        else:
            seen[target] = path.name
        age = (datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)).days
        rows = pending_rows(path)
        if rows:
            files.append(
                {
                    "file": str(path),
                    "name": path.name,
                    "project": project,
                    "route": route,
                    "pending": rows,
                    "age_days": age,
                    "stale": age > STALE_DAYS,
                }
            )
    if a.only and not files:
        warnings.append(f"no vault file for --only {a.only} (expected ideas-on-the-go-{a.only}.md)")

    payload = {
        "vault": info["vault"],
        "files": files,
        "warnings": warnings,
        "date": str(date.today()),
    }
    total = sum(len(f["pending"]) for f in files)
    if a.json:
        print(json.dumps(payload, indent=2))
    else:
        for w in warnings:
            print(f"warn: {w}")
        for f in files:
            stale = f"  (last synced {f['age_days']}d ago — check iCloud)" if f["stale"] else ""
            print(f"{f['name']}  → {f['route']}{stale}")
            for r in f["pending"]:
                print(f"    {r['line']:>4}: {r['text'][:88]}")
        print(f"-- {total} pending row(s) in {len(files)} file(s)")
    return 0 if total else 3


def cmd_annotate(a) -> int:
    path = Path(a.file)
    if not path.is_file():
        die(f"{path} not found")
    lines = path.read_text(encoding="utf-8").splitlines()
    if not 1 <= a.line <= len(lines):
        die(f"line {a.line} out of range for {path.name}")
    m = PENDING_RE.match(lines[a.line - 1])
    if not m:
        die(f"{path.name}:{a.line} is not a pending `- [ ]` row — refusing to rewrite it")
    lines[a.line - 1] = (
        f"{m['indent']}- [x] ({date.today()} → {a.summary} via {path.name}) {m['text']}"
    )
    # Atomic: iCloud Drive does not reliably take an in-place write.
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    os.replace(tmp, path)
    print(f"annotated {path.name}:{a.line} → {a.summary}")
    return 0


def register(ap: argparse.ArgumentParser) -> None:
    sub = ap.add_subparsers(dest="subcommand", required=True)
    sub.add_parser("vault", help="resolve and report the vault folder")
    s = sub.add_parser("scan", help="matching files, routes and pending rows")
    s.add_argument("--only", metavar="PROJECT", help="restrict to ideas-on-the-go-<project>.md")
    n = sub.add_parser("annotate", help="mark one row collected, atomically")
    n.add_argument("--file", required=True)
    n.add_argument("--line", required=True, type=int)
    n.add_argument(
        "--summary",
        required=True,
        help='e.g. "cross-cutting, PR #271" · "skipped: personal" · "failed: <reason>"',
    )
    # --json belongs on each subcommand, so `<cmd> --json` works (the natural form).
    for sp in sub.choices.values():
        sp.add_argument("--json", action="store_true", help="machine-readable output")

    # Dispatch lives on the subparser, not in a trailing lookup: an unknown
    # subcommand is then argparse's error, with the valid choices, not a KeyError.
    _dispatch = {
        "vault": cmd_vault,
        "scan": cmd_scan,
        "annotate": cmd_annotate,
    }
    for _name, _sp in sub.choices.items():
        _sp.set_defaults(func=_dispatch[_name])
