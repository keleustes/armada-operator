"""collect.py — the deterministic half of /alemax:collect-feedback.

Drains `.local/feedback.md` across every active project in the operator's
`projects.yaml`, plus the meta-repo itself (which is never a row in that file
by design, and is reported under the name `claude-meta`).

Subcommands
  scan       every uncollected row, with a dedup candidate list and a
             harness/meta suggestion per row. Exit 0 rows found, 3 none.
  emit       append the kept rows to `openspec/ideas.md` § Raw ideas from a
             decisions file. Exit 0 written, 1 refused.
  annotate   stamp `(collected <date> → PR #<n>)` on each consumed source row,
             so a re-run skips it. Exit 0 done.

The decisions file is JSON: {"kept": [{"project": …, "ts": …, "slug": …,
"finding": …, "context": …}], "omitted": [{…, "reason": …}]}. `scan --json`
emits rows in exactly that shape minus the verdict — the skill adds it after
the operator confirms. Classification suggestions are advisory: the three
stages (dedup, harness-vs-meta, operator confirmation) are the skill's, and
nothing here decides for the operator.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path

from .. import git as gitmod
from ..io import die

ROW_RE = re.compile(r"^### (?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}) — (?P<kind>[a-z]+)(?P<rest>.*)$")
ENTRY_RE = re.compile(r"^  - name: (?P<name>\S+)\s*$")
FIELD_RE = re.compile(r"^    (?P<key>[a-z_]+): (?P<val>.*?)\s*$")
RAW_IDEAS_RE = re.compile(r"^##+\s+.*Raw ideas", re.IGNORECASE)
HARNESS_KW = re.compile(
    r"TodoWrite|Bash CWD|Skill tool|harness|Claude Code|prompt verbosity|Monitor|"
    r"RemoteTrigger|SendMessage|ListAgents|auto.?mode|classifier",
    re.IGNORECASE,
)
META_KW = re.compile(
    r"init-project|scaffolding/|meta/|openspec/|init-user|\.zshenv|aiml|init-machine|"
    r"broadcast|propagation|fork-sync|meta-version|projects\.yaml|repos\.yaml",
    re.IGNORECASE,
)
STOPWORDS = {
    "about",
    "after",
    "again",
    "because",
    "before",
    "being",
    "between",
    "could",
    "every",
    "first",
    "from",
    "into",
    "never",
    "other",
    "should",
    "still",
    "than",
    "that",
    "their",
    "them",
    "then",
    "there",
    "these",
    "thing",
    "this",
    "those",
    "through",
    "under",
    "until",
    "when",
    "where",
    "which",
    "while",
    "with",
    "would",
    "your",
    "claude",
    "session",
}


def meta_root() -> Path:
    top = gitmod.probe(Path.cwd(), "rev-parse", "--show-toplevel")
    if not top:
        die("not a git repository")
    root = Path(top)
    origin = (
        gitmod.probe(root, "remote", "get-url", "origin") or ""
    )  # no remote yet is a state, not a crash
    if "claude-meta" not in origin or root.name != "claude-meta":
        die(
            "context: claude-meta-only — this walks projects.yaml and opens a canonical PR.\n"
            f"  current: {root}\n  cd to your meta-repo clone first."
        )
    return root


def active_projects(root: Path) -> list[dict]:
    """The YAML subset projects.yaml actually uses: a flat list of scalar fields."""
    out, cur = [], None
    for line in (root / "projects.yaml").read_text(encoding="utf-8").splitlines():
        if m := ENTRY_RE.match(line):
            if cur:
                out.append(cur)
            cur = {"name": m["name"]}
        elif cur and (m := FIELD_RE.match(line)):
            cur[m["key"]] = m["val"].strip('"')
    if cur:
        out.append(cur)
    return [p for p in out if p.get("status") == "active"]


def parse_rows(path: Path) -> list[dict]:
    """Uncollected rows only — an annotated heading is already drained."""
    rows: list[dict] = []
    header, body = None, []

    def flush():
        nonlocal header, body
        if header and "(collected " not in header["rest"]:
            fields = {"context": "", "finding": ""}
            for line in body:
                for key in ("Context", "Finding"):
                    if line.startswith(f"**{key}:**"):
                        fields[key.lower()] = line[len(key) + 5 :].strip()
            rows.append({"ts": header["ts"], "kind": header["kind"], **fields})
        header, body = None, []

    for line in path.read_text(encoding="utf-8").splitlines():
        if m := ROW_RE.match(line):
            flush()
            header = {"ts": m["ts"], "kind": m["kind"], "rest": m["rest"]}
        elif header is not None:
            body.append(line)
    flush()
    return rows


def key_terms(text: str) -> list[str]:
    words = [w.lower() for w in re.findall(r"[A-Za-z][A-Za-z0-9_.-]{4,}", text)]
    seen = [w for w in dict.fromkeys(words) if w not in STOPWORDS]
    # Longer tokens carry more signal than the first six words of a paragraph.
    return sorted(seen, key=lambda w: (-len(w), w))[:6]


def proposals(root: Path) -> dict[str, str]:
    changes = root / "openspec" / "changes"
    out = {}
    for proposal in list(changes.glob("*/proposal.md")) + list(
        changes.glob("archive/*/proposal.md")
    ):
        try:
            out[str(proposal.parent.relative_to(root))] = proposal.read_text(
                encoding="utf-8", errors="ignore"
            ).lower()
        except OSError:
            continue
    return out


def dedup_candidates(corpus: dict[str, str], finding: str) -> list[str]:
    """A term in half the corpus says nothing; only rare terms are evidence."""
    terms = key_terms(finding)
    if not terms or not corpus:
        return []
    ceiling = max(1, len(corpus) // 5)
    rare = [t for t in terms if sum(1 for text in corpus.values() if t in text) <= ceiling]
    if len(rare) < 2:
        return []
    hits = {
        slug: sum(1 for t in rare if t in text)
        for slug, text in corpus.items()
        if sum(1 for t in rare if t in text) >= 2
    }
    return [p for p, _ in sorted(hits.items(), key=lambda kv: -kv[1])[:3]]


def slug_for(finding: str, taken: set[str]) -> str:
    base = "-".join(key_terms(finding)[:4]) or "finding"
    base = re.sub(r"[^a-z0-9-]+", "-", base.lower()).strip("-")[:48] or "finding"
    slug, n = base, 1
    while slug in taken:
        n += 1
        slug = f"{base}-{n}"
    taken.add(slug)
    return slug


def cmd_scan(a) -> int:
    root = meta_root()
    sources = [(p["name"], Path(p["path"])) for p in active_projects(root) if p.get("path")]
    sources.append(("claude-meta", root))  # never in projects.yaml, by design

    corpus = proposals(root)
    rows, warnings, taken = [], [], set()
    for name, path in sources:
        if not path.is_dir():
            warnings.append(f"{name}: path {path} not found, skipping")
            continue
        fb = path / ".local" / "feedback.md"
        if not fb.is_file():
            continue
        parsed = parse_rows(fb)
        if not parsed:
            continue
        for row in parsed:
            cands = dedup_candidates(corpus, row["finding"])
            blob = f"{row['context']} {row['finding']}"
            suggested = (
                "harness"
                if HARNESS_KW.search(blob)
                else "meta"
                if META_KW.search(blob)
                else "ambiguous"
            )
            rows.append(
                {
                    "project": name,
                    "source": str(fb),
                    "ts": row["ts"],
                    "kind": row["kind"],
                    "context": row["context"],
                    "finding": row["finding"],
                    "slug": slug_for(row["finding"], taken),
                    "dedup_candidates": cands,
                    "suggested_class": suggested,
                }
            )

    payload = {
        "rows": rows,
        "warnings": warnings,
        "sources": len(sources),
        "date": str(date.today()),
    }
    if a.json:
        print(json.dumps(payload, indent=2))
    else:
        for w in warnings:
            print(f"warn: {w}")
        for r in rows:
            flag = f"{r['suggested_class']}{'/dup?' if r['dedup_candidates'] else ''}"
            print(f"{r['project']:<22} {r['ts']}  {r['kind']:<8} {flag:<15} {r['finding'][:64]}")
            for c in r["dedup_candidates"]:
                print(f"{'':<22}   candidate: {c}")
        print(f"-- {len(rows)} uncollected row(s) across {len(sources)} source(s)")
    return 0 if rows else 3


def load_decisions(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        die(f"cannot read decisions file {path}: {exc}")
    if not isinstance(data.get("kept"), list):
        die("decisions file needs a 'kept' list")
    return data


def cmd_emit(a) -> int:
    root = meta_root()
    data = load_decisions(Path(a.decisions))
    kept = data["kept"]
    if not kept:
        print("nothing kept — no PR to open")
        return 3
    ideas = root / "openspec" / "ideas.md"
    lines = ideas.read_text(encoding="utf-8").splitlines()
    at = next((i for i, ln in enumerate(lines) if RAW_IDEAS_RE.match(ln)), None)
    if at is None:
        die(f"no '§ Raw ideas' heading in {ideas}")
    end = next(
        (i for i in range(at + 1, len(lines)) if lines[i].startswith("## ")),
        len(lines),
    )
    block = []
    for row in kept:
        block.append(f"- [ ] **{row['slug']}** — {row['finding']}")
        block.append(
            f"      _from {row['project']}, {row['ts']} ({row.get('kind', 'friction')})_"
            + (f" — context: {row['context']}" if row.get("context") else "")
        )
    while end > at + 1 and not lines[end - 1].strip():
        end -= 1
    lines[end:end] = ["", *block]
    ideas.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"appended {len(kept)} entr(y/ies) to {ideas.relative_to(root)} § Raw ideas")
    return 0


def cmd_annotate(a) -> int:
    meta_root()  # called for its refusal: annotate only runs inside a meta clone
    data = load_decisions(Path(a.decisions))
    stamp = f" (collected {date.today()} → PR #{a.pr})"
    by_source: dict[str, set[str]] = {}
    for row in data["kept"]:
        by_source.setdefault(row["source"], set()).add(row["ts"])
    done, failed = 0, []
    for source, stamps in by_source.items():
        path = Path(source)
        try:
            out = []
            for line in path.read_text(encoding="utf-8").splitlines():
                m = ROW_RE.match(line)
                if m and m["ts"] in stamps and "(collected " not in m["rest"]:
                    line += stamp
                    done += 1
                out.append(line)
            path.write_text("\n".join(out) + "\n", encoding="utf-8")
        except OSError as exc:
            failed.append(f"{source}: {exc}")
    for f in failed:
        print(f"warn: {f}")
    print(f"annotated {done} row(s) across {len(by_source) - len(failed)} file(s)")
    return 0


def register(ap: argparse.ArgumentParser) -> None:
    sub = ap.add_subparsers(dest="subcommand", required=True)
    sub.add_parser("scan", help="uncollected rows, with dedup candidates and a class suggestion")
    e = sub.add_parser("emit", help="append kept rows to openspec/ideas.md § Raw ideas")
    e.add_argument("--decisions", required=True, help="JSON file: {kept: [...], omitted: [...]}")
    n = sub.add_parser("annotate", help="stamp consumed source rows as collected")
    n.add_argument("--decisions", required=True)
    n.add_argument("--pr", required=True, help="the PR number the rows landed in")
    # --json belongs on each subcommand, so `<cmd> --json` works (the natural form).
    for sp in sub.choices.values():
        sp.add_argument("--json", action="store_true", help="machine-readable output")

    # Dispatch lives on the subparser, not in a trailing lookup: an unknown
    # subcommand is then argparse's error, with the valid choices, not a KeyError.
    _dispatch = {
        "scan": cmd_scan,
        "emit": cmd_emit,
        "annotate": cmd_annotate,
    }
    for _name, _sp in sub.choices.items():
        _sp.set_defaults(func=_dispatch[_name])
