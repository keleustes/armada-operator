#!/usr/bin/env python3
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""check-doc-set.py — the three-doc set (CLAUDE.md · README.md · architecture.md).

Checks that a repo keeps the fleet's three-doc convention (claude-meta spec
`project-doc-set`): the three files at the repo root, lowercase `architecture.md`
seeded, and a routing paragraph at the top of CLAUDE.md that names the other two.
Runs from `.pre-commit-config.yaml` when one of the three is staged, and by hand
from a session.

Exit 1 ("REFUSE") only on the two mechanical defects no project could dispute:

  R1  a CLAUDE.md or architecture.md staged directly under docs/ or openspec/
      instead of the root, with no root copy in the index
  R2  a staged CLAUDE.md whose first paragraph (everything above the first `## `,
      HTML comments excluded) no longer names README.md and architecture.md, or
      names one the index does not hold

Everything else is a WARN and never fails the commit. With --strict, R1 and R2
refuse whether or not the file is staged (for CI or a session audit).

Reads the git index (`git ls-files`), never the filesystem, and compares names
case-insensitively: APFS makes `test -f architecture.md` succeed against
`ARCHITECTURE.md`, so a filesystem check lies. An existing uppercase copy at the
root is grandfathered; a rename is never proposed. Inspects only the three docs —
it never opens MODEL.md, CHANGELOG.md, AGENTS.md, docs/ or a wiki — and edits
nothing.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

CLAUDE = "claude.md"
README = "readme.md"
ARCH = "architecture.md"
MISPLACED_DIRS = ("docs", "openspec")
CLAUDE_MAX_LINES = 120

HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
H2 = re.compile(r"^## ", re.MULTILINE)
GOTCHA_HEADING = re.compile(r"^#{2,} .*gotcha", re.IGNORECASE | re.MULTILINE)
LITERAL_PATH = re.compile(r"/(Volumes|Users)/[A-Za-z0-9_.-]+")
CONFIG_HEADING = re.compile(r"^## +Configuration\b", re.IGNORECASE | re.MULTILINE)


def git(repo: Path, *args: str) -> str | None:
    try:
        done = subprocess.run(
            ["git", *args],
            cwd=str(repo),
            check=True,
            capture_output=True,
            text=True,
        )
    except OSError, subprocess.CalledProcessError:
        return None
    return done.stdout


def default_repo() -> Path:
    top = git(Path.cwd(), "rev-parse", "--show-toplevel")
    return Path(top.strip()) if top else Path.cwd()


def index_paths(repo: Path, no_git: bool) -> tuple[list[str], str]:
    if not no_git:
        out = git(repo, "ls-files", "-z")
        if out is not None:
            return [p for p in out.split("\0") if p], "git index"
    paths: list[str] = []
    for root, dirs, files in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in (".git", ".venv", "node_modules")]
        for name in files:
            paths.append(os.path.relpath(os.path.join(root, name), repo))
    return paths, "filesystem walk (no git index; case is whatever the disk says)"


def staged_paths(repo: Path, no_git: bool) -> set[str]:
    if no_git:
        return set()
    out = git(repo, "diff", "--cached", "--name-only", "--relative", "-z")
    return {p for p in (out or "").split("\0") if p}


def root_doc(paths: list[str], name: str) -> str | None:
    """The index spelling of a root-level doc, matched case-insensitively."""
    for p in paths:
        if p.lower() == name:
            return p
    return None


def misplaced_docs(paths: list[str], name: str) -> list[str]:
    hits = []
    for p in paths:
        parts = p.split("/")
        if len(parts) == 2 and parts[0].lower() in MISPLACED_DIRS and parts[1].lower() == name:
            hits.append(p)
    return hits


def read(repo: Path, rel: str) -> str:
    try:
        return (repo / rel).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def routing_block(text: str) -> str:
    body = HTML_COMMENT.sub("", text)
    m = H2.search(body)
    return body[: m.start()] if m else body


def line_count(text: str) -> int:
    return len(HTML_COMMENT.sub("", text).splitlines())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="check-doc-set.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "--repo",
        help="repo root to check (default: git toplevel of the cwd, else the cwd)",
    )
    ap.add_argument(
        "--strict",
        action="store_true",
        help="refuse R1/R2 even when the offending file is not staged",
    )
    ap.add_argument(
        "--no-git",
        action="store_true",
        help="walk the filesystem instead of the git index (not a repo)",
    )
    args = ap.parse_args(argv)
    repo = Path(args.repo).resolve() if args.repo else default_repo()

    refusals: list[str] = []
    warnings: list[str] = []
    paths, source = index_paths(repo, args.no_git)
    staged = staged_paths(repo, args.no_git)

    claude = root_doc(paths, CLAUDE)
    readme = root_doc(paths, README)
    arch = root_doc(paths, ARCH)

    def verdict(path: str | None, rule: str, msg: str) -> None:
        hard = args.strict or (path is not None and path in staged)
        (refusals if hard else warnings).append(f"{rule}: {msg}")

    # R1 — placement: a doc under docs/ or openspec/ with no root copy.
    for name in (ARCH, CLAUDE):
        root = root_doc(paths, name)
        for mp in misplaced_docs(paths, name):
            if root is None:
                verdict(
                    mp,
                    "R1",
                    f"{mp}: the convention keeps this file at the repo root, "
                    f"not under {mp.split('/')[0]}/ — `git mv {mp} {name}`",
                )
            else:
                warnings.append(
                    f"W: {mp}: a second copy beside root {root}; "
                    "the root copy is the one the convention reads"
                )

    # R2 — the routing paragraph at the top of CLAUDE.md.
    if claude is None:
        warnings.append("W: CLAUDE.md: not at the root")
    else:
        text = read(repo, claude)
        block = routing_block(text).lower()
        for want in ("README.md", "architecture.md"):
            if want.lower() not in block:
                if want.lower() == ARCH and root_doc(paths, ARCH) is None:
                    # An absent architecture document is a warning (spec project-doc-set),
                    # so not naming the absent file cannot be a refusal: it blocked every
                    # CLAUDE.md commit in a project that never had one (app01's movies-library).
                    warnings.append(
                        f"W: {claude}: names no architecture document and the repo has "
                        "none — seed architecture.md, then name it in the routing paragraph"
                    )
                    continue
                verdict(
                    claude,
                    "R2",
                    f"{claude}: the paragraph above its first `## ` no longer names {want}",
                )
            elif root_doc(paths, want.lower()) is None:
                verdict(
                    claude,
                    "R2",
                    f"{claude}: names {want} but the index holds no root {want} (any case)",
                )
        n = line_count(text)
        if n > CLAUDE_MAX_LINES:
            warnings.append(
                f"W: {claude}: {n} lines (HTML comments excluded) — over "
                f"{CLAUDE_MAX_LINES}; a line not true for every task belongs in "
                "the owning skill, architecture.md, README.md or openspec/ideas.md"
            )
        if GOTCHA_HEADING.search(text):
            warnings.append(
                f"W: {claude}: a gotchas heading — a gotcha goes to the skill of "
                "the thing that bit, or /alemax:feedback"
            )
        m = LITERAL_PATH.search(HTML_COMMENT.sub("", text))
        if m:
            warnings.append(
                f"W: {claude}: literal path `{m.group(0)}` — resolve paths from "
                "a variable, never write one here"
            )

    # README.md — warnings only.
    if readme is None:
        warnings.append("W: README.md: not at the root")
    else:
        text = read(repo, readme)
        if ARCH not in text.lower():
            warnings.append(
                f"W: {readme}: no pointer to the architecture document "
                "(a `## Documentation` line naming architecture.md)"
            )
        if not CONFIG_HEADING.search(text):
            warnings.append(
                f"W: {readme}: no `## Configuration` heading — the variable catalogue lives there"
            )

    # architecture.md — absence warns; spelling is reported, never corrected.
    if arch is None:
        warnings.append(
            "W: architecture.md: not in the index — seed it from claude-meta's "
            "scaffolding/templates/architecture.md (a fresh bootstrap ships it)"
        )

    def show(p: str | None) -> str:
        if p is None:
            return "—"
        return f"{p}{' [staged]' if p in staged else ''}"

    print(
        f"check-doc-set: scanned {repo} via {source} ({len(paths)} paths); "
        f"CLAUDE.md={show(claude)} README.md={show(readme)} "
        f"architecture.md={show(arch)}"
        f"{' [strict]' if args.strict else ''}"
    )
    for line in refusals:
        print(f"REFUSE {line}")
    for line in warnings:
        print(f"WARN {line}")
    print(
        f"check-doc-set: {len(refusals)} refusal(s), {len(warnings)} warning(s) — "
        f"{'FAIL' if refusals else 'pass'}"
    )
    return 1 if refusals else 0


if __name__ == "__main__":
    sys.exit(main())
