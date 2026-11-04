"""broadcast.py — the deterministic half of /alemax:update-skills.

Resolves WHICH class-M artifacts a broadcast ships and whether that set is
complete, then hands the list to `meta/scripts/broadcast-update.sh`. Meta
stages; it never applies (Guardrail 4) — nothing here touches a project's
`main`, and `broadcast-update.sh` opens no PR by design.

Subcommands
  preflight  fork claude-meta clone, clean tree, gh/git present, and a
             populated `projects.yaml` (an empty manifest means canonical or a
             PR branch — there is no fleet to broadcast to). Exit 0/1.
  plan       the `--only` path list plus COMPLETE vs PARTIAL, which is what
             decides whether each project's `.meta-version` advances.
             Exit 0 paths resolved, 1 blocked, 3 nothing to ship.
  run        invoke broadcast-update.sh with the resolved paths. Exit 0/1.

Both selectors are optional and combine: `--since <ref>` narrows to class-M
`.claude` artifacts changed since that ref; `--path <p>` (repeatable) adds an
explicit shipped path. Neither → the COMPLETE class-M set computed from
`scaffolding/propagation-policy.yaml`, which is the only default that includes
the class-M *templates* (ci.yml and friends). A glob over `scaffolding/.claude/`
omits them, and projects ran dead CI gates for months because of it.

The propagation libs are sourced under **bash**, never the caller's shell: in
zsh `prop_complete_class_m_set` silently under-reports the set (6 paths where
bash finds 50), which would report PARTIAL as COMPLETE and stamp a pin on
projects that never received the files.
"""

# shipped-path-scope: meta

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from .. import git as gitmod
from ..io import die

CANONICAL = "alemaxdesign/claude-meta"
# The `--only` form is the destination path minus its harness prefix, because that is
# what broadcast-update.sh's roots consume. One entry per root there.
SCOPES = (".claude/", ".agents/")
SRC_SCOPES = ("scaffolding/.claude/", "scaffolding/.agents/")
# Shipped from OUTSIDE scaffolding/, so `--since` misses it unless named: source path and
# destination path are identical (`plugins/alemax/src/...` both ends), which is the point —
# the repo holds one copy of the package rather than a source plus a rendered mirror.
SRC_VERBATIM = ("plugins/alemax/src/", "plugins/alemax/pyproject.toml")
STATUS_RE = re.compile(r"^    status: (\S+)\s*$")


def run(*args: str, cwd: Path | None = None) -> tuple[int, str]:
    done = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    return done.returncode, (done.stdout or "") + (done.stderr or "")


def meta_root() -> Path:
    top = gitmod.probe(Path.cwd(), "rev-parse", "--show-toplevel")
    if not top:
        die("not a git repository")
    return Path(top)


def bash_prop(root: Path, snippet: str) -> tuple[int, str]:
    """Source the propagation libs under bash — see the module docstring."""
    script = (
        "set -euo pipefail\n"
        f'source "{root}/meta/bootstrap/lib/common.sh"\n'
        f'source "{root}/meta/bootstrap/lib/propagation.sh"\n'
        f"{snippet}\n"
    )
    return run("bash", "-c", script, cwd=root)


def active_count(root: Path) -> int:
    path = root / "projects.yaml"
    if not path.is_file():
        return 0
    return sum(
        1
        for line in path.read_text(encoding="utf-8").splitlines()
        if (m := STATUS_RE.match(line)) and m[1] == "active"
    )


def preflight(root: Path) -> dict:
    origin = (
        gitmod.probe(root, "remote", "get-url", "origin") or ""
    )  # no remote yet is a state, not a crash
    out: dict = {"root": str(root), "origin": origin, "blocked": []}
    if "claude-meta" not in origin or root.name != "claude-meta":
        out["blocked"].append("context: claude-meta-only — cd to your meta-repo clone")
        return out
    if CANONICAL in origin:
        out["blocked"].append(
            "origin is canonical — broadcast reads projects.yaml, which is fork-divergent; "
            "run from your fork clone on its per-volume branch"
        )
        return out
    if gitmod.probe(root, "status", "--porcelain"):
        out["blocked"].append("working tree is dirty — commit or stash first")
    out["missing_tools"] = [t for t in ("gh", "git") if not shutil.which(t)]
    if out["missing_tools"]:
        out["blocked"].append(f"not on PATH: {', '.join(out['missing_tools'])}")
    out["active_projects"] = active_count(root)
    if out["active_projects"] == 0:
        out["blocked"].append(
            "projects.yaml has no active projects — an empty manifest means canonical or a PR "
            "branch; broadcast from your per-volume branch, where the fleet lives"
        )
    return out


def to_only(dest: str) -> str:
    """A destination path in its `--only` scope-relative form."""
    for scope in SCOPES:
        if dest.startswith(scope):
            return dest[len(scope) :]
    return dest  # template → project root


def plan(root: Path, since: str | None, extra: list[str]) -> tuple[int, dict]:
    dests: list[str] = []
    if since:
        for f in gitmod.probe(
            root, "diff", "--name-only", since, "--", *SRC_SCOPES, *SRC_VERBATIM
        ).splitlines():
            if f.startswith(SRC_VERBATIM):
                dests.append(f)
                continue
            for src in SRC_SCOPES:
                if f.startswith(src):
                    dests.append(f.replace("scaffolding/", "", 1))
    else:
        code, out = bash_prop(root, 'prop_complete_class_m_set "$PWD"')
        if code != 0:
            return 1, {"blocked": [f"prop_complete_class_m_set failed: {out.strip()}"]}
        dests = [ln.strip() for ln in out.splitlines() if ln.strip()]

    paths = list(dict.fromkeys([to_only(d) for d in dests] + [p for p in extra if p]))
    if not paths:
        return 3, {
            "paths": [],
            "dests": dests,
            "complete": False,
            "note": "nothing to ship for that selector",
        }

    # Completeness compares DESTINATION paths, never the --only forms.
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
        fh.write("\n".join(dests) + "\n")
        delivered = fh.name
    code, out = bash_prop(root, f'prop_missing_from_complete_set "$PWD" "{delivered}"')
    Path(delivered).unlink(missing_ok=True)
    missing = [ln.strip() for ln in out.splitlines() if ln.strip()] if code == 0 else []
    return 0, {
        "paths": paths,
        "dests": dests,
        "complete": code == 0 and not missing,
        "missing": missing,
        "selector": f"--since {since}" if since else "complete class-M set",
    }


def cmd_preflight(a) -> int:
    r = preflight(meta_root())
    if a.json:
        print(json.dumps(r, indent=2))
    else:
        print(f"root={r['root']} active_projects={r.get('active_projects', '?')}")
        for b in r["blocked"]:
            print(f"BLOCKED: {b}")
        if not r["blocked"]:
            print("preflight clear")
    return 1 if r["blocked"] else 0


def cmd_plan(a) -> int:
    code, p = plan(meta_root(), a.since, a.path or [])
    if a.json:
        print(json.dumps(p, indent=2))
        return code
    for b in p.get("blocked", []):
        print(f"BLOCKED: {b}")
    if code == 1:
        return 1
    if code == 3:
        print(p["note"])
        return 3
    print(f"selector: {p['selector']}  ->  {len(p['paths'])} path(s)")
    for path in p["paths"]:
        print(f"  {path}")
    if p["complete"]:
        print("COMPLETE — each delivered project's .meta-version WILL advance")
    else:
        head = ", ".join(p["missing"][:6]) or "unknown"
        more = f" (+{len(p['missing']) - 6} more; --json for all)" if len(p["missing"]) > 6 else ""
        print(f"PARTIAL — the pin will NOT advance; absent: {head}{more}")
    return 0


def cmd_run(a) -> int:
    root = meta_root()
    code, p = plan(root, a.since, a.path or [])
    if code != 0:
        print(json.dumps(p, indent=2) if a.json else p.get("note", "nothing to ship"))
        return code
    script = root / "meta" / "scripts" / "broadcast-update.sh"
    if not script.is_file():
        die(f"{script} not found")
    argv = ["bash", str(script)]
    for path in p["paths"]:
        argv += ["--only", path]
    argv += ["--message", a.message]
    if a.dry_run:
        argv.append("--dry-run")
    rc = subprocess.run(argv, cwd=str(root)).returncode
    if a.json:
        print(
            json.dumps(
                {"exit": rc, "paths": p["paths"], "complete": p["complete"], "dry_run": a.dry_run},
                indent=2,
            )
        )
    return 0 if rc == 0 else 1


def add_selectors(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--since", metavar="REF", help="only class-M .claude artifacts changed since REF"
    )
    p.add_argument(
        "--path", action="append", metavar="P", help="explicit shipped path (repeatable)"
    )


def register(ap: argparse.ArgumentParser) -> None:
    sub = ap.add_subparsers(dest="subcommand", required=True)
    sub.add_parser("preflight", help="clone, tree, tools and a populated manifest")
    add_selectors(sub.add_parser("plan", help="the --only list, and COMPLETE vs PARTIAL"))
    r = sub.add_parser("run", help="stage the delivery on every active project")
    add_selectors(r)
    r.add_argument("--message", required=True, help="the delivery message")
    r.add_argument("--dry-run", action="store_true", help="print what would be staged")
    # --json belongs on each subcommand, so `<cmd> --json` works (the natural form).
    for sp in sub.choices.values():
        sp.add_argument("--json", action="store_true", help="machine-readable output")

    # Dispatch lives on the subparser, not in a trailing lookup: an unknown
    # subcommand is then argparse's error, with the valid choices, not a KeyError.
    _dispatch = {
        "preflight": cmd_preflight,
        "plan": cmd_plan,
        "run": cmd_run,
    }
    for _name, _sp in sub.choices.items():
        _sp.set_defaults(func=_dispatch[_name])
