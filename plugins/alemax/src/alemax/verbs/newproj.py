"""newproj.py — the deterministic half of /alemax:new-project.

Validates the four required arguments and every collision that would make
`meta/bootstrap/init-project.sh` fail halfway, states the side effects it is
about to cause, then runs it. Bootstrapping creates a private GitHub repo and
a local clone — the confirmation belongs to the operator, so `run` is never
reached without one.

Subcommands
  preflight  fork claude-meta clone, clean tree, gh authenticated.
             Exit 0/1.
  validate   the name, stack and handle, plus the three collisions:
             `projects.yaml`, `repos.yaml`, and the destination directory.
             `--json` for the full picture. Exit 0 clear, 1 blocked.
  plan       the exact side effects, so the confirmation is informed.
             Exit 0.
  run        invoke init-project.sh. Exit 0/1.

The destination is `${META_PROJECTS_ROOT:-/Volumes/AIML<NN>/Users/<u>/claude-code}/<handle>/<name>`
— a literal volume path per the system-path-rule, never `~`.
"""

# shipped-path-scope: meta

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from .. import git as gitmod
from ..io import die

CANONICAL = "alemaxdesign/claude-meta"
STACKS = ("python", "bash", "go", "xcode", "rust", "java")
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
HANDLE_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
ENTRY_RE = re.compile(r"^  - name: (?P<name>\S+)\s*$")
FIELD_RE = re.compile(r"^    (?P<key>[a-z_]+): (?P<val>.*?)\s*$")


def meta_root() -> Path:
    top = gitmod.probe(Path.cwd(), "rev-parse", "--show-toplevel")
    if not top:
        die("not a git repository")
    return Path(top)


def entries(path: Path) -> list[dict]:
    out, cur = [], None
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if m := ENTRY_RE.match(line):
            if cur:
                out.append(cur)
            cur = {"name": m["name"]}
        elif cur and (m := FIELD_RE.match(line)):
            cur[m["key"]] = m["val"].strip('"')
    if cur:
        out.append(cur)
    return out


def projects_root(root: Path, drive: str | None = None, volume: str | None = None) -> Path:
    """Where init-project.sh will put the project — its own rule, so `validate` checks the
    directory `run` creates: `$META_PROJECTS_ROOT`, else `<volume>/Users/$USER/claude-code`
    for `--volume`, or `/Volumes/AIML<NN>/…` for `--drive`, else beside this clone."""
    if env := os.environ.get("META_PROJECTS_ROOT"):
        return Path(env)
    if volume or drive:
        vol = Path(volume) if volume else Path("/", "Volumes", f"AIML{drive}")
        return vol / "Users" / (os.environ.get("USER") or Path.home().name) / "claude-code"
    # The meta clone lives at <root>/claude-code/<handle>/claude-meta; `run` passes this
    # clone's volume, so the script lands here too.
    return root.parent.parent


def clone_volume(root: Path) -> str | None:
    """`/Volumes/<X>` holding the meta clone, or None when the clone is not on a volume.

    init-project.sh resolves its volume on its own (--volume > --drive > a single detected
    drive > 01), so with two drives mounted it fell back to AIML01 while `validate` reported
    a destination beside THIS clone. Passing the clone's volume makes the two agree.
    """
    parts = root.parts
    if len(parts) > 2 and parts[1] == "Volumes":
        return f"/Volumes/{parts[2]}"
    return None


def destination(root: Path, handle: str, name: str, a=None) -> Path:
    drive, volume = getattr(a, "drive", None), getattr(a, "volume", None)
    return projects_root(root, drive, volume) / handle / name


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
            "origin is canonical — init-project.sh appends to YOUR fork's projects.yaml; "
            "run from your fork clone on its per-volume branch"
        )
    if gitmod.probe(root, "status", "--porcelain"):
        out["blocked"].append("working tree is dirty — the bootstrap commits to projects.yaml")
    if not shutil.which("gh"):
        out["blocked"].append("gh not on PATH — the bootstrap creates a private GitHub repo")
    elif subprocess.run(["gh", "auth", "status"], capture_output=True, text=True).returncode != 0:
        out["blocked"].append("gh is not authenticated — run `gh auth login`")
    return out


def stack_parts(a) -> list[str]:
    """Every --stack, in order; a value may itself be `+`-joined (`python+xcode`)."""
    return [p for v in a.stack or [] for p in v.split("+") if p]


def stack_label(a) -> str:
    """The manifest form of the stack set (spec stack-composition)."""
    return "+".join(stack_parts(a))


def validate(root: Path, a) -> dict:
    out: dict = {"name": a.name, "stack": stack_label(a), "ghhandle": a.ghhandle, "blocked": []}
    if not NAME_RE.match(a.name or ""):
        out["blocked"].append(
            f"--name '{a.name}' is not kebab-case lowercase (a-z, 0-9, single hyphens)"
        )
    parts = stack_parts(a)
    if not parts:
        out["blocked"].append("--stack is required")
    for part in parts:
        if part not in STACKS:
            out["blocked"].append(f"--stack '{part}' is not one of: {', '.join(STACKS)}")
    for part in sorted({p for p in parts if parts.count(p) > 1}):
        out["blocked"].append(f"--stack '{part}' given twice")
    if not HANDLE_RE.match(a.ghhandle or ""):
        out["blocked"].append(f"--ghhandle '{a.ghhandle}' is not a valid GitHub owner name")
    if not (a.description or "").strip():
        out["blocked"].append("--description is required and must not be empty")
    if a.drive and a.volume:
        out["blocked"].append("--drive and --volume are mutually exclusive")

    if NAME_RE.match(a.name or ""):
        if any(p["name"] == a.name for p in entries(root / "projects.yaml")):
            out["blocked"].append(f"'{a.name}' is already a row in projects.yaml")
        repos = [r for r in entries(root / "repos.yaml") if r["name"] == a.name]
        if repos:
            out["repos_yaml_hit"] = [r.get("ghhandle", "?") for r in repos]
            out["blocked"].append(
                f"'{a.name}' already exists in repos.yaml under: {', '.join(out['repos_yaml_hit'])}"
            )
        if a.ghhandle and HANDLE_RE.match(a.ghhandle):
            dest = destination(root, a.ghhandle, a.name, a)
            out["destination"] = str(dest)
            if dest.exists():
                out["blocked"].append(f"destination already exists: {dest}")
    return out


def cmd_preflight(a) -> int:
    r = preflight(meta_root())
    if a.json:
        print(json.dumps(r, indent=2))
    else:
        for b in r["blocked"]:
            print(f"BLOCKED: {b}")
        if not r["blocked"]:
            print("preflight clear")
    return 1 if r["blocked"] else 0


def cmd_validate(a) -> int:
    r = validate(meta_root(), a)
    if a.json:
        print(json.dumps(r, indent=2))
    else:
        for b in r["blocked"]:
            print(f"BLOCKED: {b}")
        if not r["blocked"]:
            print(f"{a.name} ({stack_label(a)}) → {r.get('destination', '?')}")
    return 1 if r["blocked"] else 0


def cmd_plan(a) -> int:
    root = meta_root()
    r = validate(root, a)
    dest = r.get("destination", "?")
    effects = [
        f"create a PRIVATE GitHub repo {a.ghhandle}/{a.name}",
        f"clone it to {dest}",
        f"scaffold the {stack_label(a)} stack there, with .meta-version pinned to canonical main",
        "append a row to THIS fork's projects.yaml and commit it",
        f"seed ideas-on-the-go-{a.name}.md in the Obsidian vault (--no-obsidian skips the prompt)",
        "generate a Desktop launcher, if this drive opted into launchers (--no-launcher skips)",
    ]
    payload = {"effects": effects, "destination": dest, "blocked": r["blocked"]}
    if a.json:
        print(json.dumps(payload, indent=2))
    else:
        for b in r["blocked"]:
            print(f"BLOCKED: {b}")
        print("this will:")
        for e in effects:
            print(f"  - {e}")
    return 1 if r["blocked"] else 0


def cmd_run(a) -> int:
    root = meta_root()
    r = validate(root, a)
    if r["blocked"]:
        for b in r["blocked"]:
            print(f"BLOCKED: {b}", file=sys.stderr)
        return 1
    script = root / "meta" / "bootstrap" / "init-project.sh"
    if not script.is_file():
        die(f"{script} not found")
    argv = [
        "bash",
        str(script),
        "--name",
        a.name,
        *(arg for part in stack_parts(a) for arg in ("--stack", part)),
        "--ghhandle",
        a.ghhandle,
        "--description",
        a.description,
    ]
    for flag, val in (("--drive", a.drive), ("--volume", a.volume)):
        if val:
            argv += [flag, val]
    if not (a.drive or a.volume) and (vol := clone_volume(root)):
        argv += ["--volume", vol]
    for flag, on in (("--no-obsidian", a.no_obsidian), ("--no-launcher", a.no_launcher)):
        if on:
            argv.append(flag)
    rc = subprocess.run(argv, cwd=str(root)).returncode
    if a.json:
        print(json.dumps({"exit": rc, "destination": r.get("destination")}, indent=2))
    elif rc == 0:
        print(f"bootstrapped → {r.get('destination')}")
        print("next: from the NEW project's own session, run /alemax:complete-init")
    return 0 if rc == 0 else 1


def add_args(p: argparse.ArgumentParser, full: bool = False) -> None:
    p.add_argument("--name", required=True, help="kebab-case lowercase project name")
    p.add_argument(
        "--stack",
        required=True,
        action="append",
        help=f"one of: {', '.join(STACKS)}; repeat it (or join with +) to combine stacks",
    )
    p.add_argument("--ghhandle", required=True, help="GitHub org or user that will own the repo")
    p.add_argument("--description", default="", help="one-line description")
    # On every subcommand that names a destination, so `validate` and `plan` check the
    # directory `run` will create rather than the one beside this clone.
    p.add_argument("--drive", help="target AIML drive (01..99)")
    p.add_argument("--volume", help="target volume path, for a renamed drive")
    if full:
        p.add_argument("--no-obsidian", action="store_true")
        p.add_argument("--no-launcher", action="store_true")


def register(ap: argparse.ArgumentParser) -> None:
    sub = ap.add_subparsers(dest="subcommand", required=True)
    sub.add_parser("preflight", help="clone, tree and gh auth")
    add_args(sub.add_parser("validate", help="the arguments and the three collisions"))
    add_args(sub.add_parser("plan", help="the exact side effects"))
    add_args(sub.add_parser("run", help="invoke init-project.sh"), full=True)
    # --json belongs on each subcommand, so `<cmd> --json` works (the natural form).
    for sp in sub.choices.values():
        sp.add_argument("--json", action="store_true", help="machine-readable output")

    # Dispatch lives on the subparser, not in a trailing lookup: an unknown
    # subcommand is then argparse's error, with the valid choices, not a KeyError.
    _dispatch = {
        "preflight": cmd_preflight,
        "validate": cmd_validate,
        "plan": cmd_plan,
        "run": cmd_run,
    }
    for _name, _sp in sub.choices.items():
        _sp.set_defaults(func=_dispatch[_name])
