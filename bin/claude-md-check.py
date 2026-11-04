#!/usr/bin/env python3
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""claude-md-check.py — the startup context budget (claude-meta spec `context-budget`).

Resolves what a session in this repo pays *before it reads a line of code* and
measures it. The startup set is what Claude Code loads at launch:

  CLAUDE.md (root, else .claude/CLAUDE.md)   — every session, every task
  CLAUDE.local.md                            — the same, per clone, untracked
  every @import, recursively, max 4 hops     — "imported files load at launch"
  .claude/rules/*.md with no `paths:` key    — "loaded at launch with the same
                                                priority as .claude/CLAUDE.md"

A rules file *with* `paths:` is conditional — it loads when a matching file is
read — so it is listed and never counted. The skill/command listing the harness
injects is reported as an estimate beside the total: it is real context, but no
line of it lives in these files.

Sizes are lines (of the files as written; block-level HTML comments are stripped
before injection, so they are stripped here too) and estimated tokens (chars/4).

Exit 1 ("REFUSE") on the two structural defects:

  R1  a fenced code block in CLAUDE.md — a procedure the model re-reads and
      re-judges on every task; code belongs in a skill, behind one invocation
  R2  an @import of an `index.md`, or of any file over 5,000 estimated tokens.
      After compaction "a file over 5,000 tokens comes back as a path reference
      without its content", so the read is a total loss — and an index is a
      manifest for a tool, never a read path

Warnings (never fail a commit; --strict promotes every one to a refusal):

  W1  CLAUDE.md over --budget lines (default 120; --canonical raises it to 200)
  W2  the startup set over --total-budget lines (default 400)
  W3  a ledger entry — a `### <n>.` heading under a `## …Guardrails…` or
      `## …Rules of engagement…` section — missing `since` / `enforced by` /
      `depth` / `retire when`; `since` may name a date or a model ID
  W4  a `.claude/rules/*.md` over 60 lines with no `paths:` — unconditional
      depth, charged to every task; scope it or move it to a skill
  W5  an @import that resolves to no file, or past the harness's 4-hop limit

R1 and R2 refuse whether or not the offending file is staged: they are defects of
shape, not of this commit. Runs from `.pre-commit-config.yaml` when CLAUDE.md, an
import or a rules file is staged, and by hand from a session. Reads the working
tree (never the git index — an import may be untracked), edits nothing, and opens
nothing outside the startup set it resolved (plus skill/command frontmatter for
the listing estimate). `--json` prints the same findings as one object.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

CHARS_PER_TOKEN = 4
COMPACTION_TOKEN_LIMIT = 5000  # docs/en/context-window § What survives compaction
MAX_IMPORT_DEPTH = 4  # docs/en/memory § Import additional files
CLAUDE_MAX_LINES = 120
CANONICAL_MAX_LINES = 200
STARTUP_MAX_LINES = 400
RULE_MAX_LINES = 60

HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
FENCE = re.compile(r"^\s{0,3}(```+|~~~+)")
CODE_SPAN = re.compile(r"`[^`\n]*`")
FRONTMATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)
PATHS_KEY = re.compile(r"^paths\s*:", re.MULTILINE)
IMPORT = re.compile(r"(?:(?<=^)|(?<=[\s(\[]))@([~./A-Za-z0-9][^\s`,;)\]]*)")
LEDGER_SECTION = re.compile(r"^##\s+.*(guardrail|rules of engagement)", re.IGNORECASE)
LEDGER_ENTRY = re.compile(r"^###\s+(\d+)\.\s*(.*)$")
ANY_H2 = re.compile(r"^##\s")
ANY_H3 = re.compile(r"^###\s")
DOC_SUFFIXES = (".md", ".markdown", ".txt", ".json", ".yaml", ".yml", ".toml")
LEDGER_FIELDS = ("since", "enforced by", "depth", "retire when")


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


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def strip_comments(text: str) -> str:
    return HTML_COMMENT.sub("", text)


def measure(text: str) -> tuple[int, int]:
    body = strip_comments(text)
    return len(body.splitlines()), (len(body) + CHARS_PER_TOKEN - 1) // CHARS_PER_TOKEN


def outside_code(text: str) -> str:
    """The text an import parser sees: fenced blocks and code spans removed."""
    kept, fence = [], None
    for line in strip_comments(text).splitlines():
        m = FENCE.match(line)
        if fence is None and m:
            fence = m.group(1)[0]
            continue
        if fence is not None:
            if m and m.group(1)[0] == fence:
                fence = None
            continue
        kept.append(CODE_SPAN.sub("", line))
    return "\n".join(kept)


def fences_in(text: str) -> int:
    n, fence = 0, None
    for line in strip_comments(text).splitlines():
        m = FENCE.match(line)
        if not m:
            continue
        if fence is None:
            fence, n = m.group(1)[0], n + 1
        elif m.group(1)[0] == fence:
            fence = None
    return n


def clean_token(token: str) -> str:
    """Trim the sentence punctuation a prose line leaves on the end of a path."""
    return token.rstrip(".!?:'\"")


def looks_like_path(token: str) -> bool:
    return (
        token.startswith(("~/", "/", "./", "../"))
        or "/" in token
        or token.lower().endswith(DOC_SUFFIXES)
    )


def resolve_import(token: str, base: Path) -> Path:
    if token.startswith("~"):
        return Path(os.path.expanduser(token))
    p = Path(token)
    return p if p.is_absolute() else (base.parent / p)


def frontmatter(text: str) -> str:
    m = FRONTMATTER.match(text)
    return m.group(1) if m else ""


def field(front: str, key: str) -> str:
    m = re.search(rf"^{key}\s*:\s*(.+)$", front, re.MULTILINE)
    return m.group(1).strip().strip("\"'") if m else ""


def ledger_entries(text: str) -> list[tuple[str, list[str]]]:
    """(entry title, missing fields) for every `### <n>.` under a ledger section."""
    out: list[tuple[str, list[str]]] = []
    lines = strip_comments(text).splitlines()
    in_section = False
    title: str | None = None
    body: list[str] = []

    def flush() -> None:
        if title is None:
            return
        blob = "\n".join(body).lower()
        missing = [f for f in LEDGER_FIELDS if f not in blob]
        out.append((title, missing))

    for line in lines:
        if ANY_H2.match(line):
            flush()
            title, body = None, []
            in_section = bool(LEDGER_SECTION.match(line))
            continue
        if in_section and ANY_H3.match(line):
            flush()
            m = LEDGER_ENTRY.match(line)
            title, body = (m.group(0)[4:].strip() if m else None), []
            continue
        if title is not None:
            body.append(line)
    flush()
    return out


def listing_estimate(repo: Path) -> dict[str, int]:
    """The skill/command listing the harness injects, in chars of name + description.

    Both skill shapes count: a flat `.claude/skills/<name>/SKILL.md` and a plugin skill
    `.claude/skills/<plugin>/skills/<name>/SKILL.md`, which lists once as `/<plugin>:<name>`.
    A capability that ships BOTH a skill and a same-named command stub is listed twice —
    the colon and hyphen spellings differ, so the harness merges nothing.
    """
    chars = entries = 0
    skills_dir = repo / ".claude" / "skills"
    found = sorted(
        list(skills_dir.glob("*/SKILL.md")) + list(skills_dir.glob("*/skills/*/SKILL.md"))
    )
    for skill in found:
        front = frontmatter(read(skill))
        chars += len(field(front, "name")) + len(field(front, "description"))
        entries += 1
    cmds = repo / ".claude" / "commands"
    for cmd in sorted(cmds.rglob("*.md")) if cmds.is_dir() else []:
        front = frontmatter(read(cmd))
        chars += len(cmd.stem) + len(field(front, "description"))
        entries += 1
    return {
        "entries": entries,
        "tokens": (chars + CHARS_PER_TOKEN - 1) // CHARS_PER_TOKEN,
    }


class Report:
    def __init__(self, repo: Path, strict: bool) -> None:
        self.repo, self.strict = repo, strict
        self.refusals: list[str] = []
        self.warnings: list[str] = []

    def rel(self, p: Path) -> str:
        try:
            return str(p.relative_to(self.repo))
        except ValueError:
            return str(p)

    def refuse(self, rule: str, msg: str) -> None:
        """R1/R2 — a defect of shape; staging does not change the answer."""
        self.refusals.append(f"{rule}: {msg}")

    def warn(self, rule: str, msg: str) -> None:
        (self.refusals if self.strict else self.warnings).append(f"{rule}: {msg}")


def collect_startup(repo: Path, rep: Report) -> list[dict]:
    """The files Claude Code loads at launch, in load order, with their sizes."""
    files: list[dict] = []
    seen: set[Path] = set()

    def add(path: Path, kind: str, depth: int, via: str | None) -> None:
        rp = path.resolve()
        if rp in seen:
            return
        seen.add(rp)
        text = read(path)
        lines, tokens = measure(text)
        files.append(
            {
                "path": rep.rel(path),
                "kind": kind,
                "depth": depth,
                "via": via,
                "lines": lines,
                "tokens": tokens,
            }
        )
        walk_imports(path, text, depth, rep, add)

    root = repo / "CLAUDE.md"
    if not root.is_file():
        alt = repo / ".claude" / "CLAUDE.md"
        root = alt if alt.is_file() else root
    if root.is_file():
        add(root, "claude-md", 0, None)
    else:
        rep.warn("W", "no CLAUDE.md at the repo root or under .claude/")

    local = repo / "CLAUDE.local.md"
    if local.is_file():
        add(local, "claude-local", 0, None)

    rules_dir = repo / ".claude" / "rules"
    for rule in sorted(rules_dir.rglob("*.md")) if rules_dir.is_dir() else []:
        text = read(rule)
        if PATHS_KEY.search(frontmatter(text)):
            lines, tokens = measure(text)
            files.append(
                {
                    "path": rep.rel(rule),
                    "kind": "rule-scoped",
                    "depth": 0,
                    "via": None,
                    "lines": lines,
                    "tokens": tokens,
                }
            )
            continue
        add(rule, "rule-always", 0, None)
        n = measure(text)[0]
        if n > RULE_MAX_LINES:
            rep.warn(
                "W4",
                f"{rep.rel(rule)}: {n} lines and no `paths:` frontmatter — it loads "
                "at launch on every task; add `paths:` or move the depth to a skill",
            )
    return files


def walk_imports(owner: Path, text: str, depth: int, rep: Report, add) -> None:
    for raw in IMPORT.findall(outside_code(text)):
        token = clean_token(raw)
        if not token:
            continue
        target = resolve_import(token, owner)
        if not target.is_file():
            if looks_like_path(token):
                rep.warn(
                    "W5",
                    f"{rep.rel(owner)}: `@{token}` resolves to no file "
                    f"({rep.rel(target)}) — the import is silently dropped",
                )
            continue
        if depth + 1 > MAX_IMPORT_DEPTH:
            rep.warn(
                "W5",
                f"{rep.rel(owner)}: `@{token}` is hop {depth + 1} — the harness "
                f"stops at {MAX_IMPORT_DEPTH}, so it never loads",
            )
            continue
        tokens = measure(read(target))[1]
        if target.name.lower() == "index.md":
            rep.refuse(
                "R2",
                f"{rep.rel(owner)}: imports `@{token}` — an index.md is a manifest "
                "for a tool, never a read path; reach the corpus through its schema "
                "file and let a query name the pages",
            )
            continue
        if tokens > COMPACTION_TOKEN_LIMIT:
            rep.refuse(
                "R2",
                f"{rep.rel(owner)}: imports `@{token}` (~{tokens} tokens) — over "
                f"{COMPACTION_TOKEN_LIMIT}, so after compaction it comes back as a "
                "path reference with no content; make it a pointer, not an import",
            )
            continue
        add(target, "import", depth + 1, rep.rel(owner))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="claude-md-check.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--repo", help="repo root (default: git toplevel of the cwd)")
    ap.add_argument(
        "--budget",
        type=int,
        default=None,
        help=f"CLAUDE.md line budget (default {CLAUDE_MAX_LINES})",
    )
    ap.add_argument(
        "--canonical",
        action="store_true",
        help=f"claude-meta itself: raise the CLAUDE.md budget to {CANONICAL_MAX_LINES}",
    )
    ap.add_argument(
        "--total-budget",
        type=int,
        default=STARTUP_MAX_LINES,
        help=f"startup-set line budget (default {STARTUP_MAX_LINES})",
    )
    ap.add_argument(
        "--strict",
        action="store_true",
        help="every warning refuses, staged or not (CI, or a session audit)",
    )
    ap.add_argument("--json", action="store_true", help="print findings as JSON")
    args = ap.parse_args(argv)

    repo = Path(args.repo).resolve() if args.repo else default_repo()
    budget = args.budget or (CANONICAL_MAX_LINES if args.canonical else CLAUDE_MAX_LINES)

    rep = Report(repo, args.strict)
    files = collect_startup(repo, rep)
    loaded = [f for f in files if f["kind"] != "rule-scoped"]
    total_lines = sum(f["lines"] for f in loaded)
    total_tokens = sum(f["tokens"] for f in loaded)
    listing = listing_estimate(repo)

    claude = next((f for f in files if f["kind"] == "claude-md"), None)
    if claude is not None:
        path = repo / claude["path"]
        text = read(path)
        n_fences = fences_in(text)
        if n_fences:
            rep.refuse(
                "R1",
                f"{claude['path']}: {n_fences} fenced code block(s) — a procedure "
                "here is re-read and re-judged on every task; move it to the skill "
                "that owns it and leave one invocation behind",
            )
        if claude["lines"] > budget:
            rep.warn(
                "W1",
                f"{claude['path']}: {claude['lines']} lines — over {budget}; length "
                "is the symptom, retirement the remedy: move a line that is not true "
                "for every task one loading level down",
            )
        for title, missing in ledger_entries(text):
            if missing:
                rep.warn(
                    "W3",
                    f"{claude['path']}: ledger entry `{title}` has no "
                    + ", ".join(f"`{m}`" for m in missing)
                    + " — an entry without a retire condition is never retired "
                    "(`since` may name a date or a model ID)",
                )
    if total_lines > args.total_budget:
        rep.warn(
            "W2",
            f"startup set: {total_lines} lines across {len(loaded)} file(s) — over "
            f"{args.total_budget}; every line is charged to every task in this repo",
        )

    if args.json:
        print(
            json.dumps(
                {
                    "repo": str(repo),
                    "budget": budget,
                    "total_budget": args.total_budget,
                    "startup": files,
                    "totals": {"lines": total_lines, "tokens": total_tokens},
                    "listing": listing,
                    "refusals": rep.refusals,
                    "warnings": rep.warnings,
                    "ok": not rep.refusals,
                },
                indent=2,
            )
        )
        return 1 if rep.refusals else 0

    print(
        f"claude-md-check: {repo}"
        f"{' [canonical]' if args.canonical else ''}"
        f"{' [strict]' if args.strict else ''}"
    )
    for f in files:
        via = f" ← {f['via']}" if f["via"] else ""
        note = " (conditional — not counted)" if f["kind"] == "rule-scoped" else ""
        print(
            f"  {f['path']:<44} {f['lines']:>4} lines  ~{f['tokens']:>5} tok  "
            f"[{f['kind']}]{via}{note}"
        )
    print(
        f"  {'startup set':<44} {total_lines:>4} lines  ~{total_tokens:>5} tok  "
        f"(budget {args.total_budget}; CLAUDE.md budget {budget})"
    )
    print(
        f"  {'+ skill/command listing (harness)':<44} {'—':>4}        "
        f"~{listing['tokens']:>5} tok  ({listing['entries']} entries, not in these files)"
    )
    for line in rep.refusals:
        print(f"REFUSE {line}")
    for line in rep.warnings:
        print(f"WARN {line}")
    print(
        f"claude-md-check: {len(rep.refusals)} refusal(s), {len(rep.warnings)} "
        f"warning(s) — {'FAIL' if rep.refusals else 'pass'}"
    )
    return 1 if rep.refusals else 0


if __name__ == "__main__":
    sys.exit(main())
