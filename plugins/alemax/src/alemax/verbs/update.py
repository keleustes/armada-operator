"""`alemax update` — the deterministic half of /alemax:complete-update.

Runs in the PROJECT's clone. It finds the delivery, says how it must be applied, and
says what stands in the way. It never commits, branches, pushes or opens a PR: the
skill body does that with git, so every mutation is one the session chose. `result`
prints an autonomous run's final line and, for a question, adds it to the handoff.
"""

from __future__ import annotations

import argparse
import os
import re
from datetime import UTC, datetime
from fnmatch import fnmatch
from pathlib import Path

from .. import git
from ..io import AMBIGUOUS, ERROR, FOUND, OK, emit
from ..repo import foreign_ci_jobs, is_meta_repo, require_project, stacks, toplevel

PLUGIN_MANIFEST = ".claude/skills/alemax/.claude-plugin/plugin.json"
PLUGIN_SKILLS = ".claude/skills/alemax/skills"
FLAT_COMMANDS = ".claude/commands/alemax"
FLAT_SKILL_PREFIX = ".claude/skills/alemax-"
HANDOFFS = (".local/HANDOFF.md", ".local/update-todo.md")
# Set by `alemax agent deliver` (spec agent-launcher, design D12): this run has no human.
AUTONOMOUS_ENV = "ALEMAX_AUTONOMOUS"
# The one final line an autonomous run ends with, which the runner reads.
RESULT_STATUSES = ("done", "needs-operator", "nothing-to-apply")
NEEDS_OPERATOR_HEADING = "## Needs the operator"
SUPERSEDED_HEADING = "## Superseded paths"
BOOTSTRAP_PATHS = (
    ".claude/skills/alemax/skills/complete-update",
    ".claude/skills/alemax/.claude-plugin/plugin.json",
)

BRANCH_RE = re.compile(r"(meta-broadcast/[A-Za-z0-9._/-]+|claude-meta-update)")
# The broadcast run that staged this handoff (spec agent-launcher, design D10); absent
# from a handoff written before run records existed.
RUN_RE = re.compile(r"\*\*run:\*\*\s+`([^`]+)`")
SUPERSEDED_LINE_RE = re.compile(r"^(?P<path>[^\s#][^\s]*)(?:\s+#.*)?$")
# --- context ------------------------------------------------------------------------


def cmd_context(a: argparse.Namespace) -> int:
    root = toplevel()
    meta = is_meta_repo(root)
    autonomous = os.environ.get(AUTONOMOUS_ENV) == "1"
    payload = {
        "root": str(root),
        "is_meta_repo": meta,
        "stacks": stacks(root),
        "autonomous": autonomous,
    }
    plain = (
        f"project={root.name} root={root} stacks={', '.join(payload['stacks']) or 'none detected'}"
    )
    if autonomous:
        plain += (
            "\nautonomous=yes — no human is watching: never ask; end with one"
            " `alemax update result` line (done | needs-operator | nothing-to-apply)"
        )
    if meta:
        plain = (
            "BLOCKED: this is the claude-meta clone — /alemax:complete-update runs in the\n"
            "  PROJECT's own session (Guardrail 4). Meta stages; it never applies."
        )
    emit(payload, as_json=a.json, plain=plain)
    return ERROR if meta else OK


# --- handoff ------------------------------------------------------------------------


def read_handoff(root: Path) -> dict:
    for rel in HANDOFFS:
        path = root / rel
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="ignore")
            m = BRANCH_RE.search(text)
            run = RUN_RE.search(text)
            return {
                "rel": rel,
                "branch": m[1] if m else None,
                "run": run[1] if run else None,
                "text": text,
            }
    return {}


def cmd_handoff(a: argparse.Namespace) -> int:
    root = require_project()
    h = read_handoff(root)
    if a.json:
        emit(h or {"rel": None, "branch": None, "run": None}, as_json=True)
    elif h:
        named = f"  names branch: {h['branch']}" if h["branch"] else ""
        named += f"  run: {h['run']}" if h["run"] else ""
        print(f"handoff: {h['rel']}{named}\n{h['text']}")
    else:
        print(
            "no .local/HANDOFF.md or .local/update-todo.md — `locate` can still find a branch,\n"
            "and a class-M gap is still worth probing before reporting 'already current'."
        )
    return OK if h else FOUND


# --- locate -------------------------------------------------------------------------


def cmd_locate(a: argparse.Namespace) -> int:
    root = require_project()
    named = read_handoff(root).get("branch")
    found: list[str] = []

    for cand in filter(None, [named, "claude-meta-update"]):
        if git.probe(root, "rev-parse", "--verify", "--quiet", cand):
            found.append(cand)
    if not found and a.meta_src:
        git.probe(
            root,
            "fetch",
            a.meta_src,
            "refs/heads/meta-broadcast/*:refs/remotes/metasrc/meta-broadcast/*",
            "--quiet",
        )
        found += git.lines(
            root,
            "for-each-ref",
            "--format=%(refname:short)",
            "refs/remotes/metasrc/meta-broadcast/*",
        )
    if not found:
        git.probe(root, "fetch", "origin", "--quiet")
        found += git.lines(
            root,
            "for-each-ref",
            "--format=%(refname:short)",
            "refs/remotes/origin/meta-broadcast/*",
        )
    found = list(dict.fromkeys(found))

    untracked: list[str] = []
    for b in BOOTSTRAP_PATHS:
        untracked += sorted(git.untracked(root, b))

    def shape(ref: str) -> str:
        return "broadcast" if "meta-broadcast/" in ref else "sync"

    refs = [
        {
            "ref": r,
            "shape": shape(r),
            "verb": "git cherry-pick" if shape(r) == "broadcast" else "git merge --no-ff",
        }
        for r in found
    ]
    payload = {"refs": refs, "named_by_handoff": named, "bootstrap_untracked": untracked}

    if a.json:
        emit(payload, as_json=True)
    else:
        for r in refs:
            print(f"{r['ref']}  shape={r['shape']}  apply with: {r['verb']}")
        if not found:
            print("no update branch found — nothing to apply")
        if len(found) > 1:
            print(
                "\nSeveral refs. Apply the one the HANDOFF names — never 'the first one':\n"
                "  a re-broadcast can leave two refs with IDENTICAL trees and different\n"
                "  .meta-version pins, so picking wrong applies a stale pin with no conflict."
            )
        if untracked:
            print(
                f"\nbootstrap collision: {len(untracked)} untracked path(s) the delivery also carries —"
            )
            print("  `git add` and commit them BEFORE applying, or git refuses the cherry-pick:")
            for u in untracked:
                print(f"    {u}")
    return OK if len(found) == 1 else (AMBIGUOUS if found else FOUND)


# --- citrim -------------------------------------------------------------------------


def cmd_citrim(a: argparse.Namespace) -> int:
    root = require_project()
    ci = root / ".github" / "workflows" / "ci.yml"
    if not ci.is_file():
        emit(
            {"file": None, "foreign_jobs": []}, as_json=a.json, plain="no .github/workflows/ci.yml"
        )
        return OK

    have = set(stacks(root))
    foreign = foreign_ci_jobs(ci.read_text(encoding="utf-8"), have)
    if foreign is None:
        emit(
            {"file": str(ci), "foreign_jobs": []},
            as_json=a.json,
            plain="no `jobs:` block in ci.yml",
        )
        return OK

    payload = {"stacks_present": sorted(have), "foreign_jobs": foreign, "file": str(ci)}
    if a.json:
        emit(payload, as_json=True)
    else:
        print(f"stacks present: {', '.join(sorted(have)) or 'none'}")
        for f in foreign:
            print(
                f"  ci.yml:{f['line']} job '{f['job']}' is {'/'.join(f['stacks'])}-only — trim it"
            )
        if not foreign:
            print("  every job matches a stack this project has — nothing to trim")
    return FOUND if foreign else OK


# --- stale --------------------------------------------------------------------------


def read_superseded(root: Path) -> list[str]:
    """Paths the delivery says meta no longer ships.

    Inferring supersession from the plugin's own skill names only ever covered the
    alemax family. It cannot see `.claude/commands/review.md`, which meta stopped
    shipping and every project bootstrapped before that still carries — the same
    defect in a second artifact, found independently. Meta cannot compute this either:
    a path that stopped shipping looks exactly like one that never shipped. So the
    delivery carries the list, and a project removes nothing that is not on it.
    """
    handoff = read_handoff(root)
    if not handoff:
        return []
    out: list[str] = []
    in_section = False
    for line in handoff["text"].splitlines():
        if line.startswith("## "):
            in_section = line.strip() == SUPERSEDED_HEADING
            continue
        if not in_section:
            continue
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if m := SUPERSEDED_LINE_RE.match(stripped):
            out.append(m["path"])
    return out


def matches_superseded(rel: str, patterns: list[str]) -> str | None:
    """The pattern that claims `rel`, or None. A trailing `/` means the whole subtree."""
    for pat in patterns:
        if pat.endswith("/"):
            if rel.startswith(pat) or fnmatch(rel + "/", pat + "*"):
                return pat
        elif fnmatch(rel, pat) or rel == pat or fnmatch(rel, pat.rstrip("/") + "/*"):
            return pat
    return None


def plugin_skill_names(root: Path) -> list[str]:
    d = root / PLUGIN_SKILLS
    if not d.is_dir():
        return []
    try:
        return sorted(p.name for p in d.iterdir() if (p / "SKILL.md").is_file())
    except OSError:
        return []


def is_stub_of(rel: str, supplied: list[str]) -> bool:
    """A stub is `<name>.md` DIRECTLY in the command dir, and `<name>` is a plugin skill.

    Matching `Path(rel).stem` at any depth counted a note at `archive/feedback.md` and a
    `feedback.txt` as the `feedback` stub — and because they then looked accounted-for,
    the directory-wide `git rm -r` was re-enabled over a tree holding more than stubs.
    """
    parent, _, name = rel.rpartition("/")
    return parent == FLAT_COMMANDS and name.endswith(".md") and name[: -len(".md")] in supplied


def superseded_hits(root: Path, patterns: list[str]) -> list[tuple[str, str, bool]]:
    """(path, the pattern that claims it, tracked) for everything the manifest names.

    Scanned over the whole tree, not one directory: the manifest exists precisely
    because supersession is not confined to the family a verb happens to know about.
    """
    if not patterns:
        return []
    tracked = git.tracked(root)
    hits: list[tuple[str, str, bool]] = []
    for rel in sorted(tracked | git.untracked(root)):
        if pat := matches_superseded(rel, patterns):
            hits.append((rel, pat, rel in tracked))
    return hits


def cmd_stale(a: argparse.Namespace) -> int:
    root = require_project()
    patterns = read_superseded(root)
    manifest_hits = superseded_hits(root, patterns)
    entries = sorted(
        [(f, True) for f in git.tracked(root, FLAT_COMMANDS)]
        + [(f, False) for f in git.untracked(root, FLAT_COMMANDS)]
    )

    if not (root / PLUGIN_MANIFEST).is_file():
        emit(
            {"plugin_present": False, "waiting": len(entries)},
            as_json=a.json,
            plain=(
                f"the plugin is not here yet ({PLUGIN_MANIFEST} absent) — nothing to remove.\n"
                f"  {len(entries)} file(s) under {FLAT_COMMANDS}/ are waiting on it.\n"
                "  Apply the delivery first; removing the stubs before it lands leaves no /alemax:* at all."
            ),
        )
        return OK

    supplied = plugin_skill_names(root)
    if not supplied:
        emit(
            {"plugin_present": True, "plugin_skills": []},
            as_json=a.json,
            plain=(
                f"INCOMPLETE: {PLUGIN_MANIFEST} is here but {PLUGIN_SKILLS}/ supplies no skill.\n"
                "  Half a delivery. Do not remove anything — finish or re-request the broadcast first."
            ),
        )
        return ERROR

    stubs = [(f, t) for f, t in entries if is_stub_of(f, supplied)]
    others = [(f, t) for f, t in entries if not is_stub_of(f, supplied)]

    skill_dirs: dict[str, bool] = {}
    flat_tracked = git.tracked(root, FLAT_SKILL_PREFIX + "*")
    for f in sorted(flat_tracked | git.untracked(root, FLAT_SKILL_PREFIX + "*")):
        parts = f.split("/")
        if len(parts) < 3 or not parts[2].startswith("alemax-"):
            continue
        if parts[2][len("alemax-") :] in supplied:
            d = "/".join(parts[:3])
            skill_dirs[d] = skill_dirs.get(d, True) and f in flat_tracked

    found = bool(stubs or skill_dirs)
    payload = {
        "plugin_skills": supplied,
        "stale_commands": [f for f, _ in stubs],
        "stale_skill_dirs": sorted(skill_dirs),
        "unsupplied_commands": [f for f, _ in others],
        "superseded_by_manifest": [
            {"path": rel, "pattern": pat, "tracked": t} for rel, pat, t in manifest_hits
        ],
        "manifest_patterns": patterns,
    }
    found = found or bool(manifest_hits)
    if a.json:
        emit(payload, as_json=True)
        return FOUND if found else OK

    def removal(path: str, is_tracked: bool, recurse: bool = False) -> str:
        # `git rm` only knows tracked paths; an untracked one needs a plain rm.
        r = "-r " if recurse else ""
        return f"    git rm {r}--quiet {path}" if is_tracked else f"    rm {r}-- {path}"

    print(f"plugin supplies {len(supplied)} skill(s) under {PLUGIN_SKILLS}/")
    if stubs:
        print(f"\n{len(stubs)} command stub(s) now shadowed by the plugin's own /alemax:<name>:")
        # Sweep the directory ONLY when it holds nothing but accounted-for stubs.
        if not others and all(t for _, t in stubs):
            print(removal(FLAT_COMMANDS, True, recurse=True))
        else:
            for f, t in stubs:
                print(removal(f, t))
    if skill_dirs:
        print(f"\n{len(skill_dirs)} flat skill dir(s) superseded by the plugin's copy:")
        for d in sorted(skill_dirs):
            print(removal(d, skill_dirs[d], recurse=True))
    if others:
        print(
            f"\n{len(others)} path(s) the plugin does NOT supply — read each, remove nothing blind:"
        )
        for f, t in others:
            print(f"    {f}{'' if t else '  (untracked)'}")
    beyond = [h for h in manifest_hits if not h[0].startswith((FLAT_COMMANDS, FLAT_SKILL_PREFIX))]
    if beyond:
        print(f"\n{len(beyond)} path(s) the delivery says meta no longer ships:")
        for rel, pat, is_tracked in beyond:
            print(f"{removal(rel, is_tracked)}   # {pat}")
    if not patterns:
        print(
            "\nNo superseded-path manifest in the handoff, so only the alemax family was\n"
            "  checked. A delivery that carries one lets this see everything meta dropped."
        )
    if not found:
        print("nothing stale — the flat surface is already gone")
    return FOUND if found else OK


# --- result -------------------------------------------------------------------------


def cmd_result(a: argparse.Namespace) -> int:
    """Print the run's final status line; a needs-operator question also goes in the handoff.

    The line is what `alemax agent deliver` reads from an autonomous run (design D12):
    `done: <pin> <merge sha> <pr url>`, `needs-operator: <the question>` or
    `nothing-to-apply: <why>`. Each `--step` is printed first as `operator-step: <command>`,
    a command only the operator may run (the staged settings `cp`, for one); the runner
    gathers them into one list.
    """
    root = require_project()
    detail = " ".join(a.detail).strip()
    if not detail:
        print("alemax: result needs a detail: the pin and sha, the question, or the reason")
        return ERROR
    line = f"{a.status}: {detail}"
    if a.status == "needs-operator":
        handoff = root / HANDOFFS[0]
        handoff.parent.mkdir(parents=True, exist_ok=True)
        text = handoff.read_text(encoding="utf-8") if handoff.is_file() else ""
        if NEEDS_OPERATOR_HEADING not in text:
            text = text.rstrip("\n") + f"\n\n{NEEDS_OPERATOR_HEADING}\n"
        stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        handoff.write_text(text.rstrip("\n") + f"\n- {stamp} {detail}\n", encoding="utf-8")
    steps = [s.strip() for s in (a.step or []) if s.strip()]
    plain = "\n".join([*(f"operator-step: {s}" for s in steps), line])
    emit(
        {"status": a.status, "detail": detail, "line": line, "operator_steps": steps},
        as_json=a.json,
        plain=plain,
    )
    return OK


# --- registration -------------------------------------------------------------------

SUBCOMMANDS = {
    "context": (cmd_context, "refuse on the meta-repo; report root and stack"),
    "handoff": (cmd_handoff, "the meta side's briefing and the branch it names"),
    "locate": (cmd_locate, "the update ref, its shape, and the bootstrap collision"),
    "citrim": (cmd_citrim, "ci.yml jobs belonging to a stack this project does not have"),
    "stale": (cmd_stale, "the flat /alemax:* surface the delivered plugin supersedes"),
    "result": (
        cmd_result,
        "an autonomous run's final line: done | needs-operator | nothing-to-apply",
    ),
}


def register(ap: argparse.ArgumentParser) -> None:
    subs = ap.add_subparsers(dest="subcommand", required=True, metavar="SUBCOMMAND")
    for name, (fn, help_text) in SUBCOMMANDS.items():
        sp = subs.add_parser(name, help=help_text)
        sp.add_argument("--json", action="store_true", help="machine-readable output")
        if name == "result":
            sp.add_argument("status", choices=RESULT_STATUSES)
            sp.add_argument(
                "detail", nargs="*", help="the pin and sha, the question, or the reason"
            )
            sp.add_argument(
                "--step",
                action="append",
                metavar="COMMAND",
                help="a command the operator must run, printed as operator-step: (repeatable)",
            )
        if name == "locate":
            sp.add_argument(
                "--meta-src",
                metavar="PATH",
                help="a nearby meta worktree to fetch meta-broadcast/* from",
            )
        sp.set_defaults(func=fn)
