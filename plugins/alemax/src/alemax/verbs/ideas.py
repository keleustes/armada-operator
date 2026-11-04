"""ideas.py — the deterministic half of `/alemax:archive-ideas` and `/alemax:reprioritise-ideas`.

One script, two verbs: the two halves of one file's lifecycle (`openspec/ideas.md`).

    list [--state open|x|all] [--json]
                        the § Raw ideas entries, with slug, state and one-line summary
    archive [--only <slug> …] [--capability <slug>=<cap>[,<cap>] …] [--context <name>]
            [--apply] [--force] [--json]
                        move each classified `[x]` entry out of § Raw ideas into
                        § Archived ideas — by capability, snapshotting first
    reprioritise [--pick <slug|index> …] [--add] [--clear] [--apply] [--force] [--json]
                        rewrite § Suggested next-up with pointer-only entries

Run from anywhere inside the repo:

    uv run --directory plugins/alemax alemax ideas list --state x
    uv run --directory plugins/alemax alemax ideas reprioritise --pick foo --apply

**Both mutating verbs are dry-run by default** — they print the plan and write nothing
until `--apply`. The per-entry confirmation the operator sees is the session reading the
plan back; the script never prompts.

`archive` classifies each `[x]` entry with the three-tier fallback: (1) an inline
`→ [<slug>](changes/archive/…)` pointer; (2) a slug mentioned in the entry body (or the
entry's own slug) matching exactly one directory under `openspec/changes/archive/`;
(3) unresolved — reported for the session to ask the operator, whose answer comes back as
`--capability <slug>=<capability>`. Capabilities are read from the archived change's
`proposal.md` § Capabilities. The one-line bullet
`- <archive date> — `<slug>` ([archive](changes/archive/<dir>/)) — <summary>` is appended
under each named `### [`<capability>`]` heading; the full body leaves § Raw ideas.
`--apply` snapshots `openspec/ideas.md` to `openspec/ideas-snapshots/<today>-<context>.md`
(default context `pre-reshape`; `-2`, `-3` … on collision) before writing.

`reprioritise` replaces § Suggested next-up with `- <slug> — <summary>` pointers (spec
`alemax-skills`: each run is a fresh curation). `--add` appends to what is there instead,
`--clear` empties the section. § Raw ideas and § Archived ideas are never touched.

Refusals: no `openspec/ideas.md` at the repo root; a conflict marker in it (an unfinished
merge — never rewrite that); with `--apply`, uncommitted changes to `openspec/ideas.md`
itself unless `--force`. Nothing is committed and no branch is created — landing the
result is the session's job (in claude-meta: a branch and a PR, Guardrail 2).
Exit 0 on success, 1 on refusal, 2 on usage.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import tempfile
from datetime import date
from pathlib import Path

from .. import git as gitmod
from ..io import die
from ..repo import toplevel

RAW = "Raw ideas"
ARCHIVED = "Archived ideas"
NEXTUP = "Suggested next-up"
CLOSED_HEADING = "### Closed without implementation"
ENTRY_RE = re.compile(r"^- \[( |x)\] (.*)$")
BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
SLUG_IN_TITLE_RE = re.compile(r"\(`([a-z0-9][a-z0-9-]{2,})`\)")
WIKI_RE = re.compile(r"\[\[([a-z0-9][a-z0-9-]{2,})\]\]")
TICK_RE = re.compile(r"`([a-z0-9][a-z0-9-]{2,})`")
POINTER_RE = re.compile(r"→\s*\[([a-z0-9][a-z0-9-]*)\]\(changes/archive/([^)]+)\)")
ARCHIVE_DIR_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-(.+)$")
CAP_HEADING_RE = re.compile(r"^### \[`([a-z0-9][a-z0-9-]*)`\]")
CONFLICT_RE = re.compile(r"^(<{7}|={7}|>{7})(\s|$)")
NEXTUP_MAX = 10


def one_line(text: str) -> str:
    return " ".join(text.split())


def slugify(text: str) -> str:
    out = re.sub(r"[^a-z0-9]+", "-", one_line(text).lower()).strip("-")
    return out[:40] or "entry"


# --- the file ----------------------------------------------------------------


def section_bounds(lines: list[str], title: str) -> tuple[int, int]:
    """[start, end) of the `## <title>…` section — start is the heading line itself."""
    start = None
    for i, ln in enumerate(lines):
        if not ln.startswith("## "):
            continue
        if start is None and ln[3:].strip().startswith(title):
            start = i
        elif start is not None:
            return start, i
    if start is None:
        die(f"openspec/ideas.md has no `## {title}` section")
    return start, len(lines)


class Entry:
    def __init__(self, state: str, lines: list[str], start: int) -> None:
        self.state = state
        self.lines = lines
        self.start = start
        title = BOLD_RE.search(lines[0])
        head = title.group(1) if title else ENTRY_RE.match(lines[0]).group(2)  # type: ignore[union-attr]
        self.summary = one_line(head).rstrip(".")
        m = SLUG_IN_TITLE_RE.search(self.summary) or WIKI_RE.search(self.summary)
        self.slug = m.group(1) if m else slugify(self.summary)
        if m:  # the title ends `… (`slug`)` — the pointer already carries the slug
            self.summary = one_line(self.summary.replace(m.group(0), "")).rstrip(" .")
        self.body = "\n".join(lines)

    def as_dict(self) -> dict:
        return {
            "slug": self.slug,
            "state": self.state,
            "summary": self.summary,
            "lines": len(self.lines),
        }


class Ideas:
    """`openspec/ideas.md` as sections plus the § Raw ideas entries."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.path = root / "openspec" / "ideas.md"
        if not self.path.is_file():
            die(
                f"no openspec/ideas.md at the repo root ({root}) — this verb reshapes a repo's own "
                "ideas backlog; run it from the meta-repo or from a bootstrapped project"
            )
        self.lines = self.path.read_text(encoding="utf-8").splitlines()
        for n, ln in enumerate(self.lines, 1):
            if CONFLICT_RE.match(ln):
                die(
                    f"openspec/ideas.md line {n} is a conflict marker — finish the merge first; refusing to rewrite it"
                )
        self.entries = [Entry(*e) for e in self._raw_entries()]

    def bounds(self, title: str) -> tuple[int, int]:
        return section_bounds(self.lines, title)

    def _raw_entries(self) -> list[tuple[str, list[str], int]]:
        start, end = self.bounds(RAW)
        out: list[tuple[str, list[str], int]] = []
        buf: list[str] = []
        state = ""
        at = 0
        for i in range(start + 1, end):
            m = ENTRY_RE.match(self.lines[i])
            if m:
                if buf:
                    out.append((state, trim(buf), at))
                buf, state, at = [self.lines[i]], m.group(1), i
            elif buf:
                buf.append(self.lines[i])
        if buf:
            out.append((state, trim(buf), at))
        return out

    def raw_intro(self) -> list[str]:
        start, _ = self.bounds(RAW)
        first = self.entries[0].start if self.entries else None
        stop = first if first is not None else self.bounds(RAW)[1]
        return trim(self.lines[start + 1 : stop])

    def write(self, lines: list[str], *, apply: bool) -> None:
        body = "\n".join(lines).rstrip("\n") + "\n"
        if not apply:
            return
        fd, tmp = tempfile.mkstemp(prefix=".ideas.", dir=str(self.path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(body)
            os.replace(tmp, self.path)
        except OSError as exc:
            with contextlib.suppress(OSError):
                os.unlink(tmp)
            die(f"cannot write {self.path}: {exc}")


def trim(lines: list[str]) -> list[str]:
    """Drop leading and trailing blank lines (the caller re-adds the separators it wants)."""
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def guard_clean(root: Path, apply: bool, force: bool) -> None:
    if not apply or force:
        return
    status = gitmod.probe(root, "status", "--porcelain", "--", "openspec/ideas.md")
    if status:
        die(
            "openspec/ideas.md has uncommitted changes — commit or stash them first (or pass --force)"
        )


# --- archive -----------------------------------------------------------------


def archive_slugs(root: Path) -> dict[str, str]:
    """slug → directory name, for every openspec/changes/archive/<date>-<slug>/."""
    out: dict[str, str] = {}
    base = root / "openspec" / "changes" / "archive"
    if not base.is_dir():
        return out
    for e in sorted(os.scandir(base), key=lambda x: x.name):
        m = ARCHIVE_DIR_RE.match(e.name)
        if e.is_dir() and m:
            out[m.group(2)] = e.name
    return out


def capabilities_of(root: Path, dirname: str) -> list[str]:
    proposal = root / "openspec" / "changes" / "archive" / dirname / "proposal.md"
    if not proposal.is_file():
        return []
    caps: list[str] = []
    inside = False
    for ln in proposal.read_text(encoding="utf-8", errors="replace").splitlines():
        if ln.startswith("## "):
            inside = ln[3:].strip().lower().startswith("capabilit")
            continue
        if not inside or not ln.lstrip().startswith("-"):
            continue
        m = TICK_RE.search(ln)
        if m and m.group(1) not in caps:
            caps.append(m.group(1))
    return caps


def classify(
    entry: Entry, slugs: dict[str, str], overrides: dict[str, list[str]], root: Path
) -> dict:
    """→ {slug, dirname, capabilities, tier, note}."""
    out = {
        "slug": entry.slug,
        "summary": entry.summary,
        "dirname": "",
        "capabilities": [],
        "tier": "",
        "note": "",
    }
    m = POINTER_RE.search(entry.body)
    if m and m.group(2).strip("/") in set(slugs.values()):
        out["dirname"], out["tier"] = m.group(2).strip("/"), "1 (inline pointer)"
    elif m and m.group(1) in slugs:
        out["dirname"], out["tier"] = slugs[m.group(1)], "1 (inline pointer)"
    else:
        seen = set(TICK_RE.findall(entry.body)) | set(WIKI_RE.findall(entry.body)) | {entry.slug}
        hits = sorted(seen & set(slugs))
        if len(hits) == 1:
            out["dirname"], out["tier"] = slugs[hits[0]], "2 (body slug-mention)"
        elif len(hits) > 1:
            out["note"] = "ambiguous — mentions " + ", ".join(hits)
    if entry.slug in overrides:
        out["capabilities"], out["tier"] = overrides[entry.slug], "3 (operator)"
    elif out["dirname"]:
        out["capabilities"] = capabilities_of(root, out["dirname"])
        if not out["capabilities"]:
            out["note"] = f"{out['dirname']}/proposal.md names no § Capabilities"
    if not out["capabilities"] and not out["note"]:
        out["note"] = "no archive pointer and no unique slug mention"
    return out


def snapshot(ideas: Ideas, context: str, apply: bool) -> Path:
    d = ideas.root / "openspec" / "ideas-snapshots"
    target = d / f"{date.today().isoformat()}-{context}.md"
    n = 2
    while target.exists():
        target = d / f"{date.today().isoformat()}-{context}-{n}.md"
        n += 1
    if apply:
        d.mkdir(parents=True, exist_ok=True)
        target.write_text(ideas.path.read_text(encoding="utf-8"), encoding="utf-8")
    return target


def insert_bullets(
    lines: list[str], bounds: tuple[int, int], bullets: dict[str, list[str]]
) -> tuple[list[str], list[str]]:
    """Append each capability's bullets under its `### [`cap`]` heading; create missing ones."""
    start, end = bounds
    section = lines[start:end]
    created: list[str] = []
    for cap, rows in bullets.items():
        at = None
        for i, ln in enumerate(section):
            m = CAP_HEADING_RE.match(ln)
            if m and m.group(1) == cap:
                at = i
                break
        if at is None:
            closed = next(
                (i for i, ln in enumerate(section) if ln.startswith(CLOSED_HEADING)),
                len(trim(section)),
            )
            block = [
                f"### [`{cap}`](specs/{cap}/spec.md)",
                "Capability heading created by /alemax:archive-ideas — replace this line with the capability's own one-liner.",
                *rows,
                "",
            ]
            section = section[:closed] + block + section[closed:]
            created.append(cap)
            continue
        stop = at + 1
        while stop < len(section) and not section[stop].startswith("### "):
            stop += 1
        tail = stop
        while tail > at + 1 and not section[tail - 1].strip():
            tail -= 1
        section = section[:tail] + rows + section[tail:]
    return lines[:start] + section + lines[end:], created


def cmd_archive(a: argparse.Namespace) -> int:
    root = Path(a.root).resolve() if a.root else toplevel()
    ideas = Ideas(root)
    guard_clean(root, a.apply, a.force)
    overrides: dict[str, list[str]] = {}
    for item in a.capability:
        if "=" not in item:
            die(f"--capability wants <slug>=<capability>, got `{item}`", 2)
        k, v = item.split("=", 1)
        overrides[k.strip()] = [c.strip() for c in v.split(",") if c.strip()]
    slugs = archive_slugs(root)
    todo = [e for e in ideas.entries if e.state == "x" and (not a.only or e.slug in a.only)]
    unknown = sorted(set(a.only) - {e.slug for e in ideas.entries if e.state == "x"})
    if unknown:
        die("no `[x]` entry for: " + ", ".join(unknown))
    plan = [classify(e, slugs, overrides, root) for e in todo]
    resolved = {p["slug"]: p for p in plan if p["capabilities"]}
    bullets: dict[str, list[str]] = {}
    for p in plan:
        if not p["capabilities"]:
            continue
        m = ARCHIVE_DIR_RE.match(p["dirname"]) if p["dirname"] else None
        when = m.group(1) if m else date.today().isoformat()
        link = f" ([archive](changes/archive/{p['dirname']}/))" if p["dirname"] else ""
        row = f"- {when} — `{p['slug']}`{link} — {p['summary']}"
        for cap in p["capabilities"]:
            bullets.setdefault(cap, []).append(row)
    out = list(ideas.lines)
    created: list[str] = []
    if resolved:
        out, created = insert_bullets(out, ideas.bounds(ARCHIVED), bullets)
        kept = [e for e in ideas.entries if e.slug not in resolved]
        raw_start, raw_end = section_bounds(out, RAW)
        body: list[str] = [out[raw_start], "", *ideas.raw_intro()]
        for e in kept:
            body += ["", *e.lines]
        out = out[:raw_start] + body + [""] + out[raw_end:]
    snap = snapshot(ideas, a.context, a.apply and bool(resolved))
    ideas.write(out, apply=a.apply and bool(resolved))
    report = {
        "verb": "archive",
        "applied": bool(a.apply and resolved),
        "snapshot": str(snap.relative_to(root)) if resolved else None,
        "reshaped": [
            {"slug": p["slug"], "capabilities": p["capabilities"], "tier": p["tier"]}
            for p in plan
            if p["capabilities"]
        ],
        "unresolved": [
            {"slug": p["slug"], "summary": p["summary"], "note": p["note"]}
            for p in plan
            if not p["capabilities"]
        ],
        "created_headings": created,
        "archive_slugs": sorted(slugs),
    }
    if a.json:
        print(json.dumps(report, indent=2))
        return 0
    if not todo:
        print("no `[x]` entries in § Raw ideas — nothing to reshape")
        return 0
    print(
        ("applied" if report["applied"] else "[dry-run] would apply")
        + f" — {len(report['reshaped'])} entry(ies) to § Archived ideas, {len(report['unresolved'])} unresolved"
    )
    if resolved:
        print(f"snapshot: {report['snapshot']}" + ("" if a.apply else " (not written)"))
    for p in plan:
        if p["capabilities"]:
            print(f"  {p['slug']:<44} → {', '.join(p['capabilities'])}   [tier {p['tier']}]")
    for p in plan:
        if not p["capabilities"]:
            print(
                f"  {p['slug']:<44} ? {p['note']} — ask the operator, then pass --capability {p['slug']}=<capability>"
            )
    for cap in created:
        print(
            f"  note: created a new `{cap}` heading in § Archived ideas — give it a one-line description"
        )
    if not a.apply and resolved:
        print("re-run with --apply once the operator has confirmed each row")
    return 0


# --- reprioritise ------------------------------------------------------------


def cmd_reprioritise(a: argparse.Namespace) -> int:
    root = Path(a.root).resolve() if a.root else toplevel()
    ideas = Ideas(root)
    guard_clean(root, a.apply, a.force)
    open_entries = [e for e in ideas.entries if e.state == " "]
    by_slug = {e.slug: e for e in open_entries}
    start, end = ideas.bounds(NEXTUP)
    intro = [ln for ln in ideas.lines[start + 1 : end] if ln.strip() and not ln.startswith("- ")]
    existing = [ln for ln in ideas.lines[start + 1 : end] if ln.startswith("- ")]
    picks: list[str] = []
    if not a.clear:
        for raw in a.pick:
            token = raw.strip()
            if token.isdigit() and 1 <= int(token) <= len(open_entries):
                token = open_entries[int(token) - 1].slug
            if token not in by_slug:
                die(f"Unknown slug: {token} — it is not a `[ ]` entry in § Raw ideas")
            if token not in picks:
                picks.append(token)
    rows = [f"- {s} — {by_slug[s].summary}" for s in picks]
    if a.add and not a.clear:
        keep = [ln for ln in existing if not any(ln.startswith(f"- {s} ") for s in picks)]
        rows = keep + rows
    section = [ideas.lines[start], ""] + intro + (["", *rows] if rows else []) + [""]
    out = ideas.lines[:start] + section + ideas.lines[end:]
    changed = rows != existing
    ideas.write(out, apply=a.apply and changed)
    report = {
        "verb": "reprioritise",
        "applied": bool(a.apply and changed),
        "mode": "clear" if a.clear else ("add" if a.add else "replace"),
        "was": existing,
        "now": rows,
        "backlog": [e.as_dict() for e in open_entries],
    }
    if a.json:
        print(json.dumps(report, indent=2))
        return 0
    if not open_entries and not a.clear:
        print("no `[ ]` entries in § Raw ideas — no active backlog to reprioritise")
        return 0
    if not picks and not a.clear:
        print(
            f"§ Raw ideas has {len(open_entries)} `[ ]` entries; § Suggested next-up has {len(existing)}."
        )
        for i, e in enumerate(open_entries, 1):
            print(f"  {i:>3}. {e.slug:<44} {e.summary[:90]}")
        print("pick 3-5 with --pick <slug|index> (repeatable), or --clear to empty the section")
        return 0
    if len(rows) > NEXTUP_MAX:
        print(
            f"warning: § Suggested next-up is meant to be small (target 3-5, max {NEXTUP_MAX}) — this writes {len(rows)}"
        )
    print(
        ("applied" if report["applied"] else "[dry-run] would apply")
        + f" — mode {report['mode']}, {len(existing)} → {len(rows)} pointer(s)"
    )
    for ln in rows or ["  (section emptied)"]:
        print(f"  {ln}")
    if not a.apply and changed:
        print("re-run with --apply once the operator has confirmed the list")
    return 0


# --- list --------------------------------------------------------------------


def cmd_list(a: argparse.Namespace) -> int:
    root = Path(a.root).resolve() if a.root else toplevel()
    ideas = Ideas(root)
    wanted = {"open": " ", "x": "x"}.get(a.state)
    rows = [e for e in ideas.entries if wanted is None or e.state == wanted]
    if a.json:
        print(
            json.dumps(
                {"path": "openspec/ideas.md", "entries": [e.as_dict() for e in rows]}, indent=2
            )
        )
        return 0
    if not rows:
        print(f"no `{a.state}` entries in § Raw ideas")
        return 0
    for i, e in enumerate(rows, 1):
        print(f"{i:>3}. [{e.state}] {e.slug:<44} {e.summary[:90]}")
    print(f"— {len(rows)} of {len(ideas.entries)} entries in § Raw ideas")
    return 0


# --- main --------------------------------------------------------------------


def register(ap: argparse.ArgumentParser) -> None:
    ap.add_argument("--root", help="repo toplevel (default: git rev-parse --show-toplevel)")
    sub = ap.add_subparsers(dest="subcommand", required=True)

    s = sub.add_parser("list", help="print the § Raw ideas entries")
    s.add_argument(
        "--state", choices=("open", "x", "all"), default="all", help="which entries (default: all)"
    )
    s.add_argument("--json", action="store_true", help="machine-readable output")
    s.set_defaults(func=cmd_list)

    s = sub.add_parser(
        "archive", help="move classified `[x]` entries into § Archived ideas — by capability"
    )
    s.add_argument(
        "--only", action="append", default=[], help="restrict to this entry slug (repeatable)"
    )
    s.add_argument(
        "--capability",
        action="append",
        default=[],
        metavar="SLUG=CAP[,CAP]",
        help="the operator's tier-3 answer, or an override (repeatable)",
    )
    s.add_argument(
        "--context", default="pre-reshape", help="snapshot filename suffix (default: pre-reshape)"
    )
    s.add_argument(
        "--apply",
        action="store_true",
        help="write the snapshot and the mutation (default: dry-run)",
    )
    s.add_argument(
        "--force",
        action="store_true",
        help="apply even though openspec/ideas.md has uncommitted changes",
    )
    s.add_argument("--json", action="store_true", help="machine-readable plan")
    s.set_defaults(func=cmd_archive)

    s = sub.add_parser("reprioritise", help="rewrite § Suggested next-up with pointer-only entries")
    s.add_argument(
        "--pick",
        action="append",
        default=[],
        help="a `[ ]` entry slug or its 1-based index (repeatable)",
    )
    s.add_argument(
        "--add",
        action="store_true",
        help="append to the existing pointers instead of replacing them",
    )
    s.add_argument("--clear", action="store_true", help="empty § Suggested next-up")
    s.add_argument("--apply", action="store_true", help="write the mutation (default: dry-run)")
    s.add_argument(
        "--force",
        action="store_true",
        help="apply even though openspec/ideas.md has uncommitted changes",
    )
    s.add_argument("--json", action="store_true", help="machine-readable plan")
    s.set_defaults(func=cmd_reprioritise)
