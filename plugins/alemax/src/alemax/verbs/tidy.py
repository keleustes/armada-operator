"""tidy.py — the deterministic half of /alemax:tidy-aiml.

Drives `meta/scripts/fork-tidy-aiml.sh`, which owns the classification, the
temp-branch build, the tree-equivalence check and the force-push-with-lease.
This script owns what the skill body used to carry as fenced bash: the
preflight, the duplicate-commit classification a fork session must read
before syncing, and a machine-readable view of the reshape plan.

Subcommands
  preflight   context + clean tree + both staleness guards + `git cherry`
              duplicate classification. Exit 0 proceed, 1 blocked.
  preview     `fork-tidy-aiml.sh --dry-run`, parsed into a plan.
              Exit 0 reshape needed, 1 blocked, 3 already tidy.
  apply       `fork-tidy-aiml.sh --yes [--push]`, then the resulting shape.
              Exit 0 applied, 1 refused.

Every subcommand takes --json. Guardrail 1: run this against a real fork
clone, not through a PR — `--dry-run` and `preflight` mutate nothing.
"""

# shipped-path-scope: meta

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from .. import git as gitmod

CANONICAL = "alemaxdesign/claude-meta"
YAML_FILES = ("orgs.yaml", "users.yaml", "repos.yaml", "projects.yaml")
FOUND_RE = re.compile(r"Found (\d+) yaml-only commit\(s\), (\d+) non-yaml commit\(s\)")
MERGE_RE = re.compile(r"\+ (\d+) merge commit\(s\) that will be dropped")
SQUASH_RE = re.compile(r"\+ (\d+) commit\(s\) already upstream .* that will be dropped")
SHA_RE = re.compile(r"^\s*(?:\[INFO\]\s+)?([0-9a-f]{7,40})\s+(.*)$")


def run(*args: str, cwd: Path | None = None) -> tuple[int, str]:
    done = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    return done.returncode, (done.stdout or "") + (done.stderr or "")


def repo_root() -> Path:
    code, out = run("git", "rev-parse", "--show-toplevel")
    if code != 0:
        sys.exit("not a git repository")
    return Path(out.strip())


def per_volume(root: Path, branch: str) -> bool:
    """One authority: fork_is_per_volume_branch in meta/scripts/lib/fork.sh."""
    lib = root / "meta" / "scripts" / "lib" / "fork.sh"
    if not lib.is_file():
        return False
    code, _ = run(
        "bash",
        "-c",
        f'. "{lib}" && fork_is_per_volume_branch "{branch}"',
        cwd=root,
    )
    return code == 0


def preflight(root: Path) -> dict:
    origin = (
        gitmod.probe(root, "remote", "get-url", "origin") or ""
    )  # no remote yet is a state, not a crash
    branch = gitmod.probe(root, "symbolic-ref", "--short", "HEAD") or "<detached>"
    out: dict = {"root": str(root), "origin": origin, "branch": branch, "blocked": []}

    if "claude-meta" not in origin or root.name != "claude-meta":
        out["blocked"].append("not a claude-meta clone — cd to your meta-repo fork")
        return out
    if CANONICAL in origin:
        out["blocked"].append("origin is canonical; canonical has no per-volume branches")
        return out
    if not per_volume(root, branch):
        out["blocked"].append(
            f"branch '{branch}' is not a per-volume operator branch — git checkout <volume-branch>"
        )
        return out

    out["dirty"] = bool(gitmod.probe(root, "status", "--porcelain"))
    if out["dirty"]:
        out["blocked"].append("working tree is dirty — commit, stash or discard first")

    run("git", "fetch", "origin", "--quiet", cwd=root)
    has_upstream = bool(
        gitmod.probe(root, "rev-parse", "--verify", "--quiet", "refs/remotes/upstream/main")
    )
    if has_upstream:
        run("git", "fetch", "upstream", "--quiet", cwd=root)

    behind = gitmod.probe(root, "rev-list", "--count", f"{branch}..origin/main") or "0"
    out["origin_main_ahead_by"] = int(behind)
    if int(behind) > 0:
        out["blocked"].append(
            f"origin/main is {behind} commit(s) ahead of {branch} — "
            "./meta/scripts/fork-sync.sh --non-interactive --push first"
        )

    out["fork_main_behind_canonical_by"] = 0
    if has_upstream:
        gap = gitmod.probe(root, "rev-list", "--count", "origin/main..upstream/main") or "0"
        out["fork_main_behind_canonical_by"] = int(gap)
        if int(gap) > 0:
            out["blocked"].append(
                f"fork main is {gap} commit(s) behind canonical — reshaping now "
                "lands on a STALE base; ./meta/scripts/fork-sync.sh --non-interactive --push first"
            )

    # Duplicates: a commit whose patch is already upstream must be dropped
    # BEFORE the sync, or the reshape replays it as a permanent no-op.
    out["duplicates"], out["unique"] = [], []
    if has_upstream:
        for line in gitmod.probe(root, "cherry", "-v", "upstream/main", branch).splitlines():
            mark, _, rest = line.partition(" ")
            sha, _, subject = rest.strip().partition(" ")
            entry = {"sha": sha[:7], "subject": subject}
            (out["duplicates"] if mark == "-" else out["unique"]).append(entry)
    if out["duplicates"]:
        out["blocked"].append(
            f"{len(out['duplicates'])} commit(s) are already upstream under other SHAs — "
            "reset below the lowest one and cherry-pick back any '+' above it, THEN sync; "
            "syncing first makes the reshape replay them as no-ops"
        )
    return out


def preview(root: Path) -> tuple[int, dict]:
    script = root / "meta" / "scripts" / "fork-tidy-aiml.sh"
    if not script.is_file():
        return 1, {"error": f"{script} not found"}
    code, out = run("bash", str(script), "--dry-run", cwd=root)
    plan: dict = {
        "exit": code,
        "already_tidy": "already tidy" in out,
        "yaml_commits": None,
        "non_yaml_commits": None,
        "merge_commits_dropped": 0,
        "squashed_dropped": 0,
        "dropped": [],
        "output": out.strip().splitlines(),
    }
    if m := FOUND_RE.search(out):
        plan["yaml_commits"], plan["non_yaml_commits"] = int(m[1]), int(m[2])
    if m := MERGE_RE.search(out):
        plan["merge_commits_dropped"] = int(m[1])
    if m := SQUASH_RE.search(out):
        plan["squashed_dropped"] = int(m[1])
    if plan["merge_commits_dropped"] or plan["squashed_dropped"]:
        for line in out.splitlines():
            if (s := SHA_RE.match(line)) and s[1] != s[2]:
                plan["dropped"].append({"sha": s[1][:7], "subject": s[2]})
    if code != 0:
        plan["blocked"] = [
            ln.strip() for ln in out.splitlines() if "ERROR" in ln or "mixed" in ln
        ] or ["fork-tidy-aiml.sh refused; see output"]
        return 1, plan
    if plan["already_tidy"]:
        return 3, plan
    return 0, plan


def apply(root: Path, push: bool) -> tuple[int, dict]:
    script = root / "meta" / "scripts" / "fork-tidy-aiml.sh"
    args = ["bash", str(script), "--yes"] + (["--push"] if push else [])
    code, out = run(*args, cwd=root)
    branch = gitmod.probe(root, "symbolic-ref", "--short", "HEAD")
    shape = [
        {"sha": ln.split(" ", 1)[0], "subject": ln.split(" ", 1)[1]}
        for ln in (
            gitmod.probe(root, "log", "--oneline", f"origin/main..{branch}") or ""
        ).splitlines()
        if " " in ln
    ]
    return (0 if code == 0 else 1), {
        "exit": code,
        "pushed": push and code == 0,
        "branch": branch,
        "shape": shape,
        "output": out.strip().splitlines(),
    }


def emit(as_json: bool, payload: dict, lines: list[str]) -> None:
    print(json.dumps(payload, indent=2) if as_json else "\n".join(lines))


def cmd_preflight(a: argparse.Namespace) -> int:
    r = preflight(repo_root())
    lines = [f"branch={r['branch']} root={r['root']}"]
    if r.get("duplicates"):
        lines.append(f"duplicates already upstream: {len(r['duplicates'])}")
        lines += [f"  - {d['sha']} {d['subject']}" for d in r["duplicates"]]
    if r.get("unique"):
        lines.append(f"fork-local commits: {len(r['unique'])}")
        lines += [f"  + {d['sha']} {d['subject']}" for d in r["unique"]]
    lines += [f"BLOCKED: {b}" for b in r["blocked"]] or ["preflight clear"]
    emit(a.json, r, lines)
    return 1 if r["blocked"] else 0


def cmd_preview(a: argparse.Namespace) -> int:
    code, plan = preview(repo_root())
    if code == 3:
        lines = ["already tidy — nothing to do"]
    elif code == 1:
        lines = [f"BLOCKED: {b}" for b in plan.get("blocked", [plan.get("error", "refused")])]
    else:
        lines = [
            f"{plan['yaml_commits']} yaml commit(s), {plan['non_yaml_commits']} non-yaml "
            f"commit(s) -> origin/main + {', '.join(YAML_FILES)} + non-yaml on top"
        ]
        lines += [f"  dropped: {d['sha']} {d['subject']}" for d in plan["dropped"]]
    emit(a.json, plan, lines)
    return code


def cmd_apply(a: argparse.Namespace) -> int:
    code, res = apply(repo_root(), a.push)
    lines = [f"{'applied' if code == 0 else 'refused'} on {res['branch']}"]
    lines += [f"  {c['sha']} {c['subject']}" for c in res["shape"]]
    if res["pushed"]:
        lines.append("force-pushed with lease to origin")
    elif code == 0:
        lines.append(f"push with: git push --force-with-lease origin {res['branch']}")
    emit(a.json, res, lines)
    return code


def register(ap: argparse.ArgumentParser) -> None:
    sub = ap.add_subparsers(dest="subcommand", required=True, metavar="SUBCOMMAND")
    sub.add_parser("preflight", help="context, staleness guards, duplicate commits")
    sub.add_parser("preview", help="the reshape plan, without touching anything")
    sub.add_parser("apply", help="reshape the branch").add_argument(
        "--push", action="store_true", help="force-push-with-lease after the reshape"
    )
    # --json belongs on each subcommand, so `<cmd> --json` works (the natural form).
    for sp in sub.choices.values():
        sp.add_argument("--json", action="store_true", help="machine-readable output")
    sub.choices["preflight"].set_defaults(func=cmd_preflight)
    sub.choices["preview"].set_defaults(func=cmd_preview)
    sub.choices["apply"].set_defaults(func=cmd_apply)
