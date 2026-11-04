"""`alemax feedback` — capture one finding as a row in this repo's `.local/feedback.md`.

The row shape is what `alemax collect scan` parses: an H3 heading and bold fields.
Nothing else is written, and nothing is ever committed.
"""

from __future__ import annotations

import argparse
import re
from datetime import datetime
from pathlib import Path

from .. import git
from ..io import OK, die, emit
from ..repo import toplevel
from ..scratch import append_block, local_dir, one_line

KINDS = ("blocker", "friction", "idea", "harness")
ROW_RE = re.compile(r"^### (?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}) — (?P<kind>[a-z]+)(?P<rest>.*)$")
FEEDBACK = "feedback.md"


def root_for(a: argparse.Namespace) -> Path:
    return Path(a.root).resolve() if a.root else toplevel()


def default_context(root: Path) -> str:
    """Branch and HEAD subject — what the operator was doing, without asking them."""
    branch = (
        git.probe(root, "symbolic-ref", "--short", "HEAD")
        or git.probe(root, "rev-parse", "--short", "HEAD")
        or "?"
    )
    subject = git.probe(root, "log", "-1", "--format=%s") or ""
    return f"on {branch} — {subject}" if subject else f"on {branch}"


def cmd_add(a: argparse.Namespace) -> int:
    root = root_for(a)
    finding = one_line(a.finding)
    if not finding:
        die("empty finding", 2)
    path = local_dir(root, write=True) / FEEDBACK
    row = [
        f"### {datetime.now().strftime('%Y-%m-%d %H:%M')} — {a.kind}",
        "",
        f"**Context:** {one_line(a.context) if a.context else default_context(root)}",
        f"**Finding:** {finding}",
    ]
    if a.diagnosis:
        row.append(f"**Related diagnosis:** {a.diagnosis}")
    append_block(path, "\n".join(row))
    print("\n".join(row))
    print(f"→ {path.relative_to(root)}")
    return OK


def rows(path: Path) -> list[dict]:
    """Every row in the file, with its finding line and whether it was collected."""
    out: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if m := ROW_RE.match(line):
            out.append(
                {
                    "ts": m["ts"],
                    "kind": m["kind"],
                    "collected": "(collected " in m["rest"],
                    "finding": "",
                }
            )
        elif out and line.startswith("**Finding:**"):
            out[-1]["finding"] = line[len("**Finding:**") :].strip()
    return out


def cmd_list(a: argparse.Namespace) -> int:
    root = root_for(a)
    path = local_dir(root) / FEEDBACK
    if not path.exists():
        emit({"rows": []}, as_json=a.json, plain=f"no {path.relative_to(root)} yet")
        return OK
    shown = [
        r
        for r in rows(path)
        if (a.all or not r["collected"]) and (not a.kind or r["kind"] == a.kind)
    ]
    if a.json:
        emit({"rows": shown}, as_json=True)
        return OK
    for r in shown:
        mark = " [collected]" if r["collected"] else ""
        print(f"{r['ts']}  {r['kind']:<8} {r['finding']}{mark}")
    if not shown:
        tail = "" if a.all else " pending collection (pass --all to include collected ones)"
        print(f"no rows{tail}")
    return OK


SUBCOMMANDS = {
    "add": (cmd_add, "append one row to .local/feedback.md"),
    "list": (cmd_list, "print the rows"),
}


def register(ap: argparse.ArgumentParser) -> None:
    ap.add_argument("--root", help="repo toplevel (default: git rev-parse --show-toplevel)")
    subs = ap.add_subparsers(dest="subcommand", required=True, metavar="SUBCOMMAND")
    for name, (fn, help_text) in SUBCOMMANDS.items():
        sp = subs.add_parser(name, help=help_text)
        sp.add_argument("--json", action="store_true", help="machine-readable output")
        if name == "add":
            sp.add_argument("finding", help="the friction / bug / idea, 1-3 sentences")
            sp.add_argument(
                "--kind",
                "--severity",
                dest="kind",
                choices=KINDS,
                default="friction",
                help="severity tag (default: friction)",
            )
            sp.add_argument("--context", help="what the operator was doing")
            sp.add_argument("--diagnosis", help="related diagnosis path")
        else:
            sp.add_argument("--all", action="store_true", help="include collected rows")
            sp.add_argument("--kind", choices=KINDS, help="only this severity tag")
        sp.set_defaults(func=fn)
