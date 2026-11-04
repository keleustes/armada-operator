#!/usr/bin/env python3
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""spec-summary-check.py — every capability spec opens with a `## Summary`.

`spec-governance` asks that each `openspec/specs/*/spec.md` open with a `## Summary` —
3-5 sentences of plain prose between the H1 and `## Purpose` — naming the load-bearing
concepts an operator needs before reading the `### Requirement:` blocks.

WHY THIS IS A CHECK AND NOT A REVIEW HABIT. `openspec archive` copies a new capability's
`## Purpose` out of the change's spec delta and writes the main spec. It knows nothing
about `## Summary`, which is this repo's convention rather than upstream's. So a
capability-creating change lands non-compliant unless the archiving session remembers to
hand-write the summary afterwards — and 16 of 36 specs measured exactly what that
remembering is worth. The rule needs a machine behind it or it decays on every archive.

Findings (warnings by default; `--strict` promotes every one to a refusal):

  S1  no `## Summary` section at all
  S2  `## Summary` present but misplaced — it must sit between the H1 and `## Purpose`,
      because that is the only position where it is read before the requirements it
      orients
  S3  fewer than MIN_SENTENCES sentences of prose. The floor is a proxy, not a quality
      bar: prose that names the wrong concepts is a review problem and stays one. The
      3-5 range in the spec is guidance; only the floor is policed.

A repo with no `openspec/specs/` has nothing to check and exits 0 saying so — a project
that keeps no specs is not in violation of a rule about specs.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

MIN_SENTENCES = 3
H1_RE = re.compile(r"^#\s+\S")
HEADING_RE = re.compile(r"^##\s+(.+?)\s*$")
# A sentence end: . ! or ? followed by whitespace-then-capital, or end of text. Counting
# bare periods over-counts every `build.py` and `.claude` in the prose.
SENTENCE_RE = re.compile(r"[.!?](?=\s+[A-Z\"'`(])|[.!?]\s*$")


def sections(text: str) -> list[tuple[str, int]]:
    """Every `## ` heading with its line number, in file order."""
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        if m := HEADING_RE.match(line):
            out.append((m.group(1), i))
    return out


def summary_body(text: str) -> str:
    """Text between `## Summary` and the next `## ` heading."""
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if HEADING_RE.match(line) and HEADING_RE.match(line).group(1).lower() == "summary":
            start = i + 1
            break
    if start is None:
        return ""
    body = []
    for line in lines[start:]:
        if HEADING_RE.match(line):
            break
        body.append(line)
    return "\n".join(body).strip()


def count_sentences(body: str) -> int:
    prose = "\n".join(
        line for line in body.splitlines() if not line.lstrip().startswith(("-", "*", "|"))
    )
    return len(SENTENCE_RE.findall(prose))


def check(path: Path) -> tuple[str, str] | None:
    """(code, message) for the first finding on this spec, or None."""
    text = path.read_text(encoding="utf-8")
    heads = sections(text)
    names = [h.lower() for h, _ in heads]
    if "summary" not in names:
        return ("S1", "no `## Summary` — it belongs between the H1 and `## Purpose`")

    first_h1 = next((i for i, line in enumerate(text.splitlines(), 1) if H1_RE.match(line)), 0)
    sum_line = next(line for h, line in heads if h.lower() == "summary")
    before = [h.lower() for h, line in heads if line < sum_line]
    if sum_line < first_h1 or any(h in ("purpose", "requirements") for h in before):
        return ("S2", "`## Summary` is misplaced — it must sit between the H1 and `## Purpose`")

    n = count_sentences(summary_body(path.read_text(encoding="utf-8")))
    if n < MIN_SENTENCES:
        return ("S3", f"`## Summary` has {n} sentence(s) — the floor is {MIN_SENTENCES}")
    return None


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--repo", default=".", help="repo root (default: cwd)")
    ap.add_argument("--strict", action="store_true", help="promote every warning to a refusal")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    specs_dir = repo / "openspec" / "specs"
    paths = sorted(specs_dir.glob("*/spec.md")) if specs_dir.is_dir() else []

    findings = []
    for p in paths:
        if hit := check(p):
            findings.append((p.relative_to(repo), *hit))

    refusals = findings if args.strict else []
    warnings = [] if args.strict else findings

    if args.json:
        print(
            json.dumps(
                {
                    "repo": str(repo),
                    "checked": len(paths),
                    "findings": [
                        {"path": str(f[0]), "code": f[1], "message": f[2]} for f in findings
                    ],
                    "refusals": len(refusals),
                    "warnings": len(warnings),
                },
                indent=2,
            )
        )
        return 1 if refusals else 0

    if not paths:
        print(f"spec-summary-check: {repo} — no openspec/specs/ in this repo; nothing to check")
        print("spec-summary-check: 0 refusal(s), 0 warning(s) — pass")
        return 0

    print(
        f"spec-summary-check: {repo} — {len(paths)} capability spec(s) under openspec/specs/"
        f"{' [strict]' if args.strict else ''}"
    )
    for rel, code, msg in refusals:
        print(f"REFUSE {rel}: {code}: {msg}")
    for rel, code, msg in warnings:
        print(f"WARN {rel}: {code}: {msg}")
    print(
        f"spec-summary-check: {len(refusals)} refusal(s), {len(warnings)} warning(s) — "
        f"{'FAIL' if refusals else 'pass'}"
    )
    return 1 if refusals else 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    sys.exit(main())
