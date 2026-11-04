"""Reading skill bodies: frontmatter, family/verb discovery on both harness layouts,
the commands a body invokes, and the structure two twins are compared on.

Two layouts, both conventions every plugin already follows (design D6):

    Claude   .claude/skills/<family>/skills/<verb>/SKILL.md      nested, plugin root has a manifest
    Codex    .agents/skills/<family>-<verb>/SKILL.md            flat, the name carries the prefix

Entries may be symlinks (a meta clone links `.claude/skills/<family>` into the plugin and
each Codex name into `plugins/<family>/meta/.agents/`); they are resolved, never skipped.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

# A code span is a command only when it STARTS with a program followed by a space (or is a
# relative script). `openspec/ideas.md` is a path, `openspec validate` is a command.
INVOKERS = (
    "uv run ",
    "uvx ",
    "python3 ",
    "python ",
    "bash ",
    "sh ",
    "./",
    "git ",
    "gh ",
    "openspec ",
)
FENCE_RE = re.compile(r"^```([a-zA-Z0-9_-]*)\s*$")
INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
STEP_RE = re.compile(r"^\s*(\d+)\.\s+(.*)$")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
INTENTIONAL = "<!-- twin: intentional -->"
SCRIPT_PATH_RE = re.compile(
    r"(?<![A-Za-z0-9_./-])((?:\.claude/skills/|\.agents/skills/)[A-Za-z0-9_./-]+?\.(?:py|sh)|scripts/[A-Za-z0-9_.-]+\.(?:py|sh))"
)


def split_frontmatter(text: str) -> tuple[list[str], list[str]]:
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return [], lines
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            return lines[: i + 1], lines[i + 1 :]
    return [], lines


def scalars(front: list[str]) -> dict[str, str]:
    """Top-level `key: value` lines of a frontmatter block. Nested blocks are not parsed."""
    out: dict[str, str] = {}
    for line in front:
        m = re.match(r"^([A-Za-z_-]+):\s*(.*?)\s*$", line)
        if m:
            out[m.group(1)] = m.group(2)
    return out


@dataclass
class Skill:
    family: str
    verb: str
    claude: Path | None = None
    codex: Path | None = None

    @property
    def codex_name(self) -> str:
        return f"{self.family}-{self.verb}"


@dataclass
class Family:
    name: str
    skills: dict[str, Skill] = field(default_factory=dict)


def _claude_families(root: Path) -> dict[str, dict[str, Path]]:
    out: dict[str, dict[str, Path]] = {}
    base = root / ".claude" / "skills"
    if not base.is_dir():
        return out
    for fam in sorted(base.iterdir()):
        skills = fam / "skills"
        if not skills.is_dir():
            continue
        verbs = {
            p.parent.name: p.resolve() for p in sorted(skills.glob("*/SKILL.md")) if p.is_file()
        }
        if verbs:
            out[fam.name] = verbs
    return out


def _codex_names(root: Path) -> dict[str, Path]:
    base = root / ".agents" / "skills"
    if not base.is_dir():
        return {}
    return {p.parent.name: p.resolve() for p in sorted(base.glob("*/SKILL.md")) if p.is_file()}


def split_codex_name(name: str, families: set[str]) -> tuple[str, str] | None:
    """`wiki-lint-concept-hubs` → (`wiki`, `lint-concept-hubs`), using known families;
    with no known family that prefixes it, the first segment."""
    for fam in sorted(families, key=len, reverse=True):
        if name.startswith(fam + "-"):
            return fam, name[len(fam) + 1 :]
    if "-" in name:
        fam, verb = name.split("-", 1)
        return fam, verb
    return None


def discover(root: Path, families: list[str] | None = None) -> dict[str, Family]:
    """Every family on either harness, each skill with whichever bodies exist."""
    claude = _claude_families(root)
    codex = _codex_names(root)
    known = set(claude)
    fams: dict[str, Family] = {}
    for fam, verbs in claude.items():
        f = fams.setdefault(fam, Family(fam))
        for verb, path in verbs.items():
            f.skills.setdefault(verb, Skill(fam, verb)).claude = path
    for name, path in codex.items():
        split = split_codex_name(name, known)
        if not split:
            continue
        fam, verb = split
        f = fams.setdefault(fam, Family(fam))
        f.skills.setdefault(verb, Skill(fam, verb)).codex = path
    if families:
        fams = {k: v for k, v in fams.items() if k in set(families)}
    return fams


def invocations(text: str) -> list[str]:
    """Every command a body invokes: fenced shell lines, and inline code that starts a
    command. Raw text, one entry per command."""
    out: list[str] = []
    in_fence = False
    lang = ""
    for line in text.split("\n"):
        m = FENCE_RE.match(line.strip())
        if m:
            if in_fence:
                in_fence = False
            else:
                in_fence, lang = True, m.group(1).lower()
            continue
        if in_fence:
            if lang in ("", "bash", "sh", "shell", "zsh", "console", "shellscript"):
                s = line.strip()
                if s and not s.startswith("#"):
                    out.append(s[2:] if s.startswith("$ ") else s)
            continue
        for span in INLINE_CODE_RE.findall(line):
            s = span.strip()
            if s.startswith(INVOKERS):
                out.append(s)
    return out


PLACEHOLDER_RE = re.compile(r"<[^<>`]+>|\$ARGUMENTS|\$\d|\[[^\]]*\]|\.\.\.|…")
QUOTED_VAR_PREFIX_RE = re.compile(r'"?\$\{[A-Z_]+\}/')


def normalise(cmd: str) -> str:
    """The command with harness-specific path phrasing and placeholders removed (D4)."""
    s = cmd.strip()
    s = re.sub(r"\s*\\\s*$", "", s)
    s = QUOTED_VAR_PREFIX_RE.sub("", s)
    # any directory chain ending in scripts/ → scripts/: the file is the identity, not
    # where a harness happens to keep it
    s = re.sub(r"(?<![A-Za-z0-9_])[A-Za-z0-9_./-]*?/?scripts/", "scripts/", s)
    s = s.replace('"', "")
    s = PLACEHOLDER_RE.sub("", s)
    s = re.sub(r"\s+", " ", s).strip(" ;|&")
    return s


def program(cmd: str) -> tuple[str, str]:
    """(`kind`, `identity`): what the command runs, independent of arguments.

    kind is `packaged` for `uv run --directory <d> <name> <verb>` / `uv run <name> <verb>`,
    `script` for anything that runs a `.py`/`.sh` file, `other` for git/gh/openspec/…"""
    s = normalise(cmd)
    toks = s.split()
    if not toks:
        return "other", ""
    m = re.match(r"uv run --directory (\S+) (\S+)(?: (\S+))?", s)
    if m:
        return "packaged", " ".join(t for t in m.groups() if t)
    m = re.match(r"uv run (?!--)(\S+)(?: (\S+))?", s)
    if m and not m.group(1).endswith((".py", ".sh")):
        return "packaged", " ".join(t for t in m.groups() if t)
    for t in toks[:4]:
        if t.endswith((".py", ".sh")):
            return "script", t.rsplit("/", 1)[-1]
    return "other", " ".join(toks[:2])


# Section headings one harness carries by design; never compared.
HARNESS_HEADINGS = {
    "working directory",
    "helper location",
    "todowrite fallback",
    "progress tracking",
    "governance preamble (run before any other step)",
}


@dataclass
class Structure:
    headings: list[str]
    steps: list[tuple[int, str]]
    commands: set[str]
    intentional: list[tuple[int, str]]

    @property
    def programs(self) -> set[tuple[str, str]]:
        """What the body runs, by program identity — the granularity twins must agree on.
        `other` commands (git, gh, openspec) vary legitimately between harnesses."""
        return {program(c) for c in self.commands if program(c)[0] != "other"}


def _first_sentence(s: str) -> str:
    s = re.sub(r"[`*_]", "", s)
    s = re.split(r"(?<=[.!?])\s|\s—\s|\s-\s", s, maxsplit=1)[0]
    return s.strip().rstrip(".:").lower()


def structure(text: str) -> Structure:
    """What two twins are compared on (D5): headings, numbered steps' first sentences,
    the normalised command set. Steps marked `<!-- twin: intentional -->` are set apart."""
    headings: list[str] = []
    steps: list[tuple[int, str]] = []
    intentional: list[tuple[int, str]] = []
    in_fence = False
    for line in text.split("\n"):
        if FENCE_RE.match(line.strip()):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        h = HEADING_RE.match(line)
        if h:
            title = re.sub(r"[`*_]", "", h.group(2)).strip().lower()
            if title not in HARNESS_HEADINGS:
                headings.append(title)
            continue
        st = STEP_RE.match(line)
        if st:
            n, rest = int(st.group(1)), st.group(2)
            if INTENTIONAL in rest:
                intentional.append((n, _first_sentence(rest.replace(INTENTIONAL, ""))))
            else:
                steps.append((n, _first_sentence(rest)))
    commands = {normalise(c) for c in invocations(text)}
    return Structure(headings, steps, commands, intentional)


def script_paths(text: str) -> list[tuple[int, str]]:
    """(line, path) for every script a body names."""
    out: list[tuple[int, str]] = []
    for i, line in enumerate(text.split("\n"), 1):
        for m in SCRIPT_PATH_RE.finditer(line):
            out.append((i, m.group(1)))
    return out
