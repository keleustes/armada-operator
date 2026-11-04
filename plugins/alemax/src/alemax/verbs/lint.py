"""`alemax lint` — run the claude-artifact checkers and print one summary.

Does no checking of its own. It answers the two questions a caller would otherwise
answer by inference — where the checkers are, and whether this is canonical — then runs
them and gets out of the way. Each checker's output is printed verbatim; this never
rewrites a message.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

from ..io import ERROR, OK
from ..repo import toplevel

# verb -> [(checker, extra args, extra args when canonical)]
CHECKS: dict[str, list[tuple[str, list[str], list[str]]]] = {
    "docs": [
        ("check-doc-set.py", [], []),
        ("claude-md-check.py", [], ["--canonical"]),
        ("change-triad-check.py", [], []),
        ("spec-summary-check.py", [], []),
    ],
    "skills": [
        ("skill-check.py", [], []),
        ("path-literal-check.py", [], []),
    ],
    # spec toolchain-versions: every declared Python/Go/Java version against the minimum,
    # every crate's pin, the golangci-lint schema. Warnings unless --strict.
    "toolchain": [
        ("toolchain-check.py", [], []),
    ],
}
# A project carries them at bin/; canonical authors them at scaffolding/templates/bin/
# and has no bin/ of its own. Whichever holds them wins.
CHECKER_DIRS = ("bin", "scaffolding/templates/bin")
COUNTS_RE = re.compile(r"(\d+) refusal\(s\), (\d+) warning\(s\)")


def find_checker_dir(repo: Path) -> Path | None:
    wanted = {name for group in CHECKS.values() for name, _, _ in group}
    for rel in CHECKER_DIRS:
        candidate = repo / rel
        if candidate.is_dir() and any((candidate / n).is_file() for n in wanted):
            return candidate
    return None


def is_canonical_layout(repo: Path) -> bool:
    """The two things only the meta-repo has. Raises the CLAUDE.md budget 120 → 200."""
    return (repo / "scaffolding" / "propagation-policy.yaml").is_file() and (
        repo / "meta" / "bootstrap"
    ).is_dir()


def run_checks(a: argparse.Namespace, which: list[str]) -> int:
    repo = Path(a.repo).resolve() if a.repo else toplevel()
    checker_dir = find_checker_dir(repo)
    if checker_dir is None:
        print(
            f"alemax lint: no checkers under {repo} ({' or '.join(CHECKER_DIRS)}) — a project "
            "gets them from the class-M set; run /alemax:complete-update",
            file=sys.stderr,
        )
        return ERROR

    canonical = is_canonical_layout(repo)
    planned = [(n, e, c) for v in which for n, e, c in CHECKS[v]]
    budget = "200" if canonical else "120"
    mode = "strict (every finding refuses)" if a.strict else "report-only (--strict to gate)"
    print(f"alemax lint: {repo}")
    print(
        f"alemax lint: {'canonical' if canonical else 'project'} — checkers at "
        f"{checker_dir.relative_to(repo)}/, CLAUDE.md budget {budget} lines, {mode}"
        f"{', specs included' if a.include_specs else ''}"
    )
    if a.list:
        for name, extra, canon in planned:
            state = "installed" if (checker_dir / name).is_file() else "NOT INSTALLED"
            print(f"  {name} {' '.join(extra + (canon if canonical else []))} [{state}]")
        return OK

    rows: list[tuple[str, str]] = []
    failed = False
    n_refuse = n_warn = 0
    for name, extra, canon in planned:
        script = checker_dir / name
        if not script.is_file():
            # Never a failure: a project gets the new ones on its next class-M delivery.
            rows.append((name, "not installed — skipped"))
            continue
        cmd = [sys.executable, str(script), "--repo", str(repo), *extra]
        if canonical:
            cmd += canon
        if a.strict:
            cmd.append("--strict")
        if a.include_specs and name == "path-literal-check.py":
            cmd.append("--include-specs")
        print(f"\n===== {name} =====")
        done = subprocess.run(cmd, capture_output=True, text=True, check=False)
        out = (done.stdout or "") + (done.stderr or "")
        print(out.rstrip())
        if counts := COUNTS_RE.search(out):
            n_refuse += int(counts.group(1))
            n_warn += int(counts.group(2))
            verdict = f"{counts.group(1)} refusal(s), {counts.group(2)} warning(s)"
        else:
            verdict = f"exit {done.returncode}"
        rows.append((name, ("FAIL — " if done.returncode else "pass — ") + verdict))
        failed = failed or bool(done.returncode)

    width = max(len(n) for n, _ in rows)
    print(f"\n===== alemax lint {'+'.join(which)} =====")
    for name, verdict in rows:
        print(f"  {name.ljust(width)}  {verdict}")
    total = f"{n_refuse} refusal(s), {n_warn} warning(s) in total"
    if failed:
        print(f"alemax lint: FAIL — at least one checker refused; {total}")
    elif n_warn:
        print(
            f"alemax lint: pass — {total}. A warning is a finding that did not gate this run; "
            "--strict makes every one of them refuse."
        )
    else:
        print(f"alemax lint: pass — {total}. Nothing to act on.")
    return ERROR if failed else OK


def cmd_docs(a):
    return run_checks(a, ["docs"])


def cmd_skills(a):
    return run_checks(a, ["skills"])


def cmd_toolchain(a):
    return run_checks(a, ["toolchain"])


def cmd_all(a):
    return run_checks(a, ["docs", "skills", "toolchain"])


SUBCOMMANDS = {
    "docs": (cmd_docs, "the three-doc set, the context budget, intent · spec · plan"),
    "skills": (cmd_skills, "the thin-skill contract, double listings, resolved absolute paths"),
    "toolchain": (cmd_toolchain, "declared language versions against the minimum, crate pins"),
    "all": (cmd_all, "all three sets, one summary"),
}


def register(ap: argparse.ArgumentParser) -> None:
    subs = ap.add_subparsers(dest="subcommand", required=True, metavar="SUBCOMMAND")
    for name, (fn, help_text) in SUBCOMMANDS.items():
        sp = subs.add_parser(name, help=help_text)
        sp.add_argument("--repo", help="repo root (default: the git toplevel of the cwd)")
        sp.add_argument(
            "--strict",
            action="store_true",
            help="every finding refuses, not only staged ones — the gate mode",
        )
        sp.add_argument(
            "--include-specs",
            action="store_true",
            help="widen path-literal-check.py to openspec/specs/**",
        )
        sp.add_argument("--list", action="store_true", help="print what would run and exit")
        sp.add_argument("--json", action="store_true", help="accepted for symmetry; unused here")
        sp.set_defaults(func=fn)
