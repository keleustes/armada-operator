#!/usr/bin/env python3
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""skill-check.py — the thin-skill contract (claude-meta specs `alemax-skills`, `project-skill-authoring`).

Walks every skill under `.claude/skills/` — the flat `*/SKILL.md` shape AND the plugin shape
`*/skills/*/SKILL.md`, where the outer directory carries `.claude-plugin/plugin.json` and each
inner skill is invoked as `/<plugin>:<name>` — plus `.claude/commands/**/*.md`. A skill is a
thin wrapper around one script or CLI verb: the body says which invocation to run and what to
report; the logic lives in the script, where `--help` and tests cover it. Runs from
`.pre-commit-config.yaml` when a skill or command is staged, and by hand from a session.

Exit 1 ("REFUSE") — for a staged file, or every file with --strict — on:

  F1  frontmatter missing `name`, `description` or `context`
      (`alemax-*` skills: `context` ∈ claude-meta-only | project | either; `fork` is the
      harness's own value and is accepted anywhere)
  F2  frontmatter missing `metadata.reviewed_model` or `metadata.reviewed` (YYYY-MM-DD) —
      the provenance that says which model the body was reviewed against, and when
  F3  frontmatter outside the Agent Skills limits (platform.claude.com, "Skill authoring best
      practices" § YAML frontmatter requirements): `name` over 64 characters, not lowercase
      letters, digits and hyphens, or containing a reserved word (`anthropic`, `claude`);
      `description` over 1,024 characters or containing an XML tag. A `<placeholder>` is an
      XML tag to a validator — write `{placeholder}` in a description; the body may keep `<…>`
  F4  a top-level frontmatter value that is a plain (unquoted) scalar containing `: ` or ending
      in `:`, on its first line or a continuation line — strict YAML (PyYAML `safe_load`)
      refuses it with "mapping values are not allowed here", and a parser that drops the whole
      frontmatter on error loses `allowed-tools` and `context` with it. A ` # comment` after
      the value is not part of it. Quote the value, or use a `>-` block scalar
  B1  a fenced block that is not single-line invocations: every non-comment line must start
      with one of uv · python3 · git · gh (or --allow <leader>) — no loops, no conditionals,
      no `&&`/`;`/`$( )`, no assignments; an untagged fence that looks like shell counts
  L1  a script path the body or `allowed-tools` names does not exist
      (`.claude/skills/<x>/scripts/<y>`, `${CLAUDE_SKILL_DIR}/<y>`, `scripts/<y>`)
  S1  a command file that delegates to a skill which does not exist
  D2  a command stub PAIRED with a skill (see D1) whose `description` is not a routing
      line — over 160 characters, or a restatement of the skill's own description
      (content-word containment ≥ 0.80). A routing line names the job and the skill and
      stops; it cannot drift, because there is nothing in it to drift. A stub that
      paraphrases can, and every one of the sixteen alemax pairs did: `update-skills.md`
      said "opens PRs" while its `SKILL.md` said "opens NO PR"; `complete-update.md`
      said "merges" while its `SKILL.md` said "never `git merge`". This check does not
      detect contradiction — a reliable contradiction detector is not a regex — it
      removes the room a contradiction needs.

There is no stub-pairing rule *requiring* a stub. It used to require
`.claude/commands/alemax/<name>.md` beside `.claude/skills/alemax-<name>/SKILL.md`; since the
alemax family ships as a plugin (change `alemax-as-plugin`), the plugin itself supplies
`/alemax:<name>` and a paired stub would be a second listing entry for the same capability.
A plugin skill has no stub by design.

Everything else is a WARN and never fails the commit: `name` differing from the directory,
a body over 120 lines, a fence with more than three invocations,
`metadata.reviewed` older than the file's last commit (the body changed after its review), a
`description` that says what the skill does but not when to use it (no `when`/`whenever`, no
sentence opening `Use`, `Run` or `Invoke`) — the model picks a skill from its description
alone, so a trigger-less one leaves the choice to guesswork — or one whose trigger starts past
the first 300 characters, where Claude Code's skill listing cuts the description, and:

  D1  DOUBLE LISTING — a command stub and a skill are the same capability, so the harness
      lists it twice and the listing is budgeted at ~1 % of the context window; on overflow
      the harness drops descriptions from the least-invoked entries, so a duplicate evicts a
      real capability's description. The fix is a plugin: a directory under `.claude/skills/`
      carrying `.claude-plugin/plugin.json` supplies the `/<plugin>:<name>` namespace, and the
      stub is deleted. Three pairing signals, in order — (a) NAME: the stub's path
      (`commands/<ns>/<n>.md` → `<n>`, `<ns>-<n>`, `<ns>:<n>`) or its normalized frontmatter
      `name` matches a skill's own spellings; (b) DELEGATION: the stub body names a skill that
      exists; (c) DESCRIPTION: content-word containment ≥ 0.60 with at least four content
      words on each side. (c) is the loose one and is why D1 only ever warns — two genuinely
      different capabilities phrased alike (a `-all` batch wrapper beside its singular) can
      trip it. D1 pairs against EVERY skill on disk, vendored ones included: the stub is the
      side that can be fixed.

Vendored skills are skipped, never edited to pass: a skill this repo did not author is
byte-comparable with its source, and an edit is lost at the next re-vendoring. `opsx` (the
vendored openspec plugin, rendered by `plugins/opsx/build.py`) and the pre-plugin `openspec-*`
layout are skipped by default —
`--include-vendored` checks it anyway, and `--skip <glob>` adds a project's own vendored
families (`wiki-*`). A glob matches the skill's own directory name or, for a plugin skill, its
plugin directory. Skipped directories are named in the header line, never silently dropped;
a command that delegates to a skipped skill still resolves (S1 sees every skill on disk).

--fix-dates stamps `metadata.reviewed: <today>` (and `reviewed_model` when missing) on every
skill whose only refusals are F2 — never on a skill that also fails B1/L1, so a fat body is
not stamped as reviewed. Reads the working tree, edits nothing else, opens no other file.

This checker and `skill-craft` (claude-meta's `marketplace/skill-craft/`, spec `skill-craft`)
read one platform guide, "Skill authoring best practices", two ways. This one enforces the
repo's thin-wrapper contract and gates commits. skill-craft is the guide itself — one skill per
practice, a `checker.py` for the deterministic checks, written criteria for the judgment ones —
run by hand when a skill is being written or a finding here is in doubt. Where the two overlap
they are one rule, copied: F3 is skill-craft's `frontmatter-name` + `frontmatter-description`,
the trigger warning is its `description-trigger` — same limits, same regexes (equal on
2026-10-05). The copy is deliberate: this file ships to projects and skill-craft stays outside
alemax, so neither imports the other. The guide is Anthropic's and it moves; skill-craft follows
it (`checker.py --check-source` reports when the guide's sections changed) and this file follows
skill-craft — a refresh that changes a limit or the regex lands there first, then here. The body
limit differs on purpose: 120 lines here, for a wrapper that says what to run; 500 there, the
guide's own budget. skill-craft's practice skills are knowledge, invoke-only and read now and
then, so they may run long — and this file walks only `.claude/`, never `marketplace/`.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ALLOWED_LEADERS = ("uv", "python3", "git", "gh")
ALEMAX_CONTEXTS = ("claude-meta-only", "project", "either")
VENDORED_SKIP = ("openspec-*", "opsx")  # vendored openspec: flat (pre-plugin) and the opsx plugin
SHELL_LANGS = {"bash", "sh", "shell", "zsh", "console", "shellscript"}
SHELL_HINTS = re.compile(
    r"^\s*(for |while |until |if |case |function |fi$|done$|esac$|do$|then$|else$|elif |\[\[? |set -|export |source |#!/|local |declare |[A-Za-z_][A-Za-z0-9_]*=)"
)
SHELL_INLINE = re.compile(r"\$\(|&&|\|\||2>/dev/null|\bthen\b|\bdo\b")
CONTROL = re.compile(r"^\s*(for|while|until|if|case|function|fi|done|esac|do|then|else|elif)\b")
FENCE_RE = re.compile(r"^(```+|~~~+)\s*([A-Za-z0-9_+-]*)\s*$")
FRONT_LIMIT = 8192
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PATH_RE = re.compile(
    r"(\$\{CLAUDE_SKILL_DIR\}/[A-Za-z0-9_./-]+|\.claude/skills/[A-Za-z0-9_-]+/[A-Za-z0-9_./-]+|(?<![A-Za-z0-9_./-])scripts/[A-Za-z0-9_./-]+\.(?:py|sh))"
)
STUB_REF_RE = re.compile(
    r"\.claude/skills/(?:[A-Za-z0-9_-]+/skills/)?([A-Za-z0-9_-]+)/SKILL\.md|`([A-Za-z0-9_-]+)` skill\b"
)
# Skills the Claude Code harness ships itself — a stub may delegate to one without a
# body under .claude/skills/ (the `/security` stub wraps the built-in `security-review`).
HARNESS_SKILLS = frozenset({"security-review", "code-review", "simplify", "init"})
BODY_MAX_LINES = 120
FENCE_MAX_INVOCATIONS = 3

# F3 — the Agent Skills frontmatter limits, verbatim from the platform docs ("Skill authoring
# best practices" § YAML frontmatter requirements). Not tunable: a skill over them is one a
# validator may reject, whatever this repo thinks of it. The same values as skill-craft's
# `checker.py` (NAME_MAX · NAME_RESERVED · DESC_MAX · XML_TAG_RE, and TRIGGER_RE for WHEN_RE
# below); a guide refresh updates them there first, then here — see the header.
NAME_RE = re.compile(r"^[a-z0-9-]{1,64}$")
NAME_RESERVED = ("anthropic", "claude")
DESC_MAX_CHARS = 1024
XML_TAG_RE = re.compile(r"</?[A-Za-z][^<>]*>")
# W — a trigger: where the description tells the model WHEN, not only WHAT.
WHEN_RE = re.compile(r"\bwhen(ever)?\b|(^|[.;:—]\s*)(use|run|invoke)\b", re.IGNORECASE)
# W — Claude Code's skill listing shows each description cut to its first 300 characters
# (measured 2026-10-05: 299 plus an ellipsis); a trigger past the cut never reaches the model.
LISTING_VISIBLE_CHARS = 300

# D1/D2 — the stub-versus-skill pair.
# 160 chars: the four `/opsx:*` stub descriptions on canonical run 54-83 chars, so a routing
# line has ~2x headroom; a paragraph does not fit. PR #277 cut the sixteen alemax stubs to
# routing lines and their descriptions landed in the same band.
STUB_DESC_MAX_CHARS = 160
PAIR_CONTAINMENT = 0.60  # D1 warn: these two entries are one capability
RESTATE_CONTAINMENT = 0.80  # D2 refuse: the stub restates the skill instead of routing to it
MIN_CONTENT_WORDS = 4  # below this a description carries no signal; never pair on it
WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]*")
NAME_NORM_RE = re.compile(r"[^a-z0-9]+")
STOPWORDS = frozenset(
    [
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "in",
        "into",
        "is",
        "it",
        "its",
        "of",
        "on",
        "or",
        "that",
        "the",
        "then",
        "this",
        "to",
        "use",
        "used",
        "uses",
        "user",
        "users",
        "want",
        "wants",
        "when",
        "where",
        "which",
        "with",
        "you",
        "your",
        "not",
        "no",
        "all",
        "one",
        "two",
    ]
)


class Skill:
    """One SKILL.md on disk: flat (`.claude/skills/<dir>/`) or inside a plugin
    (`.claude/skills/<plugin>/skills/<dir>/`, invoked as `/<plugin>:<dir>`)."""

    __slots__ = ("dir_name", "path", "plugin")

    def __init__(self, path: Path, plugin: str | None) -> None:
        self.path = path
        self.dir_name = path.parent.name
        self.plugin = plugin

    @property
    def family(self) -> str:
        """The `alemax-*` / `retrofit-*` prefix a flat directory carries, which a plugin
        skill carries in its plugin directory instead."""
        return self.plugin or self.dir_name

    def names(self) -> set[str]:
        """Every spelling a command file might use to name this skill."""
        out = {self.dir_name}
        if self.plugin:
            out |= {self.plugin, f"{self.plugin}-{self.dir_name}", f"{self.plugin}:{self.dir_name}"}
        return out


def discover_skills(skills_dir: Path) -> list[Skill]:
    """Every skill under `.claude/skills/`, flat and plugin-nested, sorted by path."""
    if not skills_dir.is_dir():
        return []
    found = [Skill(p, None) for p in skills_dir.glob("*/SKILL.md")]
    found += [Skill(p, p.parent.parent.parent.name) for p in skills_dir.glob("*/skills/*/SKILL.md")]
    return sorted(found, key=lambda s: s.path)


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


# --- frontmatter (the YAML subset SKILL.md files use) ---------------------------


def split_frontmatter(text: str) -> tuple[list[str] | None, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, text
    for i in range(1, min(len(lines), 400)):
        if lines[i].strip() == "---":
            return lines[1:i], "\n".join(lines[i + 1 :])
    return None, text


def plain_scalar_colons(lines: list[str]) -> list[str]:
    """Top-level keys whose plain (unquoted, non-block) value YAML reads as a mapping (rule F4):
    `: ` anywhere, or a trailing `:`, on the first line or an indented continuation line. A
    ` #` ends the value — what follows is a comment."""
    bad: list[str] = []
    key: str | None = None  # the key whose plain scalar the next indented line continues
    for line in lines:
        m = re.match(r"^([A-Za-z0-9_-]+):(?:[ \t]+(.*))?$", line)
        if m:
            key, text = m.group(1), (m.group(2) or "").strip()
            if not text or text[0] in "\"'>|[{&*!#":
                key = None  # a nested mapping, a block, a quoted or a flow value
                continue
        elif key and line[:1] in " \t" and line.strip():
            text = line.strip()
        else:
            key = None
            continue
        text = re.split(r"[ \t]#", text, maxsplit=1)[0].rstrip()
        if (": " in text or text.endswith(":")) and key not in bad:
            bad.append(key)
    return bad


def scalar(raw: str) -> str:
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        return raw[1:-1]
    return raw


def parse_frontmatter(lines: list[str]) -> dict[str, object]:
    fm: dict[str, object] = {}
    current: str | None = None
    block: tuple[str, str, list[str]] | None = None  # (key, `>` or `|`, lines) of a block scalar

    def close_block() -> None:
        if block:
            key, style, buf = block
            text = "\n".join(buf).strip()
            # Folded: a line break is a space; n blank lines are n line breaks.
            fm[key] = (
                re.sub(r"\n(\n*)", lambda m: m.group(1) or " ", text) if style == ">" else text
            )

    for line in lines:
        indent = len(line) - len(line.lstrip(" "))
        if block and (indent > 0 or not line.strip()):
            block[2].append(line.strip())
            continue
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if indent == 0:
            close_block()
            block = None
            current = None
            if ":" not in line:
                continue
            key, tail = line.split(":", 1)
            key, tail = key.strip(), tail.strip()
            header = tail.split(" #", 1)[0].strip()  # `description: >- # note` is still a block
            if header[:1] in (">", "|") and header.rstrip("+-0123456789") in (">", "|"):
                block = (key, header[0], [])
            elif tail.startswith("{") and tail.endswith("}"):
                inner: dict[str, str] = {}
                for part in tail[1:-1].split(","):
                    if ":" in part:
                        k, v = part.split(":", 1)
                        inner[k.strip()] = scalar(v)
                fm[key] = inner
            elif tail == "":
                fm[key] = {}
                current = key
            else:
                fm[key] = scalar(tail)
        elif current is not None and isinstance(fm.get(current), dict) and ":" in line:
            k, v = line.strip().split(":", 1)
            fm[current][k.strip()] = scalar(v)  # type: ignore[index]
    close_block()
    return fm


def stamp_dates(path: Path, fm_lines: list[str], body: str, today: str, model: str) -> None:
    """Rewrite the frontmatter with metadata.reviewed/reviewed_model set. Block style only."""
    out: list[str] = []
    in_meta = False
    seen_meta = False
    meta_keys: set[str] = set()

    def close_meta() -> None:
        if "reviewed_model" not in meta_keys:
            out.append(f"  reviewed_model: {model}")
        if "reviewed" not in meta_keys:
            out.append(f"  reviewed: {today}")

    for line in fm_lines:
        indent = len(line) - len(line.lstrip(" "))
        if in_meta and indent == 0:
            close_meta()
            in_meta = False
        if indent == 0 and line.split(":", 1)[0].strip() == "metadata":
            tail = line.split(":", 1)[1].strip()
            seen_meta = True
            if tail.startswith("{"):
                inner = {}
                for part in tail[1:-1].split(","):
                    if ":" in part:
                        k, v = part.split(":", 1)
                        inner[k.strip()] = scalar(v)
                inner.setdefault("reviewed_model", model)
                inner["reviewed"] = today
                out.append("metadata:")
                out += [f"  {k}: {v}" for k, v in inner.items()]
                continue
            in_meta = True
            out.append("metadata:")
            continue
        if in_meta:
            k = line.strip().split(":", 1)[0]
            if k == "reviewed":
                out.append(f"  reviewed: {today}")
                meta_keys.add(k)
                continue
            meta_keys.add(k)
        out.append(line)
    if in_meta:
        close_meta()
    if not seen_meta:
        out += ["metadata:", f"  reviewed_model: {model}", f"  reviewed: {today}"]
    path.write_text(
        "---\n" + "\n".join(out) + "\n---\n" + body + ("\n" if not body.endswith("\n") else ""),
        encoding="utf-8",
    )


# --- body checks -------------------------------------------------------------


# A body that spells out its command's exit codes is documenting the code from outside it.
# The two copies then drift, which is how a skill body came to describe a guard its own code
# had disarmed: the body said the directory sweep was guarded, the code computed the guard
# with the broken test that made it fire (#282 -> #286). Exit codes belong to the capability
# spec and the module docstring, which are what a change actually edits.
EXIT_CODE_PROSE = re.compile(
    r"\b(?:exit(?:s|\s+code)?|returns?)\s+(?:code\s+)?[0-9]\b"
    r"|\bexit\s+[0-9]\s+means\b"
    r"|\bnon-zero\s+(?:exit|means)\b",
    re.IGNORECASE,
)
EXIT_CODE_MAX = 1  # one passing mention is a pointer; several is a transcription


def fences(body: str) -> list[tuple[str, list[str], int]]:
    """(lang, lines, start_line_no) for every fenced block."""
    out = []
    lang: str | None = None
    buf: list[str] = []
    start = 0
    marker = ""
    for i, line in enumerate(body.splitlines(), 1):
        m = FENCE_RE.match(line)
        if lang is None and m:
            lang, buf, start, marker = m.group(2).lower(), [], i, m.group(1)[0]
        elif lang is not None and m and m.group(1)[0] == marker and not m.group(2):
            out.append((lang, buf, start))
            lang = None
        elif lang is not None:
            buf.append(line)
    return out


def logical_lines(lines: list[str]) -> list[str]:
    out: list[str] = []
    carry = ""
    for raw in lines:
        s = raw.rstrip()
        if s.endswith("\\"):
            carry += s[:-1] + " "
            continue
        out.append((carry + s).strip())
        carry = ""
    if carry:
        out.append(carry.strip())
    return out


def looks_like_shell(lines: list[str]) -> bool:
    return any(SHELL_HINTS.match(ln) or SHELL_INLINE.search(ln) for ln in lines)


def check_fence(lang: str, lines: list[str], allowed: tuple[str, ...]) -> tuple[list[str], int]:
    """Return (problems, invocation_count) for one fence."""
    problems: list[str] = []
    n_inv = 0
    for ln in logical_lines(lines):
        if not ln or ln.startswith("#"):
            continue
        if ln.startswith("$ "):
            ln = ln[2:].strip()
        if CONTROL.match(ln):
            problems.append(
                f"control flow `{ln.split()[0]}` — a loop or branch belongs in the script"
            )
            continue
        if re.search(r"&&|\|\||\$\(|`|;\s", ln) or re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", ln):
            problems.append(f"not a single invocation: `{ln[:60]}`")
            continue
        leader = ln.split()[0]
        if leader.startswith("/"):
            continue  # a slash-command example
        if leader not in allowed:
            problems.append(
                f"`{leader}` is not an allowed leader ({' · '.join(allowed)}); the step belongs in the script"
            )
            continue
        n_inv += 1
    return problems, n_inv


def resolve_ref(ref: str, repo: Path, skill_dir: Path) -> Path:
    ref = ref.rstrip(".,;:)")
    if ref.startswith("${CLAUDE_SKILL_DIR}/"):
        return skill_dir / ref[len("${CLAUDE_SKILL_DIR}/") :]
    if ref.startswith(".claude/"):
        return repo / ref
    return skill_dir / ref


# --- D1/D2: is this stub and this skill one capability? ----------------------


def stem(word: str) -> str:
    """Crude suffix trim so `generate`/`generated` and `investigate`/`investigating`
    are the same content word. Wrong for irregular forms; the thresholds absorb it."""
    for suffix in ("ing", "ed", "es", "s"):
        if len(word) > len(suffix) + 3 and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


def content_words(text: str) -> set[str]:
    return {
        stem(w) for w in (m.group(0).lower() for m in WORD_RE.finditer(text)) if w not in STOPWORDS
    }


def containment(a: set[str], b: set[str]) -> float:
    """|a ∩ b| / min(|a|, |b|) — "one restates the other", not "these overlap"."""
    if len(a) < MIN_CONTENT_WORDS or len(b) < MIN_CONTENT_WORDS:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def normalize_name(raw: str) -> str:
    return NAME_NORM_RE.sub("-", raw.strip().lower()).strip("-")


def stub_spellings(rel: str, fm: dict[str, object]) -> set[str]:
    """Every name this command file might share with a skill: from its path
    (`.claude/commands/<ns>/<stem>.md`) and from its frontmatter `name`."""
    parts = Path(rel).parts
    stem_name = Path(rel).stem
    out = {stem_name}
    if len(parts) >= 4:  # .claude / commands / <ns> / <file>.md
        ns = parts[2]
        out |= {ns, f"{ns}-{stem_name}", f"{ns}:{stem_name}"}
    named = fm.get("name")
    if isinstance(named, str) and named.strip():
        norm = normalize_name(named)
        out |= {norm, norm.replace("-", ":", 1)}
    return out


def pair_stub(
    rel: str, fm: dict[str, object], body: str, skills: list[Skill], descs: dict[Path, str]
) -> tuple[Skill, str, float] | None:
    """The skill this command file is a second listing entry for, and how we know."""
    spellings = stub_spellings(rel, fm)
    for skill in skills:
        if skill.names() & spellings:
            return skill, "name", 1.0
    for m in STUB_REF_RE.finditer(body):
        named = m.group(1) or m.group(2)
        for skill in skills:
            if named and named in skill.names():
                return skill, "delegation", 1.0
    desc = str(fm.get("description") or "")
    if not desc:
        return None
    mine = content_words(desc)
    best: tuple[Skill, str, float] | None = None
    for skill in skills:
        score = containment(mine, content_words(descs.get(skill.path, "")))
        if score >= PAIR_CONTAINMENT and (best is None or score > best[2]):
            best = (skill, "description", score)
    return best


# --- main --------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="skill-check.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--repo", help="repo root (default: git toplevel of the cwd, else the cwd)")
    ap.add_argument("--strict", action="store_true", help="refuse for every file, staged or not")
    ap.add_argument(
        "--no-git", action="store_true", help="no staged set, no review-vs-commit-date check"
    )
    ap.add_argument(
        "--skip",
        action="append",
        default=[],
        help="skill directory name glob to leave out (repeatable), e.g. 'wiki-*'",
    )
    ap.add_argument(
        "--include-vendored",
        action="store_true",
        help=f"check the vendored skills too ({' · '.join(VENDORED_SKIP)}), which are skipped by default",
    )
    ap.add_argument(
        "--allow",
        action="append",
        default=[],
        help="an extra invocation leader (repeatable), e.g. openspec",
    )
    ap.add_argument(
        "--fix-dates",
        action="store_true",
        help="stamp metadata.reviewed/reviewed_model on skills whose only refusal is F2",
    )
    ap.add_argument(
        "--date", default=date.today().isoformat(), help="date for --fix-dates (default: today)"
    )
    ap.add_argument(
        "--model",
        default="claude-5",
        help="reviewed_model for --fix-dates when missing (default: claude-5)",
    )
    args = ap.parse_args(argv)
    repo = Path(args.repo).resolve() if args.repo else default_repo()
    allowed = ALLOWED_LEADERS + tuple(args.allow)

    staged: set[str] = set()
    if not args.no_git:
        out = git(repo, "diff", "--cached", "--name-only", "-z")
        staged = {p for p in (out or "").split("\0") if p}

    refusals: list[str] = []
    warnings: list[str] = []
    fixed: list[str] = []

    def verdict(rel: str, hard: bool, msg: str) -> None:
        (refusals if (args.strict or rel in staged) and hard else warnings).append(f"{rel}: {msg}")

    from fnmatch import fnmatch

    skipped = list(args.skip) + ([] if args.include_vendored else list(VENDORED_SKIP))

    skills_dir = repo / ".claude" / "skills"
    all_skills = discover_skills(skills_dir)

    def is_skipped(s: Skill) -> bool:
        return any(fnmatch(s.dir_name, g) or fnmatch(s.family, g) for g in skipped)

    skills = [s for s in all_skills if not is_skipped(s)]
    existing_skills: set[str] = set()
    skill_descs: dict[Path, str] = {}
    for s in all_skills:
        existing_skills |= s.names()
        # D1 pairs against every skill on disk, vendored included: the stub is the
        # side a repo can fix, so a stub doubling a vendored skill must still surface.
        head, _ = split_frontmatter(s.path.read_text(encoding="utf-8", errors="replace"))
        skill_descs[s.path] = str(parse_frontmatter(head).get("description") or "") if head else ""

    for skill in skills:
        path = skill.path
        rel = str(path.relative_to(repo))
        name = skill.dir_name
        text = path.read_text(encoding="utf-8", errors="replace")
        fm_lines, body = split_frontmatter(text)
        if fm_lines is None:
            verdict(rel, True, "F1: no YAML frontmatter")
            continue
        fm = parse_frontmatter(fm_lines)
        hard_other = False  # B1/L1 refusals block --fix-dates
        for key in ("name", "description", "context"):
            if not fm.get(key):
                verdict(rel, True, f"F1: frontmatter lacks `{key}`")
        for key in plain_scalar_colons(fm_lines):
            verdict(rel, True, f"F4: `{key}` is a plain scalar containing ': ' — quote it")
        if fm.get("name") and fm["name"] != name:
            warnings.append(
                f"{rel}: W: name `{fm['name']}` differs from the directory `{name}` (the directory is the command)"
            )
        fm_name = str(fm.get("name") or "")
        if fm_name and not NAME_RE.match(fm_name):
            verdict(
                rel, True, f"F3: name `{fm_name}` is not 1-64 lowercase letters, digits and hyphens"
            )
        if any(word in fm_name for word in NAME_RESERVED):
            verdict(
                rel,
                True,
                f"F3: name `{fm_name}` contains a reserved word ({' · '.join(NAME_RESERVED)})",
            )
        desc = str(fm.get("description") or "")
        if len(desc) > DESC_MAX_CHARS:
            verdict(
                rel, True, f"F3: description is {len(desc)} characters — over {DESC_MAX_CHARS:,}"
            )
        if tags := sorted(set(XML_TAG_RE.findall(desc))):
            verdict(
                rel,
                True,
                f"F3: description contains XML tag(s) {' '.join(tags)} — write a placeholder as `{{name}}`",
            )
        trigger = WHEN_RE.search(desc)
        if desc and not trigger:
            warnings.append(
                f"{rel}: W: description says what the skill does but not when to use it — add a `Use when …` trigger"
            )
        elif trigger and trigger.start() >= LISTING_VISIBLE_CHARS - 1:
            warnings.append(
                f"{rel}: W: description's trigger starts at character {trigger.start()}, past the"
                f" {LISTING_VISIBLE_CHARS} the skill listing shows — lead with it"
            )
        ctx = fm.get("context")
        if skill.family.startswith("alemax") and ctx and ctx not in (*ALEMAX_CONTEXTS, "fork"):
            verdict(rel, True, f"F1: context `{ctx}` is not one of {' | '.join(ALEMAX_CONTEXTS)}")
        meta = fm.get("metadata") if isinstance(fm.get("metadata"), dict) else {}
        missing_prov = []
        if not meta.get("reviewed_model"):
            missing_prov.append("reviewed_model")
        reviewed = str(meta.get("reviewed", "")) if meta else ""
        if not DATE_RE.match(reviewed):
            missing_prov.append("reviewed (YYYY-MM-DD)")
        if missing_prov:
            verdict(
                rel,
                True,
                f"F2: metadata lacks {', '.join(missing_prov)} — which model reviewed this body, and when",
            )
        n_body = len(body.splitlines())
        if n_body > BODY_MAX_LINES:
            warnings.append(
                f"{rel}: W: body is {n_body} lines — over {BODY_MAX_LINES}; a thin skill says what to run and what to report"
            )
        exit_hits = [
            i + 1
            for i, ln in enumerate(body.splitlines())
            if EXIT_CODE_PROSE.search(ln) and not ln.lstrip().startswith(("|", ">"))
        ]
        if len(exit_hits) > EXIT_CODE_MAX:
            verdict(
                rel,
                False,
                f"E1: body states its command's exit codes on {len(exit_hits)} lines "
                f"({', '.join(str(n) for n in exit_hits[:5])}"
                f"{', …' if len(exit_hits) > 5 else ''}) — that belongs to the spec and the "
                "module docstring; a body restating it drifts from it",
            )
        for lang, lines, start in fences(body):
            if lang in SHELL_LANGS or (not lang and looks_like_shell(lines)):
                problems, n_inv = check_fence(lang, lines, allowed)
                for prob in problems:
                    verdict(rel, True, f"B1: fence at line {start}: {prob}")
                    hard_other = True
                if n_inv > FENCE_MAX_INVOCATIONS:
                    warnings.append(
                        f"{rel}: W: fence at line {start} holds {n_inv} invocations — a procedure the script could carry"
                    )
        refs = set(PATH_RE.findall(body)) | set(PATH_RE.findall(str(fm.get("allowed-tools", ""))))
        for ref in sorted(refs):
            target = resolve_ref(ref, repo, path.parent)
            if not target.exists():
                verdict(
                    rel,
                    True,
                    f"L1: names `{ref}` but {target.relative_to(repo) if target.is_relative_to(repo) else target} does not exist",
                )
                hard_other = True
        if not args.no_git and DATE_RE.match(reviewed):
            last = (git(repo, "log", "-1", "--format=%cs", "--", rel) or "").strip()
            if last and last > reviewed:
                warnings.append(
                    f"{rel}: W: metadata.reviewed {reviewed} is older than the last commit ({last}) — the body changed after its review"
                )
        if args.fix_dates and missing_prov and not hard_other:
            stamp_dates(path, fm_lines, body, args.date, args.model)
            fixed.append(rel)

    commands_dir = repo / ".claude" / "commands"
    command_files = sorted(commands_dir.rglob("*.md")) if commands_dir.is_dir() else []
    n_doubled = 0
    for path in command_files:
        rel = str(path.relative_to(repo))
        text = path.read_text(encoding="utf-8", errors="replace")
        for m in STUB_REF_RE.finditer(text):
            named = m.group(1) or m.group(2)
            if named and named not in existing_skills and named not in HARNESS_SKILLS:
                verdict(
                    rel,
                    True,
                    f"S1: delegates to `{named}` but no such skill exists under .claude/skills/",
                )

        cmd_fm_lines, cmd_body = split_frontmatter(text)
        cmd_fm = parse_frontmatter(cmd_fm_lines) if cmd_fm_lines else {}
        pair = pair_stub(rel, cmd_fm, cmd_body, all_skills, skill_descs)
        if pair is None:
            continue
        partner, how = pair[0], pair[1]
        n_doubled += 1
        via = f"{how} match" + (f", containment {pair[2]:.2f}" if how == "description" else "")
        partner_rel = partner.path.relative_to(repo)
        warnings.append(
            f"{rel}: D1: double listing — this stub and `{partner_rel}` are one capability ({via}); "
            "the listing is budgeted and an overflow drops descriptions by usage, so a duplicate evicts "
            f"a real one. Ship the family as a plugin ({'/' + partner.plugin + ':' + partner.dir_name if partner.plugin else '.claude-plugin/plugin.json beside the skills'}) and delete the stub."
        )
        desc = str(cmd_fm.get("description") or "")
        restate = containment(content_words(desc), content_words(skill_descs.get(partner.path, "")))
        if len(desc) > STUB_DESC_MAX_CHARS:
            verdict(
                rel,
                True,
                f"D2: paired with `{partner_rel}` but its description is {len(desc)} chars "
                f"(over {STUB_DESC_MAX_CHARS}) — a paired stub carries a routing line, not a summary; "
                "substance in both files is what drifts",
            )
        elif restate >= RESTATE_CONTAINMENT:
            verdict(
                rel,
                True,
                f"D2: paired with `{partner_rel}` and its description restates the skill's "
                f"(containment {restate:.2f} ≥ {RESTATE_CONTAINMENT:.2f}) — say what it runs and "
                "name the skill; the skill is the single source",
            )

    n_skipped = len(all_skills) - len(skills)
    n_plugins = len({s.plugin for s in skills if s.plugin})
    print(
        f"skill-check: {repo} — {len(skills)} skill(s)"
        + (f" in {n_plugins} plugin(s)" if n_plugins else "")
        + f", {len(command_files)} command file(s)"
        + (f" of which {n_doubled} double a skill" if n_doubled else "")
        + (f", {n_skipped} skipped ({' · '.join(skipped)})" if n_skipped else "")
        + f"{' [strict]' if args.strict else ''}{' [no-git]' if args.no_git else ''}"
    )
    for line in refusals:
        print(f"REFUSE {line}")
    for line in warnings:
        print(f"WARN {line}")
    for line in fixed:
        print(f"FIXED {line}: metadata.reviewed = {args.date}")
    print(
        f"skill-check: {len(refusals)} refusal(s), {len(warnings)} warning(s) — {'FAIL' if refusals else 'pass'}"
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
