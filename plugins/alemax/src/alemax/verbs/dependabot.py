"""dependabot_merge.py — the deterministic half of `/alemax:dependabot-merge` and `…-merge-all`
(spec `alemax-dependabot-skills`).

    dependabot_merge.py <pr> [<pr> …] [--apply]     one or more Dependabot PRs, in order
    dependabot_merge.py --all [--apply]             every open Dependabot PR, oldest first
    dependabot_merge.py --checks-only <pr>          only the red-check verdicts (any PR)

Dry-run by default: prints what it would do and acts on nothing. `--apply` posts the
`@dependabot rebase` comment, polls, and squash-merges (`gh pr merge --squash --delete-branch`).

Per PR: refuses a non-Dependabot author (the whole batch, before acting); skips a closed PR;
merges when `mergeable=MERGEABLE` and `mergeStateStatus=CLEAN`; on `UNKNOWN`, `DIRTY` or
`BEHIND` posts `@dependabot rebase` once and polls every `--interval` seconds up to
`--timeout` (GitHub stops recomputing mergeability after about a week — the rebase makes it
recompute); stops on a conflict that survives the rebase, on `BLOCKED`, or on a red check.
Merging one PR flips the next one touching the same file to `DIRTY` (context drift), which
is why a batch simply runs the same loop per PR, in order, and stops at the first stop.

**A red check is a code failure only after the run executed** (CLAUDE.md ledger entry 6):
before any red check is reported, the script finds the workflow run for the PR's head SHA
(`gh run list`, `gh run view --json jobs`) and says whether a step actually ran. No run, or a
run in which no job completed a single step, is reported as *never executed — an exhausted
Actions pool or disabled workflows, not a code defect; wait for the reset*. Only a run with
a step that ran and failed is reported as a code failure to diagnose.

Output: one line per state change, then per PR `merged <sha>` / `would merge` /
`stopped: <reason>` / `skipped: <reason>`, and a batch summary. Exit 0 when nothing stopped,
1 on a stop or a refusal, 2 on usage or preflight. Needs `gh` (authenticated) and `git`.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

from ..io import die

DEPENDABOT_LOGINS = {"app/dependabot", "dependabot[bot]", "dependabot"}
REBASE_STATES = {"UNKNOWN", "DIRTY", "BEHIND"}
PR_FIELDS = (
    "number,title,author,state,isDraft,mergeStateStatus,mergeable,headRefName,headRefOid,url"
)


class Gh:
    def __init__(self, repo: str | None) -> None:
        self.repo = repo

    def run(self, *args: str, check: bool = True) -> tuple[int, str, str]:
        cmd = ["gh", *args]
        if self.repo and args and args[0] in ("pr", "run"):
            cmd += ["--repo", self.repo]
        try:
            done = subprocess.run(cmd, capture_output=True, text=True)
        except OSError as exc:
            die(f"cannot run gh: {exc}")
        if check and done.returncode != 0:
            die(f"`{' '.join(cmd)}` failed: {done.stderr.strip() or done.stdout.strip()}", 1)
        return done.returncode, done.stdout, done.stderr

    def json(self, *args: str, check: bool = True):
        _, out, _ = self.run(*args, check=check)
        try:
            return json.loads(out or "null")
        except ValueError:
            die(f"unparseable JSON from gh {' '.join(args[:3])}", 1)


def preflight(gh: Gh) -> None:
    rc, _, err = gh.run("auth", "status", check=False)
    if rc != 0:
        die(f"gh is not authenticated: {err.strip()}")
    if gh.repo is None:
        try:
            subprocess.run(
                ["git", "remote", "get-url", "origin"],
                check=True,
                capture_output=True,
                text=True,
                cwd=str(Path.cwd()),
            )
        except OSError, subprocess.CalledProcessError:
            die("no git remote `origin` here — pass --repo OWNER/REPO")


def pr_view(gh: Gh, n: int) -> dict:
    return gh.json("pr", "view", str(n), "--json", PR_FIELDS)


def is_dependabot(info: dict) -> bool:
    login = (info.get("author") or {}).get("login", "")
    return login in DEPENDABOT_LOGINS or login.startswith("dependabot")


# --- the run-executed verdict (ledger entry 6) --------------------------------


def check_verdicts(gh: Gh, n: int, info: dict) -> tuple[list[str], bool]:
    """Return (lines, any_pending). Each red check gets a verdict: never executed vs executed."""
    lines: list[str] = []
    checks = (
        gh.json("pr", "checks", str(n), "--json", "name,state,bucket,link,workflow", check=False)
        or []
    )
    pending = any(c.get("bucket") == "pending" for c in checks)
    red = [c for c in checks if c.get("bucket") in ("fail", "cancel")]
    if not checks:
        lines.append(f"#{n}: no checks reported for this PR")
        return lines, False
    if not red:
        lines.append(
            f"#{n}: checks — {len(checks)} reported, none red"
            + (", some pending" if pending else "")
        )
        return lines, pending
    sha = info.get("headRefOid", "")
    runs = (
        gh.json(
            "run",
            "list",
            "--branch",
            info.get("headRefName", ""),
            "--limit",
            "30",
            "--json",
            "databaseId,status,conclusion,workflowName,headSha",
            check=False,
        )
        or []
    )
    runs = [r for r in runs if r.get("headSha") == sha]
    if not runs:
        lines.append(
            f"#{n}: {len(red)} red check(s) but NO workflow run recorded for {sha[:7]} — Actions never started "
            "(exhausted pool or disabled workflows), not a code defect; wait for the monthly reset (CLAUDE.md ledger 7)"
        )
        return lines, pending
    for r in runs:
        rid = r.get("databaseId")
        detail = (
            gh.json("run", "view", str(rid), "--json", "status,conclusion,jobs", check=False) or {}
        )
        jobs = detail.get("jobs") or []
        executed_step = None
        for job in jobs:
            for step in job.get("steps") or []:
                if step.get("status") == "completed" and step.get("conclusion") in (
                    "success",
                    "failure",
                ):
                    executed_step = (job.get("name"), step.get("name"))
                    break
            if executed_step:
                break
        failed_at = None
        for job in jobs:
            if job.get("conclusion") == "failure":
                for step in job.get("steps") or []:
                    if step.get("conclusion") == "failure":
                        failed_at = (job.get("name"), step.get("name"))
                        break
                if failed_at:
                    break
        label = f"run {rid} ({r.get('workflowName')}, {r.get('status')}/{r.get('conclusion')})"
        if r.get("status") != "completed":
            lines.append(f"#{n}: {label}: still running — not a verdict yet")
        elif executed_step is None:
            lines.append(
                f"#{n}: {label}: NEVER EXECUTED — no job completed a single step; an exhausted Actions pool or "
                "disabled workflows, not a code defect; wait for the reset, do not touch the code (CLAUDE.md ledger 7)"
            )
        elif failed_at:
            lines.append(
                f'#{n}: {label}: executed — job "{failed_at[0]}" failed at step "{failed_at[1]}"; a code failure to diagnose'
            )
        elif r.get("conclusion") == "success":
            lines.append(f"#{n}: {label}: executed and green")
        else:
            lines.append(
                f"#{n}: {label}: executed, conclusion {r.get('conclusion')} — read the run"
            )
    return lines, pending


# --- one PR ------------------------------------------------------------------


def handle(gh: Gh, n: int, a: argparse.Namespace) -> str:
    """Return 'merged <sha>' | 'would merge' | 'skipped: …' | 'stopped: …'."""
    info = pr_view(gh, n)
    title = info.get("title", "")
    print(f"#{n} {title}")
    if info.get("state") != "OPEN":
        return f"skipped: {info.get('state', '?').lower()}"
    if info.get("isDraft"):
        return "stopped: draft PR"
    rebased = False
    deadline = time.monotonic() + a.timeout
    while True:
        mss, mrg = info.get("mergeStateStatus"), info.get("mergeable")
        print(
            f"  state: mergeStateStatus={mss} mergeable={mrg} head={info.get('headRefOid', '')[:7]}"
        )
        if mrg == "CONFLICTING" and rebased:
            return "stopped: conflict survives the rebase — resolve it by hand"
        if mss == "CLEAN" and mrg == "MERGEABLE":
            if not a.apply:
                return "would merge (squash, delete branch) — re-run with --apply"
            _, out, _ = gh.run("pr", "merge", str(n), "--squash", "--delete-branch")
            merged = pr_view(gh, n)
            sha = (
                (merged.get("mergeCommit") or {}).get("oid")
                if isinstance(merged.get("mergeCommit"), dict)
                else None
            ) or ""
            return f"merged {sha[:7] or out.strip() or 'ok'}"
        if mss in ("BLOCKED", "UNSTABLE"):
            lines, pending = check_verdicts(gh, n, info)
            for ln in lines:
                print("  " + ln)
            if pending and time.monotonic() < deadline:
                print(f"  checks pending — polling again in {a.interval}s")
                if not a.apply:
                    return "stopped: checks pending (dry-run does not wait)"
                time.sleep(a.interval)
                info = pr_view(gh, n)
                continue
            return f"stopped: {mss.lower()} — see the verdict lines above; the script never merges past a red check"
        if mss in REBASE_STATES or mrg == "UNKNOWN":
            if not rebased:
                if not a.apply:
                    return f"would post `@dependabot rebase` (state {mss}/{mrg}) and poll up to {a.timeout}s — re-run with --apply"
                gh.run("pr", "comment", str(n), "--body", "@dependabot rebase")
                print("  posted `@dependabot rebase`")
                rebased = True
                before = info.get("headRefOid")
            if time.monotonic() >= deadline:
                return f"stopped: still {mss}/{mrg} after {a.timeout}s — the bot may be slow or rate-limited; re-run later"
            time.sleep(a.interval)
            info = pr_view(gh, n)
            if info.get("headRefOid") != before and info.get("mergeStateStatus") == "UNKNOWN":
                continue  # the bot pushed; GitHub is recomputing
            continue
        if mss == "DRAFT":
            return "stopped: draft PR"
        if mss == "HAS_HOOKS":
            return "stopped: HAS_HOOKS — a pre-receive hook gates the merge"
        return f"stopped: unexpected state {mss}/{mrg}"


def cmd_merge(a: argparse.Namespace) -> int:
    if not a.prs and not a.all:
        die("give PR number(s) or --all", 2)
    gh = Gh(a.repo)
    preflight(gh)

    targets = list(a.prs)
    if a.all:
        rows = (
            gh.json(
                "pr",
                "list",
                "--author",
                "app/dependabot",
                "--state",
                "open",
                "--limit",
                "50",
                "--json",
                "number",
            )
            or []
        )
        found = sorted(r["number"] for r in rows)
        if not found:
            print("no open Dependabot PRs")
            return 0
        targets += [n for n in found if n not in targets]
    print(
        ("APPLY" if a.apply else "DRY RUN")
        + f" — {len(targets)} PR(s): "
        + " ".join(f"#{n}" for n in targets)
    )

    if a.checks_only:
        stopped = False
        for n in targets:
            info = pr_view(gh, n)
            lines, _ = check_verdicts(gh, n, info)
            for ln in lines:
                print(ln)
            stopped = stopped or any("NEVER EXECUTED" in ln or "code failure" in ln for ln in lines)
        return 1 if stopped else 0

    # Safety gate on the whole set before acting on any.
    refused = []
    for n in targets:
        info = pr_view(gh, n)
        if not is_dependabot(info):
            refused.append(
                f"#{n} is by {(info.get('author') or {}).get('login', '?')}, not Dependabot"
            )
    if refused:
        for r in refused:
            print("refused: " + r)
        print(
            "stopped: the batch contains a non-Dependabot PR; this script only drives `@dependabot rebase` — merge it by hand"
        )
        return 1

    results: dict[int, str] = {}
    for i, n in enumerate(targets):
        results[n] = handle(gh, n, a)
        print(f"  → {results[n]}")
        if results[n].startswith("stopped"):
            for rest in targets[i + 1 :]:
                results[rest] = "untouched: an earlier PR stopped the batch"
            break
    print()
    print("summary:")
    for n, r in results.items():
        print(f"  #{n}: {r}")
    return 1 if any(r.startswith("stopped") for r in results.values()) else 0


def register(ap: argparse.ArgumentParser) -> None:
    ap.add_argument("prs", nargs="*", type=int, help="PR number(s), processed in order")
    ap.add_argument("--all", action="store_true", help="every open Dependabot PR, oldest first")
    ap.add_argument(
        "--apply", action="store_true", help="act (comment, poll, merge); default is a dry run"
    )
    ap.add_argument(
        "--checks-only",
        action="store_true",
        help="print the red-check verdicts for the PR(s) and stop (any author)",
    )
    ap.add_argument(
        "--timeout",
        type=int,
        default=180,
        help="seconds to wait for the bot / checks per PR (default 180)",
    )
    ap.add_argument(
        "--interval", type=int, default=20, help="poll interval in seconds (default 20)"
    )
    ap.add_argument("--repo", help="OWNER/REPO (default: the current repo's origin)")
    ap.set_defaults(func=cmd_merge)
