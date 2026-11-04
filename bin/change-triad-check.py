#!/usr/bin/env python3
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""change-triad-check.py — every in-flight change carries intent · spec · plan.

Anthropic's AI-native SDLC playbook (academy.claude.com, 2026-08-21) asks that each
change carry three documents: `intent.md` → `spec.md` → `plan.md`, in an `intent/`
folder. OpenSpec already IS that chain under other names — `proposal.md` (why),
`specs/<capability>/spec.md` (what), `tasks.md` (how) — with an archive step the
playbook's shape lacks. So this check enforces the SHAPE, in whichever vocabulary
the repo already speaks, and never introduces a second one:

  openspec/ exists       OpenSpec convention. Per directory under `openspec/changes/`
                         (`archive/` excluded): proposal.md · specs/*/spec.md · tasks.md
  else intent/ exists    Playbook convention. Per directory under `intent/`:
                         intent.md · spec.md · plan.md
  neither                Nothing to check. Exits 0 and says so.

Exit 1 ("REFUSE"):

  C1  the intent document is missing or empty (proposal.md / intent.md) — a change
      whose reason is unwritten cannot be reviewed, resumed, or archived
  C2  the plan document is missing or empty (tasks.md / plan.md)

Warnings (never fail a commit; --strict promotes every one to a refusal):

  C3  no spec delta and no declared opt-out. Under OpenSpec this is `openspec
      validate --strict`'s rule and its message is better than anything here — the
      warning exists so the triad is reported in ONE place and so the playbook
      convention gets the same rule, where no validator ships. A change that
      genuinely touches no spec declares `skip_specs: true` in its `.openspec.yaml`
      and this check stays quiet.
  C4  a document that is still a template stub: under three lines of content once
      headings, blank lines and HTML comments are removed, or a body whose whole
      content is TBD / TODO.

`--change <name>` checks one change. Reads the working tree, edits nothing, opens
nothing outside the change directories it found. `--json` prints the same findings.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
HEADING = re.compile(r"^\s{0,3}#{1,6}\s")
STUB_BODY = re.compile(r"^(tbd|todo)\b", re.IGNORECASE)
SKIP_SPECS = re.compile(r"^\s*skip_specs\s*:\s*(true|yes)\s*$", re.IGNORECASE | re.MULTILINE)
MIN_CONTENT_LINES = 3

# (label, intent file, plan file, spec-delta glob relative to the change directory)
OPENSPEC = ("openspec", "proposal.md", "tasks.md", "specs/*/spec.md")
PLAYBOOK = ("intent", "intent.md", "plan.md", "spec.md")


def git(repo: Path, *args: str) -> str | None:
    try:
        done = subprocess.run(
            ["git", *args], cwd=str(repo), check=True, capture_output=True, text=True
        )
    except OSError, subprocess.CalledProcessError:
        return None
    return done.stdout


def default_repo() -> Path:
    top = git(Path.cwd(), "rev-parse", "--show-toplevel")
    return Path(top.strip()) if top else Path.cwd()


def content_lines(path: Path) -> int:
    """Lines that carry content: not blank, not a heading, not an HTML comment."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0
    body = HTML_COMMENT.sub("", text)
    return sum(1 for ln in body.splitlines() if ln.strip() and not HEADING.match(ln))


def is_stub(path: Path) -> bool:
    try:
        text = HTML_COMMENT.sub("", path.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return True
    stripped = "\n".join(ln for ln in text.splitlines() if not HEADING.match(ln)).strip()
    return bool(STUB_BODY.match(stripped)) or content_lines(path) < MIN_CONTENT_LINES


def declares_skip_specs(change: Path) -> bool:
    cfg = change / ".openspec.yaml"
    if not cfg.is_file():
        return False
    try:
        return bool(SKIP_SPECS.search(cfg.read_text(encoding="utf-8", errors="replace")))
    except OSError:
        return False


def find_convention(repo: Path) -> tuple[tuple[str, str, str, str], Path] | None:
    changes = repo / "openspec" / "changes"
    if changes.is_dir():
        return OPENSPEC, changes
    intent = repo / "intent"
    if intent.is_dir():
        return PLAYBOOK, intent
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="change-triad-check.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--repo", help="repo root (default: git toplevel of the cwd, else the cwd)")
    ap.add_argument("--change", help="check only this change directory")
    ap.add_argument("--strict", action="store_true", help="promote C3/C4 warnings to refusals")
    ap.add_argument("--json", action="store_true", help="print the findings as one JSON object")
    args = ap.parse_args(argv)
    repo = Path(args.repo).resolve() if args.repo else default_repo()

    found = find_convention(repo)
    if found is None:
        msg = (
            "change-triad-check: no change-triad convention in this repo "
            "(no openspec/changes/, no intent/) — nothing to check"
        )
        print(
            json.dumps({"repo": str(repo), "convention": None, "note": msg}, indent=2)
            if args.json
            else msg
        )
        return 0

    (label, intent_name, plan_name, spec_glob), root = found
    names = sorted(
        d.name
        for d in root.iterdir()
        if d.is_dir() and d.name != "archive" and not d.name.startswith(".")
    )
    if args.change:
        names = [n for n in names if n == args.change]
        if not names:
            print(f"change-triad-check: no change `{args.change}` under {root.relative_to(repo)}/")
            return 1

    refusals: list[str] = []
    warnings: list[str] = []
    records: list[dict[str, object]] = []

    for name in names:
        change = root / name
        rel = str(change.relative_to(repo))
        findings: list[dict[str, str]] = []

        for rule, doc in (("C1", intent_name), ("C2", plan_name)):
            path = change / doc
            half = "intent" if rule == "C1" else "plan"
            if not path.is_file() or path.stat().st_size == 0:
                refusals.append(
                    f"{rule}: {rel}/{doc}: missing or empty — the triad is intent · spec · plan, and this is the {half}"
                )
                findings.append({"rule": rule, "doc": doc, "state": "missing"})
            elif is_stub(path):
                line = f"C4: {rel}/{doc}: still a template stub (under {MIN_CONTENT_LINES} lines of content, or TBD/TODO only)"
                (refusals if args.strict else warnings).append(line)
                findings.append({"rule": "C4", "doc": doc, "state": "stub"})

        deltas = sorted(str(p.relative_to(change)) for p in change.glob(spec_glob) if p.is_file())
        rec: dict[str, object] = {"change": name, "path": rel, "deltas": deltas}
        if not deltas:
            if declares_skip_specs(change):
                rec["skip_specs"] = True
            else:
                hint = (
                    "`openspec validate --strict` owns this rule; set `skip_specs: true` in "
                    f"{rel}/.openspec.yaml for a change that touches no spec"
                    if label == "openspec"
                    else f"add {rel}/{spec_glob} — what the change makes true"
                )
                line = f"C3: {rel}: no spec delta ({spec_glob}) and no declared opt-out — {hint}"
                (refusals if args.strict else warnings).append(line)
                findings.append({"rule": "C3", "doc": spec_glob, "state": "missing"})
        rec["findings"] = findings
        records.append(rec)

    if args.json:
        print(
            json.dumps(
                {
                    "repo": str(repo),
                    "convention": label,
                    "root": str(root.relative_to(repo)),
                    "changes": records,
                    "refusals": len(refusals),
                    "warnings": len(warnings),
                },
                indent=2,
            )
        )
        return 1 if refusals else 0

    print(
        f"change-triad-check: {repo} — {label} convention, {len(names)} in-flight change(s) under "
        f"{root.relative_to(repo)}/ (triad: {intent_name} · {spec_glob} · {plan_name})"
        f"{' [strict]' if args.strict else ''}"
    )
    for line in refusals:
        print(f"REFUSE {line}")
    for line in warnings:
        print(f"WARN {line}")
    print(
        f"change-triad-check: {len(refusals)} refusal(s), {len(warnings)} warning(s) — {'FAIL' if refusals else 'pass'}"
    )
    return 1 if refusals else 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    sys.exit(main())
