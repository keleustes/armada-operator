#!/usr/bin/env python3
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""path-literal-check.py — variables, never resolved paths (claude-meta spec `claude-consistency-lint`).

A document that names a resolved absolute path names ONE machine. Read on any other
drive, or by any other operator, the instruction is silently wrong: the session goes
looking under a volume that is not mounted, or an account that does not exist. The
rule the fleet already holds in prose ("variables, never paths") failed as prose in
code and in skill bodies and held only inside a session; this is the mechanical form.

DEFAULT SCOPE — the instruction-bearing files, where a literal path is a direction a
session follows and a hit means act:

  CLAUDE.md · README.md · architecture.md   at the repo root, any case
  **/SKILL.md                               every skill, both trees, both shapes
  claude/commands/** · rules/** · hooks/**  stubs, path-scoped rules, hook programs
  bin/**                                    the shipped checkers and helpers
  <skill>/scripts/**                        a scripts/ directory beside a SKILL.md

Files scanned: `.md`, `.py`, `.sh`.

`openspec/specs/**` is NOT in the default scope, and the reason is this check's own
first run: 60 of its 61 findings landed there, and the four heaviest files —
`user-environment`, `multi-aiml-drive`, `machine-bootstrap`, `host-isolation` — are
specs whose SUBJECT is drive layout and path resolution. A resolved path in
`user-environment` is a worked example: it is the content, not a mistake, and
"resolve it from a variable" is wrong advice there. `--include-specs` widens to them,
and under it a spec finding WARNS rather than refuses — except one, below.

What counts as a hit — the IDENTITY SEGMENT test. A path rooted at `/Volumes/` or
`/Users/` is read segment by segment; the segment that follows a `Volumes` or a
`Users` component is an *identity segment* — it names one DRIVE, or one ACCOUNT.
The finding is a hit when any identity segment is CONCRETE. A segment is generic,
and passes, when it carries a placeholder or an interpolation:

  a shell/template interpolation   $VAR · ${VAR} · $(whoami) · %VAR% · {{ NAME }}
  an angle-bracket placeholder     <u> · <username> · <your-username>
  a drive-generic spelling         a segment containing NN or XX (AIML0NN)

The interpolation above is spelled with inner spaces on purpose: `broadcast-update.sh`
refuses any class-M file matching the un-spaced form as a bootstrap template, which
blocks the whole fleet broadcast. Detection is character-based, so both spellings pass.

So a placeholder drive with a placeholder account passes, and a resolved drive with a
placeholder account does not: the drive is still one machine's.

Severity follows the file's ROLE, and nothing else. The same string is a defect in
an instruction and content in a specification: `user-environment` names the operator
`slegrand` to state a requirement ABOUT that account, and `host-isolation` names their
Keychains path as the one that must not be accessed. A spec cannot state its own rule
if naming its subject is a refusal, so `openspec/specs/**` warns without exception.
In an instruction-bearing file a hardcoded account
is wrong on every drive but the one it was written on. A concrete DRIVE segment
refuses in the instruction scope and warns in a spec.

A line carrying `path-literal-ok` (an operator-stated exception) or
`path-literal-docs` (the line documents this rule, or is test data) is skipped —
the same line-local idiom `meta/scripts/hooks/system-path-rule-check.sh` already  # shipped-path-provenance
ships, for the same reason: a rule's own worked examples and a self-test's fixtures
are not instructions, and annotating the line is cheaper and more reviewable than
teaching the matcher about docstrings and test bodies.

This does NOT collide with the `system-path-rule` (spec `alemax-skills`, hook
`meta/scripts/hooks/system-path-rule-check.sh`), which requires macOS-mediated paths  # shipped-path-provenance
to be spelled `/Users/$(whoami)/Library/…` LITERALLY rather than through `$HOME`.
`$(whoami)` is an interpolation, so the identity segment is generic and this check
passes it. The two rules meet exactly at the account name and agree on it.

Per-repo opt-out — `.claude/path-literal-allow.txt`, one entry per line, each with a
REQUIRED trailing ` # <reason>`:

  /Volumes/AIML01/   # $HOME is redirected here; the boot-disk path is real   (path-literal-docs)
  README.md          # the bootstrap block the operator types before any var is set

An entry starting with `/` allows every finding whose literal begins with it; any
other entry allows every finding in that repo-relative file or directory prefix.
An entry with no reason is itself a refusal (E1) — an exemption nobody can read is
an exemption nobody can review. Allowed findings are printed with their reason, never
dropped silently.

Exit 1 ("REFUSE") for a refusable hit in a staged file, for every refusable hit with
--strict, and for a reasonless allow entry. Unstaged hits are warnings, so the
pre-commit hook only ever speaks about the commit in front of it. Identical literals
in one file are reported once with every line number. `--json` prints the same
findings as one object. Reads the working tree, edits nothing.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import subprocess
import sys
import tokenize
from pathlib import Path

# The two macOS roots this fleet's paths hang off. `--root` adds another.
DEFAULT_ROOTS = ("Volumes", "Users")
# A component that introduces an identity segment (the next component names a
# drive or an account).
IDENTITY_PARENTS = {"volumes", "users"}
# Anything that makes a segment a placeholder rather than one machine's name.
GENERIC_CHARS = "$<{%*"
GENERIC_TOKENS = ("NN", "XX")
# A match cut short by one of these is a glob, not a path: a bracketed character class.
GLOB_NEXT = {"[", "*", "?"}
# Line-local exception, the idiom `system-path-rule-check.sh` already ships.
MARKER_RE = re.compile(r"path-literal-(?:ok|docs)")
ROOT_DOCS = ("claude.md", "readme.md", "architecture.md")
SCANNED_SUFFIXES = (".md", ".py", ".sh")
# A directory whose contents a session reads as instruction, wherever it sits in the
# tree — so both `.claude/rules/` and `scaffolding/.claude/rules/` match.
INSTRUCTION_DIRS = ("claude/commands/", "claude/rules/", "claude/hooks/")
# `.local/` is the fleet's gitignored operator scratch (spec `scaffolding-boundary`): a session's
# notes and fixtures live there and are nobody's instructions.
SKIP_DIRS = {
    ".git",
    ".local",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
}
ALLOW_FILE = ".claude/path-literal-allow.txt"

# Everything up to whitespace or a delimiter markdown/prose puts after a path.
PATH_TAIL = r"[^\s`'\"()\[\]{},;|<>]*(?:<[^>\s]+>[^\s`'\"()\[\]{},;|<>]*)*"


def path_pattern(roots: tuple[str, ...]) -> re.Pattern[str]:
    alts = "|".join(re.escape(r) for r in roots)
    return re.compile(r"/(?:" + alts + r")/" + PATH_TAIL)


def scope_of(rel: str, repo: Path) -> str | None:
    """`instruction` (a session follows it), `spec` (reference material), or None."""
    low = rel.lower()
    if not low.endswith(SCANNED_SUFFIXES):
        return None
    if "/" not in low and low in ROOT_DOCS:
        return "instruction"
    parts = low.split("/")
    if parts[-1] == "skill.md":
        return "instruction"
    if any(d in low for d in INSTRUCTION_DIRS):
        return "instruction"
    if "bin" in parts[:-1]:
        return "instruction"
    # A `scripts/` directory beside a SKILL.md: the programs a skill body invokes.
    if (
        len(parts) >= 3
        and parts[-2] == "scripts"
        and (repo / Path(rel).parent.parent / "SKILL.md").is_file()
    ):
        return "instruction"
    if low.startswith("openspec/specs/"):
        return "spec"
    return None


def is_generic(seg: str) -> bool:
    if not seg:
        return True
    if any(c in seg for c in GENERIC_CHARS):
        return True
    return any(tok in seg for tok in GENERIC_TOKENS)


def identity_segments(literal: str) -> list[tuple[str, str]]:
    """(kind, segment) for whatever follows a `Volumes` or `Users` component:
    `drive` names one machine's disk, `account` names one operator."""
    parts = [p for p in literal.split("/") if p]
    out = []
    for i, part in enumerate(parts[:-1]):
        low = part.lower()
        if low in IDENTITY_PARENTS:
            out.append(("drive" if low == "volumes" else "account", parts[i + 1]))
    return out


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


def walk(repo: Path, include_specs: bool) -> list[tuple[str, str]]:
    """(rel, scope) for every file to scan, sorted."""
    out: list[tuple[str, str]] = []
    for root, dirs, files in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            rel = os.path.relpath(os.path.join(root, name), repo).replace(os.sep, "/")
            scope = scope_of(rel, repo)
            if scope == "instruction" or (scope == "spec" and include_specs):
                out.append((rel, scope))
    return sorted(out)


def load_allow(repo: Path, path: Path) -> tuple[list[tuple[str, str]], list[str]]:
    """Return (entries, errors). Each entry is (pattern, reason)."""
    entries: list[tuple[str, str]] = []
    errors: list[str] = []
    if not path.is_file():
        return entries, errors
    for n, raw in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        pattern, sep, reason = line.partition("#")
        pattern, reason = pattern.strip(), reason.strip()
        if not pattern:
            continue
        if not sep or not reason:
            rel = path.relative_to(repo) if path.is_relative_to(repo) else path
            errors.append(
                f"E1: {rel}:{n}: `{pattern}` has no ` # <reason>` — an exemption nobody can read is one nobody can review"
            )
            continue
        entries.append((pattern, reason))
    return entries, errors


def allowed_by(entries: list[tuple[str, str]], rel: str, literal: str) -> str | None:
    for pattern, reason in entries:
        if pattern.startswith("/"):
            if literal.startswith(pattern):
                return reason
        elif rel == pattern or rel.startswith(pattern.rstrip("/") + "/"):
            return reason
    return None


def marker_covered_lines(text: str, rel: str) -> set[int]:
    """The 1-based lines a `path-literal-ok` marker exempts.

    The marker used to exempt only the line carrying it, which made it a hostage to
    formatting: any tool that rewrapped a call moved the marker off the literal it
    was placed for. `ruff format` did exactly that to `scope-guard.py`'s self-test
    fixtures — the marker landed on the closing paren, one line below the literals —
    and meta's own gate began refusing meta's own file.

    So in Python a marker covers the whole LOGICAL statement it sits in: put it on
    the closing paren of a wrapped call and it still exempts every literal inside.
    Elsewhere (`.md`, `.sh`) it stays line-local — there is no cheap, correct notion
    of a continued statement in those, and guessing one would exempt more than asked.
    """
    covered: set[int] = set()
    for n, line in enumerate(text.splitlines(), 1):
        if MARKER_RE.search(line):
            covered.add(n)
    if not covered or not rel.endswith(".py"):
        return covered

    try:
        first: int | None = None
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type in (tokenize.NL, tokenize.INDENT, tokenize.DEDENT, tokenize.ENCODING):
                continue
            if tok.type == tokenize.NEWLINE:
                if first is not None and any(first <= c <= tok.end[0] for c in covered):
                    covered.update(range(first, tok.end[0] + 1))
                first = None
                continue
            if first is None and tok.type != tokenize.COMMENT:
                first = tok.start[0]
    except tokenize.TokenError, IndentationError, SyntaxError:
        # Unparseable file: fall back to the line-local behaviour rather than
        # exempting a span we could not establish.
        pass
    return covered


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="path-literal-check.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--repo", help="repo root (default: git toplevel of the cwd, else the cwd)")
    ap.add_argument("--strict", action="store_true", help="refuse for every file, staged or not")
    ap.add_argument("--no-git", action="store_true", help="do not ask git for the staged set")
    ap.add_argument(
        "--root",
        action="append",
        default=[],
        help=f"an extra absolute root to scan (repeatable); default {' · '.join(DEFAULT_ROOTS)}",
    )
    ap.add_argument("--allow-file", help=f"the opt-out file (default {ALLOW_FILE} under the repo)")
    ap.add_argument(
        "--include-specs",
        action="store_true",
        help="also scan openspec/specs/** (off by default; there a drive literal warns and only an account refuses)",
    )
    ap.add_argument("--json", action="store_true", help="print the findings as one JSON object")
    args = ap.parse_args(argv)

    repo = Path(args.repo).resolve() if args.repo else default_repo()
    roots = DEFAULT_ROOTS + tuple(args.root)
    pattern = path_pattern(roots)
    allow_path = Path(args.allow_file) if args.allow_file else repo / ALLOW_FILE
    entries, errors = load_allow(repo, allow_path)

    staged: set[str] = set()
    if not args.no_git:
        out = git(repo, "diff", "--cached", "--name-only", "-z")
        staged = {p for p in (out or "").split("\0") if p}

    files = walk(repo, args.include_specs)
    scopes = dict(files)
    n_marked = 0
    # (rel, literal) -> [line numbers]
    hits: dict[tuple[str, str], list[int]] = {}
    for rel, _scope in files:
        try:
            text = (repo / rel).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        covered = marker_covered_lines(text, rel)
        for n, line in enumerate(text.splitlines(), 1):
            marked = n in covered
            for m in pattern.finditer(line):
                if line[m.end() : m.end() + 1] in GLOB_NEXT:
                    continue  # a bracketed character class is a pattern, not one machine's path
                literal = m.group(0).rstrip(".,:;")
                if all(is_generic(seg) for _kind, seg in identity_segments(literal)):
                    continue
                if marked:
                    n_marked += 1
                    continue  # the line declares itself documentation of the rule, or test data
                hits.setdefault((rel, literal), []).append(n)

    refusals: list[str] = list(errors)
    warnings: list[str] = []
    allowed: list[str] = []
    records: list[dict[str, object]] = []

    for (rel, literal), lines in sorted(hits.items()):
        where = ", ".join(str(n) for n in lines)
        concrete = [(kind, seg) for kind, seg in identity_segments(literal) if not is_generic(seg)]
        scope = scopes.get(rel, "instruction")
        # Severity follows the file's ROLE and nothing else. The same string is a defect
        # in an instruction and content in a specification: `user-environment` names the
        # operator `slegrand` to state a requirement ABOUT that account, and
        # `host-isolation` names their Keychains path as the one that must not be
        # accessed. A spec cannot state its own rule if naming its subject is a refusal.
        refusable = scope == "instruction"
        named = " and ".join(f"{seg} ({kind})" for kind, seg in concrete)
        tail = "" if refusable else " [spec: reference material, so this warns]"
        msg = f"{rel}:{where}: `{literal}` names {named} — resolve it from a variable, or add an entry with a reason to {ALLOW_FILE}{tail}"
        reason = allowed_by(entries, rel, literal)
        if reason is not None:
            allowed.append(f"{rel}:{where}: `{literal}` — {reason}")
            state = "allowed"
        elif refusable and (args.strict or rel in staged):
            refusals.append(f"P1: {msg}")
            state = "refuse"
        else:
            warnings.append(f"P1: {msg}")
            state = "warn"
        records.append(
            {
                "file": rel,
                "scope": scope,
                "lines": lines,
                "literal": literal,
                "identity": [{"kind": k, "segment": s} for k, s in concrete],
                "refusable": refusable,
                "state": state,
                "reason": reason,
            }
        )

    if args.json:
        print(
            json.dumps(
                {
                    "repo": str(repo),
                    "files_scanned": len(files),
                    "include_specs": args.include_specs,
                    "marker_skipped": n_marked,
                    "roots": list(roots),
                    "allow_file": str(allow_path.relative_to(repo))
                    if allow_path.is_relative_to(repo)
                    else str(allow_path),
                    "allow_entries": [{"pattern": p, "reason": r} for p, r in entries],
                    "allow_errors": errors,
                    "findings": records,
                    "refusals": len(refusals),
                    "warnings": len(warnings),
                    "allowed": len(allowed),
                },
                indent=2,
            )
        )
        return 1 if refusals else 0

    n_spec = sum(1 for _r, s in files if s == "spec")
    print(
        f"path-literal-check: {repo} — {len(files)} file(s) in scope"
        + (
            f" ({len(files) - n_spec} instruction + {n_spec} spec)"
            if n_spec
            else " (instruction-bearing; --include-specs adds openspec/specs/**)"
        )
        + f", roots {' · '.join(roots)}"
        + (f", {len(entries)} allow entr(ies)" if entries else "")
        + (f", {n_marked} line(s) marked path-literal-ok/docs" if n_marked else "")
        + f"{' [strict]' if args.strict else ''}"
    )
    for line in refusals:
        print(f"REFUSE {line}")
    for line in warnings:
        print(f"WARN {line}")
    for line in allowed:
        print(f"ALLOWED {line}")
    print(
        f"path-literal-check: {len(refusals)} refusal(s), {len(warnings)} warning(s), {len(allowed)} allowed — {'FAIL' if refusals else 'pass'}"
        + (
            ""
            if args.strict or refusals
            else " (unstaged findings are warnings; --strict refuses them all)"
        )
    )
    return 1 if refusals else 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    sys.exit(main())
