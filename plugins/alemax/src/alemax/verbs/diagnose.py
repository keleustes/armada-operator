"""`alemax diagnose` — scaffold a diagnosis directory from the standard 10-section template.

The template is the point: ten headings in a fixed order, so a diagnosis written in one
clone reads the same as one written in another. Everything under them is filled in
conversationally.
"""

from __future__ import annotations

import argparse
import getpass
import os
import re
import sys
from datetime import date
from pathlib import Path

from ..io import OK, die, emit
from ..repo import is_meta_repo, toplevel
from ..scratch import atomic_write, local_dir

SLUG_OK = re.compile(r"^[a-z][a-z0-9-]*$")
OPENSPEC_DIR = "openspec/diagnosis"
LOCAL_DIR = ".local/diagnosis"

SECTIONS = (
    "TL;DR",
    "The scenario that triggered the diagnosis",
    "Empirical findings",
    "Mechanism",
    "Design re-examination",
    "Findings table",
    "Reproduction",
    "Open questions",
    "Next steps",
    "Cross-links",
)


def root_for(a: argparse.Namespace) -> Path:
    return Path(a.root).resolve() if a.root else toplevel()


def drive_of(root: Path) -> str:
    """The volume name from a `/Volumes/<drive>/…` root, for the header. (path-literal-docs)"""
    parts = root.resolve().parts
    return parts[2] if len(parts) > 2 and parts[1] == "Volumes" else ""


def template(
    slug: str, symptom: str, scope: str, hypothesis: str, when: str, operator: str, drive: str
) -> str:
    head = [f"# Diagnosis — {symptom}", "", f"**Date:** {when}", f"**Operator:** {operator}"]
    if drive:
        head.append(f"**Active drive:** {drive}")
    filled = {
        "TL;DR": f"<2-4 sentences. Refine as the diagnosis develops.>\n\nStarting hypothesis: {hypothesis}",
        "The scenario that triggered the diagnosis": f"**Scope:** {scope}\n\n<Detailed context: what was the operator doing, what command "
        "produced what output.>",
        "Empirical findings": "<Observations from runs, command output, traced behavior, log excerpts.>",
        "Mechanism": "<Root-cause analysis. What is actually happening under the hood?>",
        "Design re-examination": "<Does this finding change any spec or assumption? Which capability is affected?>",
        "Findings table": "| # | Finding | Severity | Resolution |\n|---|---|---|---|\n"
        "| 1 | <one-line> | blocker / friction / idea | <action / proposal> |",
        "Reproduction": "<Minimal repro steps, as a fenced block of commands.>",
        "Open questions": "<What is not yet resolved? What needs an operator decision?>",
        "Next steps": "<Follow-up changes to propose, ideas to capture, fixes to ship.>",
        "Cross-links": f"<Related specs, archived changes, sibling diagnoses, PRs. Slug: {slug}>",
    }
    body = "".join(f"\n## {name}\n\n{filled[name]}\n" for name in SECTIONS)
    return "\n".join(head) + "\n" + body


def cmd_new(a: argparse.Namespace) -> int:
    root = root_for(a)
    slug = a.slug.strip()
    if not SLUG_OK.match(slug):
        die(f"invalid slug `{slug}` — kebab-case lowercase (a letter, then a-z 0-9 and -)", 2)

    # `auto` is resolved here but never silently: the skill asks the operator either way
    # (spec alemax-skills — it SHALL ALWAYS ask). This only supplies the default.
    location = a.location
    if location == "auto":
        location = "openspec" if is_meta_repo(root) else "local"

    when = date.today().isoformat()
    target = (
        root / OPENSPEC_DIR / f"{when}-{slug}"
        if location == "openspec"
        else root / LOCAL_DIR / slug
    )
    if target.exists() and not a.force:
        die(
            f"{target.relative_to(root)} already exists — pick another slug, or --force to "
            "overwrite its diagnosis.md"
        )

    text = template(
        slug,
        a.symptom.strip(),
        (a.scope or "<not given>").strip(),
        (a.hypothesis or "<not given — refine as you go>").strip(),
        when,
        getpass.getuser(),
        drive_of(root),
    )
    rel = f"{target.relative_to(root)}/diagnosis.md"
    if a.dry_run:
        sys.stdout.write(text)
        print(f"[dry-run] would write {rel}", file=sys.stderr)
        return OK

    if location == "local":
        local_dir(root, write=True)
    target.mkdir(parents=True, exist_ok=True)
    atomic_write(target / "diagnosis.md", text)

    where = (
        "committed — lands in canonical by PR"
        if location == "openspec"
        else "operator-local, gitignored"
    )
    print(f"scaffolded {rel}\n  slug:     {slug}\n  location: {location} ({where})")
    print(f"  sections: {' · '.join(SECTIONS[:5])} ·\n            {' · '.join(SECTIONS[5:])}")
    return OK


def cmd_list(a: argparse.Namespace) -> int:
    root = root_for(a)
    rows = []
    for location, rel in (("openspec", OPENSPEC_DIR), ("local", LOCAL_DIR)):
        base = root / rel
        if not base.is_dir():
            continue
        for e in sorted(os.scandir(base), key=lambda x: x.name):
            if e.is_dir():
                rows.append(
                    {
                        "location": location,
                        "path": f"{rel}/{e.name}",
                        "has_diagnosis": (Path(e.path) / "diagnosis.md").is_file(),
                    }
                )
    if a.json:
        emit({"diagnoses": rows}, as_json=True)
        return OK
    if not rows:
        print(f"no diagnosis directories under {OPENSPEC_DIR}/ or {LOCAL_DIR}/")
        return OK
    for r in rows:
        tail = "" if r["has_diagnosis"] else "   (no diagnosis.md)"
        print(f"{r['location']:<9} {r['path']}{tail}")
    print(f"— {len(rows)} directory(ies)")
    return OK


SUBCOMMANDS = {
    "new": (cmd_new, "scaffold a diagnosis directory"),
    "list": (cmd_list, "the diagnosis directories this repo already has"),
}


def register(ap: argparse.ArgumentParser) -> None:
    ap.add_argument("--root", help="repo toplevel (default: git rev-parse --show-toplevel)")
    subs = ap.add_subparsers(dest="subcommand", required=True, metavar="SUBCOMMAND")
    for name, (fn, help_text) in SUBCOMMANDS.items():
        sp = subs.add_parser(name, help=help_text)
        sp.add_argument("--json", action="store_true", help="machine-readable output")
        if name == "new":
            sp.add_argument("--slug", required=True, help="kebab-case topic slug")
            sp.add_argument(
                "--symptom", required=True, help="the observable failure (becomes the H1)"
            )
            sp.add_argument("--scope", help="one line: what this diagnosis covers")
            sp.add_argument("--hypothesis", help="the starting guess")
            sp.add_argument(
                "--location",
                choices=("openspec", "local", "auto"),
                default="auto",
                help="committed / operator-local / by context (default: auto)",
            )
            sp.add_argument(
                "--force",
                action="store_true",
                help="overwrite diagnosis.md in an existing directory",
            )
            sp.add_argument(
                "--dry-run", action="store_true", help="print the scaffold instead of writing it"
            )
        sp.set_defaults(func=fn)
