"""burner.py — the deterministic half of `/alemax:back-burner` (down) and `/alemax:front-burner` (up).

    down [--note "<next step>"] [--open "<item>" …] [--dry-run]
                        write <repo>/.local/resume.md from git state + the operator's note
    up [--check-remote] [--check-openspec]
                        print the checkpoint, the drift since it, and a staleness warning

Run from anywhere inside the repo:

    uv run --directory plugins/alemax alemax burner down --note "…"
    uv run --directory plugins/alemax alemax burner up --check-remote

`down` writes schema 1 (spec `back-burner-session-wind-down`): YAML frontmatter
(`schema_version`, `recorded_at`, `branch`, `head_sha`, `working_tree_clean`) and the three
H2 sections — `## Next step` (the note), `## Open questions` (every uncommitted path, every
stash from today, every `--open` item), `## Recent activity` (`git log --oneline -5`). It
overwrites the previous checkpoint atomically, deletes nothing, commits nothing, and never
touches `.claude/settings*.json` — settings reconciliation is `reconcile-settings.py`'s. It
counts today's `/tmp/claude-*` files and says so; removing them is the operator's call.

`up` is read-only. No checkpoint → standalone mode from `git merge-base HEAD origin/main`.
`schema_version` ≥ 2 → best-effort with a warning; no frontmatter → malformed, synthetic
snapshot. Drift: branch, HEAD (count + first three commits), working tree, stashes newer than
the checkpoint; `--check-remote` adds `git fetch --no-write-fetch-head origin main` + the
count on origin/main; `--check-openspec` adds openspec/changes/ directories newer than the
checkpoint and `gh pr list --state open --base main`. Staleness: silent ≤ 24 h, soft ≤ 7 d,
strong beyond. It proposes nothing and runs nothing — the session does that.

Refuses to write when `.local/` is not gitignored. Exit 0 on success, 1 on refusal, 2 on usage.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .. import git as gitmod
from ..io import die
from ..repo import toplevel
from ..scratch import local_dir

SCHEMA_VERSION = 1
CANONICAL_ONLY = (
    "openspec/changes/",
    "openspec/specs/",
    "openspec/decisions.md",
    "openspec/ideas.md",
)
CANONICAL_ORIGIN = "alemaxdesign/claude-meta"
TMP_PREFIX = "claude-"


def now_utc() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(text: str) -> datetime | None:
    text = text.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S %z"):
        try:
            dt = datetime.strptime(text, fmt)
            return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def branch_of(root: Path) -> str:
    return (
        gitmod.probe(root, "symbolic-ref", "--short", "HEAD")
        or gitmod.probe(root, "rev-parse", "HEAD")
        or "?"
    )


def status_buckets(root: Path) -> dict[str, list[str]]:
    out = gitmod.probe(root, "status", "--porcelain") or ""
    buckets: dict[str, list[str]] = {"staged": [], "unstaged": [], "untracked": []}
    for line in out.splitlines():
        if len(line) < 4:
            continue
        x, y, path = line[0], line[1], line[3:]
        if x == "?" and y == "?":
            buckets["untracked"].append(path)
            continue
        if x not in (" ", "?"):
            buckets["staged"].append(path)
        if y not in (" ", "?"):
            buckets["unstaged"].append(path)
    return buckets


def stashes(root: Path) -> list[tuple[str, datetime | None, str]]:
    out = gitmod.probe(root, "stash", "list", "--format=%gd\t%ci\t%s") or ""
    rows = []
    for line in out.splitlines():
        parts = line.split("\t", 2)
        if len(parts) != 3:
            continue
        rows.append((parts[0], parse_iso(parts[1]), parts[2]))
    return rows


def recent_activity(root: Path) -> list[str]:
    return (gitmod.probe(root, "log", "--oneline", "-5") or "").splitlines()


def tmp_files_today(prefix: str = TMP_PREFIX) -> int:
    floor = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    count = 0
    try:
        with os.scandir("/tmp") as it:
            for e in it:
                if (
                    e.name.startswith(prefix)
                    and e.is_file(follow_symlinks=False)
                    and e.stat().st_mtime >= floor
                ):
                    count += 1
    except OSError:
        return 0
    return count


# --- down --------------------------------------------------------------------


def cmd_down(a: argparse.Namespace) -> int:
    root = Path(a.root).resolve() if a.root else toplevel()
    local = local_dir(root, write=not a.dry_run)
    path = local / "resume.md"
    branch = branch_of(root)
    head = gitmod.probe(root, "rev-parse", "HEAD") or "?"
    buckets = status_buckets(root)
    clean = not any(buckets.values())
    note = " ".join(a.note.split("\n")).strip() if a.note else ""
    if not note:
        print("burner: no --note given — recording '(no next step recorded)'", file=sys.stderr)
        note = "(no next step recorded)"
    today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    open_items: list[str] = []
    for label, key in (
        ("staged, uncommitted", "staged"),
        ("unstaged", "unstaged"),
        ("untracked", "untracked"),
    ):
        for p in buckets[key]:
            open_items.append(f"- Uncommitted ({label}): `{p}` — left at wind-down")
    for ref, when, msg in stashes(root):
        if when is None or when >= today:
            open_items.append(f"- Stash `{ref}` ({iso(when) if when else '?'}): {msg}")
    for item in a.open:
        open_items.append(f"- {item.strip()}")
    lines = [
        "---",
        f"schema_version: {SCHEMA_VERSION}",
        f"recorded_at: {iso(now_utc())}",
        f"branch: {branch}",
        f"head_sha: {head}",
        f"working_tree_clean: {'true' if clean else 'false'}",
        "---",
        "",
        "## Next step",
        "",
        note,
        "",
        "## Open questions",
        "",
    ]
    lines += open_items or ["- (none)"]
    lines += ["", "## Recent activity", ""]
    lines += [f"- {row}" for row in recent_activity(root)] or ["- (no commits)"]
    body = "\n".join(lines) + "\n"
    if a.dry_run:
        sys.stdout.write(body)
        print(f"[dry-run] would write {path.relative_to(root)}", file=sys.stderr)
    else:
        fd, tmp = tempfile.mkstemp(prefix=".resume.", dir=str(local))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(body)
            os.replace(tmp, path)
        except OSError as exc:
            die(f"cannot write {path}: {exc}")
        print(
            f"wrote {path.relative_to(root)} — {branch} @ {head[:7]}, working tree {'clean' if clean else 'dirty'}, {len(open_items)} open item(s)"
        )
    n_tmp = tmp_files_today()
    if n_tmp:
        print(
            f"{n_tmp} /tmp/{TMP_PREFIX}* file(s) touched today — remove by hand if wanted (nothing deleted)"
        )
    return 0


# --- up ----------------------------------------------------------------------


def parse_checkpoint(text: str) -> tuple[dict[str, str], dict[str, str], str]:
    """Return (frontmatter, sections, mode) where mode ∈ v1 | future | malformed."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, {}, "malformed"
    fm: dict[str, str] = {}
    i = 1
    while i < len(lines) and lines[i].strip() != "---":
        if ":" in lines[i]:
            k, v = lines[i].split(":", 1)
            fm[k.strip()] = v.strip()
        i += 1
    if i >= len(lines):
        return {}, {}, "malformed"
    sections: dict[str, str] = {}
    current: str | None = None
    buf: list[str] = []
    for line in lines[i + 1 :]:
        if line.startswith("## "):
            if current is not None:
                sections[current] = "\n".join(buf).strip()
            current, buf = line[3:].strip(), []
        elif current is not None:
            buf.append(line)
    if current is not None:
        sections[current] = "\n".join(buf).strip()
    version = fm.get("schema_version", "")
    if not version.isdigit():
        return fm, sections, "malformed"
    return fm, sections, ("v1" if int(version) == SCHEMA_VERSION else "future")


def first_lines(text: str, n: int) -> list[str]:
    rows = [ln for ln in text.splitlines() if ln.strip()]
    out = rows[:n]
    if len(rows) > n:
        out.append(f"[+{len(rows) - n} more]")
    return out or ["—"]


def cmd_up(a: argparse.Namespace) -> int:
    root = Path(a.root).resolve() if a.root else toplevel()
    path = root / ".local" / "resume.md"
    caveats: list[str] = []
    fm: dict[str, str] = {}
    sections: dict[str, str] = {}
    if not path.exists():
        mode = "standalone"
        caveats.append(
            "No checkpoint found — synthesizing from git history (run /alemax:back-burner next time)"
        )
    else:
        fm, sections, mode = parse_checkpoint(path.read_text(encoding="utf-8", errors="replace"))
        if mode == "malformed":
            caveats.append(
                "checkpoint is malformed (no parseable frontmatter) — reading the body as opaque text, synthetic snapshot"
            )
        elif mode == "future":
            caveats.append(
                f"checkpoint schema version {fm.get('schema_version')} is newer than this reader — best-effort"
            )
    if mode in ("standalone", "malformed"):
        snap_sha = (
            gitmod.probe(root, "merge-base", "HEAD", "origin/main")
            or gitmod.probe(root, "rev-parse", "HEAD")
            or ""
        )
        snap_branch = branch_of(root)
        recorded = None
    else:
        snap_sha = fm.get("head_sha", "")
        snap_branch = fm.get("branch", "")
        recorded = parse_iso(fm.get("recorded_at", ""))

    if recorded is not None:
        age = now_utc() - recorded
        if age > timedelta(days=7):
            caveats.insert(
                0,
                f"⚠ checkpoint is {age.days} days old — consider discarding it and using standalone mode",
            )
        elif age > timedelta(hours=24):
            caveats.insert(
                0,
                f"checkpoint is {int(age.total_seconds() // 3600)} hours old — verify it still reflects current intent",
            )

    cur_branch = branch_of(root)
    cur_sha = gitmod.probe(root, "rev-parse", "HEAD") or ""
    drift: list[tuple[str, str]] = []
    drift.append(
        (
            "branch",
            f"{snap_branch} → {cur_branch}" if snap_branch and snap_branch != cur_branch else "—",
        )
    )
    if snap_sha and cur_sha and snap_sha != cur_sha:
        count = gitmod.probe(root, "rev-list", "--count", f"{snap_sha}..HEAD") or "?"
        first3 = (
            gitmod.probe(root, "log", "--oneline", "-3", f"{snap_sha}..HEAD") or ""
        ).splitlines()
        drift.append(
            (
                "HEAD",
                f"{count} commit(s) since checkpoint"
                + (" — " + "; ".join(first3) if first3 else ""),
            )
        )
    else:
        drift.append(("HEAD", "—"))
    b = status_buckets(root)
    drift.append(
        (
            "working tree",
            f"{len(b['unstaged'])} unstaged · {len(b['staged'])} staged · {len(b['untracked'])} untracked",
        )
    )
    if recorded is not None:
        new_stashes = [
            f"{ref} {msg}" for ref, when, msg in stashes(root) if when is None or when >= recorded
        ]
        drift.append(("stash", "; ".join(new_stashes) if new_stashes else "—"))
    else:
        drift.append(("stash", "—"))
    if a.check_remote:
        gitmod.probe(root, "fetch", "--no-write-fetch-head", "origin", "main")
        count = (
            gitmod.probe(root, "rev-list", "--count", f"{snap_sha}..origin/main")
            if snap_sha
            else None
        )
        first3 = (
            (
                gitmod.probe(root, "log", "--oneline", "-3", f"{snap_sha}..origin/main") or ""
            ).splitlines()
            if snap_sha
            else []
        )
        if count is None:
            drift.append(("remote", "(origin/main not reachable)"))
        else:
            drift.append(
                (
                    "remote",
                    f"{count} commit(s) on origin/main since checkpoint"
                    + (" — " + "; ".join(first3) if first3 else "")
                    if count != "0"
                    else "—",
                )
            )
    else:
        drift.append(("remote", "(not checked — pass --check-remote)"))
    if a.check_openspec:
        new_changes = 0
        changes = root / "openspec" / "changes"
        if recorded is not None and changes.is_dir():
            for e in os.scandir(changes):
                if e.is_dir() and e.name != "archive" and e.stat().st_mtime >= recorded.timestamp():
                    new_changes += 1
        prs = "?"
        try:
            done = subprocess.run(
                [
                    "gh",
                    "pr",
                    "list",
                    "--state",
                    "open",
                    "--base",
                    "main",
                    "--json",
                    "number,title",
                    "--limit",
                    "20",
                ],
                cwd=str(root),
                capture_output=True,
                text=True,
                check=True,
            )
            rows = json.loads(done.stdout or "[]")
            prs = (
                "; ".join(f"#{r['number']} {r['title']}" for r in rows[:3])
                + (f" [+{len(rows) - 3} more]" if len(rows) > 3 else "")
                if rows
                else "none"
            )
        except OSError, subprocess.CalledProcessError, ValueError:
            prs = "(gh unavailable)"
        drift.append(
            ("openspec", f"{new_changes} new change dir(s) since checkpoint; open PRs: {prs}")
        )
    else:
        drift.append(("openspec", "(not checked — pass --check-openspec)"))

    for c in caveats:
        print(c)
    if caveats:
        print()
    print("## Next step (recorded)")
    next_step = sections.get("Next step", "")
    for ln in first_lines(next_step, 3):
        print(f"  {ln}")
    origin = gitmod.probe(root, "remote", "get-url", "origin") or ""
    if (
        cur_branch == "main"
        and CANONICAL_ORIGIN not in origin
        and any(p in next_step for p in CANONICAL_ONLY)
    ):
        print(
            "  (note: the next step names a canonical-only path and this is a fork's main — switch to a feature branch first)"
        )
    print()
    print("## Open questions")
    for ln in first_lines(sections.get("Open questions", ""), 3):
        print(f"  {ln}")
    print()
    print("## Drift")
    for k, v in drift:
        print(f"  {k + ':':<14} {v}")
    print()
    print("## Recent activity")
    for ln in first_lines(
        sections.get("Recent activity", "") or "\n".join(recent_activity(root)), 5
    ):
        print(f"  {ln}")
    return 0


# --- main --------------------------------------------------------------------


def register(ap: argparse.ArgumentParser) -> None:
    ap.add_argument("--root", help="repo toplevel (default: git rev-parse --show-toplevel)")
    sub = ap.add_subparsers(dest="subcommand", required=True)

    s = sub.add_parser("down", help="write .local/resume.md (wind-down)")
    s.add_argument("--note", help="the next step, in the operator's words")
    s.add_argument(
        "--open", action="append", default=[], help="an open question to record (repeatable)"
    )
    s.add_argument(
        "--dry-run", action="store_true", help="print the checkpoint instead of writing it"
    )
    s.set_defaults(func=cmd_down)

    s = sub.add_parser("up", help="read .local/resume.md and report drift (resume)")
    s.add_argument(
        "--check-remote",
        action="store_true",
        help="fetch origin/main and count commits since the checkpoint",
    )
    s.add_argument(
        "--check-openspec",
        action="store_true",
        help="count new openspec/changes/ dirs and list open PRs (gh)",
    )
    s.set_defaults(func=cmd_up)
