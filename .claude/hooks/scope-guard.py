#!/usr/bin/env python3
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""scope-guard.py — PreToolUse hook: a session acts only inside its own repo.

Claude Code runs this before Read, Edit, Write, MultiEdit, NotebookEdit, Bash,
Glob and Grep (the `hooks.PreToolUse` entry in `.claude/settings-template.json`,
folded into `settings.local.json` by `bin/reconcile-settings.py`). It reads the
hook JSON on stdin, extracts every path the call names, and refuses — exit 2,
one line on stderr, which Claude sees as the reason — any path outside this
session's scope (claude-meta specs `sibling-access-practice` and
`project-environments`). Everything else is exit 0 and silent.

Inside scope, always:
  - the repo root — `$CLAUDE_PROJECT_DIR`, else the git toplevel of the hook's
    `cwd` — with its `.local/`, its `.claude/worktrees/**`, and, from a worktree,
    the main checkout the worktree is linked from
  - the sibling delivery worktree `<root>-claude-meta` (what `broadcast-update.sh`
    stages beside a project)
  - `$TMPDIR`, `/tmp`, `/private/tmp`, `/var/folders`, `/private/var/folders`
  - toolchains: `/opt/homebrew`, `/Volumes/*/opt`, `/usr`, `/bin`, `/sbin`,
    `/etc`, `/dev`
  - `$HOME/.claude/**`, `$HOME/.cache`, `$HOME/.local/share/uv`
  - READ-ONLY: `$HOME/.claude.json`, `$HOME/.local/bin`, `$HOME/.local/share/claude` —
    what the harness's own `/doctor` inspects (install method, duplicate installs, PATH,
    usage counters). Only a write-free reader (`HOME_READ_VERBS`: `cat`, `ls`, `jq`, …)
    or a read tool reaches them; `sort -o`, `yq -i`, any other verb or a write tool is
    still refused
  - every path listed in `<root>/.local/scope-allow.txt` — one path per line,
    `#` comments, `~` allowed, a directory covers its subtree. The operator's
    exception list: the study's `<repo>/.local/study*/…/answer.md` reads live here.
    It is the ONLY way scope widens; it is gitignored, so a widening never ships.

Outside scope — another repo's checkout, a data root, `/Users/*`, the rest of
`$HOME` — the refusal names `/alemax:send-msg <drive> <repo>` as the way to reach
that repo's session. A `cd`, `pushd` or `git -C` whose target leaves scope is
refused the same way, whatever follows it (the auto-mode classifier judges a
compound command as a whole; a path rule does not see past `cd … &&`).

Environment (`<root>/.local/env`, first word `prod` | `dev`; absent → `prod`
under `Applications/`, else `dev` — the rule `alemax_addr.py` already applies):
while this clone is `dev`, an Edit/Write/MultiEdit/NotebookEdit, a write-shaped
Bash command or a redirect targeting a path under `*/Applications/*`, under the
prod clone (`prod: <path>` in the marker, default `$HOME/Applications/<repo>`),
under a data root the prod clone declares (`data: <path>` lines in ITS marker),
or under a tree the tracked `<root>/data.yaml` declares `env: prod` (spec
`data-repo-convention`) is refused — even when `scope-allow.txt` lists the path.
One exception, the dev→prod notes channel (spec `session-confinement`, design D8):
a dev write to THIS clone's own prod clone's `.local/tracking-*.md` or anything
under its `.local/msg/` is allowed. Nothing else in that `.local/` (`env`,
`scope-allow.txt`, `settings.local.proposed.json`, …), no other repo's prod clone,
and no data root's `.local/`.
`data.yaml` is the declaration every clone of the repo shares; the marker's
`data:` / `prod-data:` lines stay as the additive per-machine override. `both`
and `dev` trees are writable from a dev session. A malformed `data.yaml`, or an
unset `$VAR` in one of its paths, is one `scope-guard: note:` line and no deny
row — never a block: `bin/data-check.py` (pre-commit, on a staged `data.yaml`)
is where the declaration fails loudly. Reads are not the environment rule's
business; the scope rule decides those.

Prose is not a path list: on `git commit|tag|merge|stash|notes`, `gh` and `alemax`, a
multi-word argument to a message flag (`-m`, `--message`, `--body`, `--title`,
`--context`, `--description`, `--detail`) or the free text after `feedback add` /
`presence send` is never opened, so a path quoted in a sentence there is not refused.
The skip ends at the next `;`, `&&`, `|`, `(` or newline, and never covers an argument
carrying a `$(…)` or backtick substitution. On any other command `-m` is that
command's own flag (`touch -m`, `ls -m`, `sort -m`) and the path after it is checked.

What it cannot see: a path inside a script the command runs, an unknown `$VAR`,
a relative path buried in an argument. It is enforced against command text, not
effect. A guard that crashes must not brick a session, nor wave a write through:
unparseable input, and any failure while judging a read, is exit 0 with a
`scope-guard: note:` on stderr (fail open); a failure while judging a write — Edit,
Write, MultiEdit, NotebookEdit, or a Bash call already classed write-shaped — is
exit 2 with `scope-guard: refused (guard error: …)` (fail closed, design D6).

    uv run --quiet --script .claude/hooks/scope-guard.py   # the hook form (stdin = hook JSON)
    uv run --script .claude/hooks/scope-guard.py --self-test   # fixture cases, exit 0/1
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

FILE_TOOLS = ("Read", "Edit", "Write", "MultiEdit", "NotebookEdit", "Glob", "Grep")
WRITE_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")
ENVS = ("prod", "dev")
SYSTEM_PREFIXES = (
    "/tmp",
    "/private/tmp",
    "/var/folders",
    "/private/var/folders",
    "/opt/homebrew",
    "/usr",
    "/bin",
    "/sbin",
    "/etc",
    "/private/etc",
    "/dev",
)
HOME_SUBDIRS = (".claude", ".cache", os.path.join(".local", "share", "uv"))
HOME_READ_ONLY = (
    ".claude.json",
    os.path.join(".local", "bin"),
    os.path.join(".local", "share", "claude"),
)
PROSE_FLAGS = frozenset(
    ["-m", "--message", "--body", "--title", "--context", "--description", "--detail"]
)
PROSE_VERBS = (("feedback", "add"), ("presence", "send"))
GIT_MESSAGE_SUBS = frozenset(["commit", "tag", "merge", "stash", "notes"])
# Shell punctuation that shlex should hand back as a word of its own; a word made of it
# that holds one of SEGMENT_CHARS (or is `&&` / `&`) ends a segment.
SHELL_PUNCT = "();<>|&\n"
SEGMENT_CHARS = ";|()\n"
EXPANDED_VARS = ("CLAUDE_PROJECT_DIR", "HOME", "TMPDIR", "PWD")

# An absolute or ~-prefixed token. The lookbehind keeps URL tails (`https://h/p`),
# ssh remotes (`git@h:o/r`), sed programs (`s/a/b/`) and relative paths (`a/b`,
# `./x`, `../x`) from reading as paths.
# An absolute path must begin with `/` followed by a real name character.
# Without that lookahead a quoted `)/\(` inside a jq filter, an `s/x/y/`
# expression, or a URL's `//` each matched as a path, and the hook refused
# commands that touch no file at all. Found 2026-09-04 when the guard
# blocked a `gh pr view --jq` call and then blocked its own fix.
PATH_TOKEN = re.compile(
    r"(?<![\w@:/.~-])("
    r"~(?:/[^\s'\"`;|&<>()]*)?(?=$|[\s'\"`;|&<>()])"
    r"|/(?=[A-Za-z0-9_.])[^\s'\"`;|&<>()]*"
    r"|/(?=$|[\s'\"`;|&<>()])"
    r")"
)
CD_RE = re.compile(
    r"(?:^|[;&|(]|\bthen\b|\bdo\b)\s*(?:cd|pushd)(?:\s+(?!-)([^\s;&|()]+))?", re.MULTILINE
)
GIT_DIR_RE = re.compile(
    r"(?:\s-C\s+|--git-dir=|--work-tree=|\bGIT_DIR=|\bGIT_WORK_TREE=)([^\s;&|()]+)"
)
REDIRECT_RE = re.compile(r"(?<![<>])>{1,2}\s*([^\s;&|()]+)")
# `/alemax:send-msg` is a slash command, not a directory. The fleet's own
# skills, briefs and commit messages name them constantly, and each one read as
# an absolute path whose first segment does not exist. Found 2026-09-04 writing
# a session checkpoint whose note quoted two command names.
SLASH_COMMAND = re.compile(r"^/[A-Za-z][A-Za-z0-9_-]*:[A-Za-z0-9_-]+$")
SEGMENT_SPLIT = re.compile(r"\|\||&&|\||;|\n")
GLOB_META = re.compile(r"[*?\[{]")

READ_ONLY_VERBS = frozenset(
    [
        "cat",
        "head",
        "tail",
        "less",
        "more",
        "grep",
        "egrep",
        "fgrep",
        "rg",
        "ug",
        "ls",
        "stat",
        "wc",
        "diff",
        "cmp",
        "comm",
        "file",
        "test",
        "[",
        "[[",
        "echo",
        "printf",
        "sort",
        "uniq",
        "cut",
        "tr",
        "awk",
        "jq",
        "yq",
        "md5",
        "md5sum",
        "shasum",
        "sha256sum",
        "du",
        "df",
        "tree",
        "which",
        "type",
        "basename",
        "dirname",
        "realpath",
        "readlink",
        "pwd",
        "true",
        "false",
        "date",
        "env",
        "printenv",
        "column",
        "paste",
        "fold",
        "nl",
        "od",
        "xxd",
        "hexdump",
        "strings",
        "tac",
        "rev",
        "seq",
        "expr",
        "bc",
        "column",
        "openspec",
        "gh",
    ]
)
# The verbs trusted on a HOME_READ_ONLY path. Narrower than READ_ONLY_VERBS, which only
# decides whether a dev session writes into prod: `sort -o`, `uniq in out`, `yq -i`,
# `awk -i inplace`, `tree -o`, `xxd -r`, `rg --pre`, `find -fprint` and
# `gh release download -D` each write, and on `~/.claude.json` or `~/.local/bin` the
# file written is the harness's own config or its launcher.
HOME_READ_VERBS = frozenset(
    [
        "cat",
        "head",
        "tail",
        "grep",
        "egrep",
        "fgrep",
        "ls",
        "stat",
        "wc",
        "diff",
        "cmp",
        "file",
        "test",
        "[",
        "[[",
        "jq",
        "md5",
        "md5sum",
        "shasum",
        "sha256sum",
        "du",
        "which",
        "type",
        "realpath",
        "readlink",
        "basename",
        "dirname",
    ]
)
GIT_READ_ONLY = frozenset(
    [
        "log",
        "status",
        "diff",
        "show",
        "ls-files",
        "ls-tree",
        "rev-parse",
        "remote",
        "worktree",
        "check-ignore",
        "cat-file",
        "describe",
        "blame",
        "shortlog",
        "reflog",
        "tag",
        "config",
        "stash",
        "branch",
        "cherry",
        "rev-list",
        "name-rev",
        "var",
        "version",
        "help",
    ]
)
GIT_READ_ONLY_REFUSE_FLAGS = {
    "branch": (
        "-d",
        "-D",
        "-m",
        "-M",
        "--delete",
        "--move",
        "-c",
        "-C",
        "--copy",
        "-u",
        "--set-upstream-to",
        "--unset-upstream",
    ),
    "remote": ("add", "remove", "rm", "rename", "set-url", "set-head", "prune", "update"),
    "worktree": ("add", "remove", "prune", "move", "lock", "unlock", "repair"),
    "tag": ("-d", "--delete", "-a", "-s", "-f", "-m"),
    "config": (
        "--unset",
        "--add",
        "--replace-all",
        "--remove-section",
        "--rename-section",
        "--edit",
        "-e",
    ),
    "stash": ("push", "pop", "apply", "drop", "clear", "save", "branch"),
    "reflog": ("expire", "delete"),
}
COMMAND_PREFIX_WORDS = frozenset(
    ("sudo", "env", "time", "nice", "command", "exec", "nohup", "caffeinate")
)

EXIT_ALLOW = 0
EXIT_BLOCK = 2

PROD_CLONE_WHY = "under a prod clone or the data it declares"


# --- paths ---------------------------------------------------------------------


def expand_home(token: str, home: str) -> str:
    if token == "~":
        return home
    if token.startswith("~/"):
        return home + token[1:]
    return token


def norm(token: str, base: str, home: str) -> str:
    token = expand_home(token, home)
    if not os.path.isabs(token):
        token = os.path.join(base, token)
    return os.path.normpath(token)


def under(path: str, prefix: str) -> bool:
    prefix = prefix.rstrip("/") or "/"
    return path == prefix or path.startswith(prefix + "/")


def real(path: str) -> str:
    try:
        return os.path.realpath(path)
    except OSError:
        return path


def read_lines(path: str) -> list[str]:
    try:
        with open(path, encoding="utf-8") as fh:
            return [ln.strip() for ln in fh if ln.strip() and not ln.lstrip().startswith("#")]
    except OSError:
        return []


# --- roots, scope, environment ----------------------------------------------------


def git_toplevel(cwd: str) -> str | None:
    try:
        done = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except OSError, subprocess.SubprocessError:
        return None
    top = done.stdout.strip()
    return top or None


def main_checkout(root: str) -> str | None:
    """For a linked worktree, the main checkout it is linked from (read from the
    `.git` file, no subprocess). None for a main checkout or a non-repo."""
    dotgit = os.path.join(root, ".git")
    if not os.path.isfile(dotgit):
        return None
    for line in read_lines(dotgit):
        if line.startswith("gitdir:"):
            gitdir = os.path.normpath(os.path.join(root, line[len("gitdir:") :].strip()))
            # <main>/.git/worktrees/<name>
            marker = os.sep + ".git" + os.sep + "worktrees" + os.sep
            idx = gitdir.find(marker)
            if idx != -1:
                return gitdir[:idx]
    return None


def project_roots(env: dict, cwd: str) -> list[str]:
    roots: list[str] = []
    pd = env.get("CLAUDE_PROJECT_DIR")
    if pd:
        roots.append(os.path.normpath(pd))
    if not any(under(os.path.normpath(cwd), r) for r in roots):
        top = git_toplevel(cwd)
        if top:
            roots.append(os.path.normpath(top))
    for r in list(roots):
        main = main_checkout(r)
        if main:
            roots.append(main)
    if not roots:
        roots.append(os.path.normpath(cwd))
    seen: dict[str, None] = {}
    for r in roots:
        seen.setdefault(r, None)
    return list(seen)


class Scope:
    def __init__(self, env: dict, cwd: str) -> None:
        self.home = env.get("HOME") or os.path.expanduser("~")
        self.cwd = os.path.normpath(cwd)
        self.roots = project_roots(env, self.cwd)
        self.root = (
            self.roots[-1]
            if len(self.roots) > 1 and main_checkout(self.roots[0])
            else self.roots[0]
        )
        self.allow: list[str] = []
        for r in self.roots:
            self.allow.append(r)
            self.allow.append(
                os.path.join(os.path.dirname(r), os.path.basename(r) + "-claude-meta")
            )
        tmpdir = env.get("TMPDIR")
        if tmpdir:
            self.allow.append(os.path.normpath(tmpdir))
        self.allow.extend(SYSTEM_PREFIXES)
        for sub in HOME_SUBDIRS:
            self.allow.append(os.path.join(self.home, sub))
        self.read_only = [os.path.join(self.home, sub) for sub in HOME_READ_ONLY]
        self.allow_files: list[str] = []
        for r in self.roots:
            f = os.path.join(r, ".local", "scope-allow.txt")
            lines = read_lines(f)
            if lines:
                self.allow_files.append(f)
            for line in lines:
                line = re.sub(r"/\*{1,2}$", "", line)
                self.allow.append(norm(line, r, self.home))
        self.allow_real = [real(p) for p in self.allow]
        # environment
        self.env_label, self.env_source, marker = env_of(self.root, self.home)
        self.env_marker = os.path.join(self.root, ".local", "env")
        self.prod_deny: list[str] = []
        self.data_deny: list[tuple[str, str]] = []
        self.own_prod: list[str] = []
        self.notes: list[str] = []
        if self.env_label == "dev":
            prod_clones = marker.get("prod") or []
            default = os.path.join(self.home, "Applications", os.path.basename(self.root))
            if not prod_clones and os.path.isdir(default):
                prod_clones = [default]
            self.own_prod = [norm(pc, self.root, self.home) for pc in prod_clones]
            for pc in prod_clones:
                self.prod_deny.append(pc)
                _, _, pinfo = env_of(pc, self.home)
                self.prod_deny.extend(pinfo.get("data") or [])
            self.prod_deny.extend(marker.get("prod-data") or [])
            self.prod_deny = [norm(p, self.root, self.home) for p in self.prod_deny]
            # the tracked declaration, read from every root in scope — a worktree
            # carries its own copy, the main checkout the one the operator edits
            for r in self.roots:
                deny, notes = prod_data_trees(r, self.home, env)
                for path, name in deny:
                    if all(path != seen for seen, _ in self.data_deny):
                        self.data_deny.append((path, name))
                self.notes.extend(n for n in notes if n not in self.notes)

    def allowed(self, path: str) -> bool:
        parts = Path(path).parts
        if len(parts) >= 4 and parts[1] == "Volumes" and parts[3] == "opt":
            return True
        rp = real(path)
        for p, pr in zip(self.allow, self.allow_real, strict=False):
            if under(path, p) or under(rp, pr) or under(path, pr) or under(rp, p):
                return True
        return False

    def read_only_allowed(self, path: str) -> bool:
        return any(under(path, p) for p in self.read_only)

    def prod_channel(self, path: str) -> bool:
        """True for this dev clone's own prod clone's notes channel: `.local/tracking-*.md`
        and anything under `.local/msg/` (spec session-confinement, design D8). Nothing else
        in the prod clone's `.local/` — `env`, `scope-allow.txt` and the proposed settings
        decide how prod is guarded — and never another repo's prod clone."""
        for pc in self.own_prod:
            for p, base in ((path, pc), (real(path), real(pc))):
                local = os.path.join(base, ".local")
                if under(p, os.path.join(local, "msg")):
                    return True
                if os.path.dirname(p) == local and re.fullmatch(
                    r"tracking-[^/]*\.md", os.path.basename(p)
                ):
                    return True
        return False

    def prod_protected(self, path: str) -> str | None:
        """None when the path is not prod-protected; otherwise the phrase that says what
        protects it, for the refusal line."""
        rp = real(path)
        if self.prod_channel(path) and not any(
            under(path, p) or under(rp, real(p)) for p, _ in self.data_deny
        ):
            return None
        if "Applications" in Path(path).parts:
            return PROD_CLONE_WHY
        if any(under(path, p) or under(rp, real(p)) for p in self.prod_deny):
            return PROD_CLONE_WHY
        for p, name in self.data_deny:
            if under(path, p) or under(rp, real(p)):
                return f"the prod data tree `{name}` — `data.yaml` declares it `env: prod`"
        return None


def env_of(root: str, home: str) -> tuple[str, str, dict]:
    """(label, 'declared'|'inferred', extra lines as {key: [values]}) for a clone root —
    the same first-word rule as `alemax_addr.py env_of`; the extra `key: value` lines
    are this guard's only addition and are ignored by every other reader."""
    lines = read_lines(os.path.join(root, ".local", "env"))
    extra: dict[str, list[str]] = {}
    label, how = None, "inferred"
    for i, line in enumerate(lines):
        if i == 0 and line.split()[0] in ENVS:
            label, how = line.split()[0], "declared"
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            value = expand_home(value.strip(), home)
            if value:
                extra.setdefault(key.strip(), []).append(os.path.normpath(value))
    if label is None:
        label = "prod" if os.path.basename(os.path.dirname(root)) == "Applications" else "dev"
    return label, how, extra


# --- data.yaml: the tracked declaration of data trees ------------------------------

VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)")
ITEM_INDENT = 2  # `  - name: …`
KEY_INDENT = 4  # `    kind: …`

# copied from bin/data-check.py — keep in sync. A PreToolUse hook must be
# self-contained (no import across files) and must not shell out: it fires on every
# tool call, and `uv run --script bin/data-check.py --json` would add 40-60 ms to
# each one. `ParseError`, `ITEM_INDENT`, `KEY_INDENT`, `_strip_comment`, `_scalar`
# and `parse_data_yaml` below are verbatim; diff them against `bin/data-check.py`
# whenever the accepted subset changes. Expansion is NOT copied — the guard resolves
# `$VAR` against the hook's environment dict, not `os.environ` (see expand_data_path).


class ParseError(Exception):
    pass


def _strip_comment(line: str) -> str:
    """Drop a trailing ` # …` that is not inside quotes."""
    quote = None
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = None
        elif ch in ("'", '"'):
            quote = ch
        elif ch == "#" and (i == 0 or line[i - 1] in " \t"):
            return line[:i]
    return line


def _scalar(raw: str) -> str | None:
    value = raw.strip()
    if value in ("", "~", "null"):
        return None
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def parse_data_yaml(text: str) -> list[dict[str, str | None]]:
    """Return the `data:` list. Accepts only the documented subset."""
    entries: list[dict[str, str | None]] = []
    in_data = False
    current: dict[str, str | None] | None = None
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = _strip_comment(raw).rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        body = line.strip()
        if indent == 0:
            in_data = False
            current = None
            key, sep, rest = body.partition(":")
            if not sep:
                raise ParseError(f"line {lineno}: expected `key:`, got {body!r}")
            if key.strip() == "data":
                in_data = True
                rest = rest.strip()
                if rest in ("", "[]"):
                    continue
                raise ParseError(
                    f"line {lineno}: `data:` must be `[]` or a list of `- name: …` items"
                )
            # another top-level scalar (`version: 1`) is tolerated and ignored
            continue
        if not in_data:
            raise ParseError(f"line {lineno}: nested content outside `data:`")
        if body.startswith("- "):
            if indent != ITEM_INDENT:
                raise ParseError(
                    f"line {lineno}: list items must be indented {ITEM_INDENT} spaces under `data:`"
                )
            current = {}
            entries.append(current)
            body = body[2:].strip()
            if not body:
                continue
        elif current is None:
            raise ParseError(f"line {lineno}: expected `- ` list item under `data:`")
        elif indent != KEY_INDENT:
            raise ParseError(
                f"line {lineno}: nested collections are not supported "
                f"(entry keys are flat, indented {KEY_INDENT} spaces)"
            )
        key, sep, rest = body.partition(":")
        if not sep or not key.strip() or key.strip().startswith("-"):
            raise ParseError(f"line {lineno}: expected `key: value`, got {body!r}")
        if rest.strip() in ("[", "{") or rest.strip().startswith(("[", "{")):
            raise ParseError(f"line {lineno}: nested collections are not supported")
        current[key.strip()] = _scalar(rest)
    return entries


# --- end of the copy ---


def expand_data_path(path: str, home: str, env: dict) -> tuple[str, list[str]]:
    """(`~`- and `$VAR`-expanded path, the names that were unset). Unset is never
    guessed — the caller drops the tree and notes it (`data-repo-convention`)."""
    unset: list[str] = []

    def repl(match: re.Match) -> str:
        name = match.group(1) or match.group(2)
        value = env.get(name)
        if value is None:
            unset.append(name)
            return match.group(0)
        return value

    return expand_home(VAR_RE.sub(repl, path), home), unset


def prod_data_trees(root: str, home: str, env: dict) -> tuple[list[tuple[str, str]], list[str]]:
    """([(path, name)] for every `env: prod` entry of `<root>/data.yaml`, notes).

    `env: both` and `env: dev` trees are writable from a dev session. No file, a
    malformed file, a missing path or an unset variable yields no deny row and at
    most one note — fail open; `bin/data-check.py` is the loud check."""
    file = os.path.join(root, "data.yaml")
    try:
        with open(file, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return [], []
    try:
        entries = parse_data_yaml(text)
    except (ParseError, UnicodeDecodeError, ValueError) as exc:
        return [], [
            f"scope-guard: note: {file}: {exc} — data trees not consulted "
            f"(`uv run --script bin/data-check.py` is the loud check)"
        ]
    deny: list[tuple[str, str]] = []
    notes: list[str] = []
    for index, entry in enumerate(entries, 1):
        if entry.get("env") != "prod":
            continue
        name = entry.get("name") or f"<entry {index}>"
        raw = entry.get("path")
        if not raw:
            notes.append(
                f"scope-guard: note: {file}: prod entry `{name}` has no path — not guarded"
            )
            continue
        expanded, unset = expand_data_path(raw, home, env)
        if unset:
            notes.append(
                f"scope-guard: note: {file}: prod entry `{name}` uses unset "
                f"{', '.join(sorted(set(unset)))} — unset means stop and ask, so the tree is "
                f"reported unresolvable, never guessed, and is not guarded"
            )
            continue
        deny.append((norm(expanded, root, home), name))
    return deny, notes


# --- candidate extraction ----------------------------------------------------------


def expand_vars(text: str, env: dict) -> str:
    for var in EXPANDED_VARS:
        value = env.get(var)
        if value:
            text = re.sub(rf"\$\{{{var}\}}|\${var}\b", lambda _m, v=value: v, text)
    return text


def glob_prefix(pattern: str) -> str:
    m = GLOB_META.search(pattern)
    head = pattern if not m else pattern[: m.start()]
    return head if head.endswith("/") else os.path.dirname(head) or head


def file_tool_candidates(tool: str, tool_input: dict, scope: Scope) -> list[tuple[str, str]]:
    cands: list[tuple[str, str]] = []
    for key in ("file_path", "notebook_path", "path"):
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            cands.append(
                (norm(value, scope.cwd, scope.home), "write" if tool in WRITE_TOOLS else "read")
            )
    if tool == "Glob":
        pattern = tool_input.get("pattern")
        if isinstance(pattern, str) and (pattern.startswith("/") or pattern.startswith("~")):
            cands.append((norm(glob_prefix(pattern), scope.cwd, scope.home), "read"))
    return cands


def segments(command: str) -> list[str]:
    return [s.strip() for s in SEGMENT_SPLIT.split(command) if s.strip()]


def verb_of(segment: str) -> list[str]:
    try:
        words = shlex.split(segment, posix=True)
    except ValueError:
        words = segment.split()
    return command_words(words)


def command_words(words: list[str]) -> list[str]:
    """`words` without the leading `VAR=value` assignments and prefix words (`env`, `sudo`, …)."""
    while words and (
        re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", words[0]) or words[0] in COMMAND_PREFIX_WORDS
    ):
        words = words[1:]
    return words


def shell_words(text: str) -> list[str]:
    """shlex words of a command line, with each run of shell punctuation outside quotes
    (`&&`, `;`, `|`, `(`, a newline, `>`) as a word of its own, so a segment boundary
    shows even when written without spaces (`a&&b`)."""
    lex = shlex.shlex(text, posix=True, punctuation_chars=SHELL_PUNCT)
    lex.whitespace = " \t\r"
    lex.whitespace_split = True
    lex.commenters = ""
    try:
        return list(lex)
    except ValueError:
        return text.split()


def ends_segment(word: str) -> bool:
    if not word or any(c not in SHELL_PUNCT for c in word):
        return False
    return any(c in SEGMENT_CHARS for c in word) or "&&" in word or word == "&"


def split_segments(words: list[str]) -> list[list[str]]:
    out: list[list[str]] = [[]]
    for w in words:
        if ends_segment(w):
            out.append([])
        else:
            out[-1].append(w)
    return [seg for seg in out if seg]


def git_subcommand(cmd: list[str]) -> str:
    """The subcommand of a `git …` word list, past `-C <dir>` / `-c <k=v>` and other flags."""
    rest = iter(cmd[1:])
    for w in rest:
        if w in ("-C", "-c"):
            next(rest, None)
        elif not w.startswith("-"):
            return w
    return ""


def prose_indices(seg: list[str]) -> set[int]:
    """Indices of the words in ONE segment that are prose — a sentence handed to a
    message flag, or the free text after `feedback add` / `presence send` — and so are
    never opened. Only on the commands whose flags carry a message: `-m` is a message on
    `git commit` but its own flag on `touch`, `ls`, `sort`, `rsync` and `zip`. Only a
    multi-word argument qualifies, and never one carrying a command substitution."""
    cmd = command_words(seg)
    off = len(seg) - len(cmd)
    names = [os.path.basename(w) for w in cmd]
    alemax = "alemax" in names
    git_sub = git_subcommand(cmd) if names[:1] == ["git"] else ""
    if not (alemax or names[:1] == ["gh"] or git_sub in GIT_MESSAGE_SUBS):
        return set()
    prose_after = len(cmd)
    if alemax:
        for i in range(len(cmd) - 1):
            if (cmd[i], cmd[i + 1]) in PROSE_VERBS:
                prose_after = min(prose_after, i + 2)
    out: set[int] = set()
    for i, w in enumerate(cmd):
        if not any(c.isspace() for c in w) or "$(" in w or "`" in w:
            continue
        if i >= prose_after or (i > 0 and cmd[i - 1] in PROSE_FLAGS):
            out.add(i + off)
    return out


def home_readable(text: str) -> bool:
    """Is every segment of the command a HOME_READ_VERBS reader — the only shape allowed
    on a HOME_READ_ONLY path?"""
    for seg in segments(text):
        words = verb_of(seg)
        if words and os.path.basename(words[0]) not in HOME_READ_VERBS:
            return False
    return True


def segment_is_read_only(words: list[str]) -> bool:
    if not words:
        return True
    verb = os.path.basename(words[0])
    if verb == "sed":
        return not any(w == "-i" or w.startswith("-i") or w == "--in-place" for w in words[1:])
    if verb == "find":
        return not any(w in ("-delete", "-exec", "-execdir", "-ok", "-okdir") for w in words[1:])
    if verb == "git":
        args = [w for w in words[1:] if not w.startswith("-")]
        sub = args[0] if args else ""
        if sub not in GIT_READ_ONLY:
            return False
        flags = GIT_READ_ONLY_REFUSE_FLAGS.get(sub, ())
        return not any(w in flags for w in words[2:])
    return verb in READ_ONLY_VERBS


HEREDOC_RE = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")


def strip_heredocs(command: str) -> str:
    """Drop heredoc BODIES, keep the command lines that introduce them.

    A heredoc body is data or code, not a path list: `python3 - <<PY` carrying
    `ROOT + "/scaffolding/..."`, or a commit message quoting a path, made the
    scanner refuse calls that open no file. The redirect and `cd` targets that
    do matter sit on the command line itself, which is preserved, so nothing
    write-shaped is lost. Found 2026-09-04, when the guard refused the command
    that was writing its own fix.
    """
    lines = command.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        delims = [m.group(2) for m in HEREDOC_RE.finditer(line)]
        i += 1
        for delim in delims:
            while i < len(lines) and lines[i].strip() != delim:
                i += 1
            if i < len(lines):
                i += 1  # consume the terminator
    return "\n".join(out)


def looks_like_real_path(token: str) -> bool:
    """Is this token a path anyone on this machine could be touching?

    An absolute path's first segment is a directory that exists at `/`. Nothing
    else can be opened, and treating every slash as a path is what produced four
    false-positive classes in one hour of ordinary use: a jq filter's `)/(`, an
    `s/foo/bar/` substitution, a URL's `//`, path-like strings inside heredoc
    bodies, and `/alemax:<n>` in a sentence. Each was patched in turn (#274,
    #276) and another shape always followed, so the test is now what the
    filesystem says rather than what the string looks like.

    Deliberately not a security boundary: a write under a root that does not
    exist yet cannot succeed anyway, its parent being absent.
    """
    if not token.startswith("/"):
        return True  # relative tokens are resolved against cwd by the caller
    first = token.lstrip("/").split("/", 1)[0]
    if not first:
        return False  # bare "/" and "//host/..." are handled by the caller
    try:
        return os.path.isdir(os.path.join("/", first))
    except OSError:
        return False


def bash_candidates(
    command: str, scope: Scope, env: dict
) -> tuple[list[tuple[str, str]], bool, bool]:
    """(candidates, write_shaped, home_readable). Kinds: 'cd', 'path', 'redirect'."""
    text = expand_vars(strip_heredocs(command), env)
    cands: list[tuple[str, str]] = []
    for m in CD_RE.finditer(text):
        target = m.group(1)
        target = scope.home if target is None else target.strip("'\"")
        if target == "-":
            continue
        cands.append((norm(target, scope.cwd, scope.home), "cd"))
    for m in GIT_DIR_RE.finditer(text):
        cands.append((norm(m.group(1).strip("'\""), scope.cwd, scope.home), "path"))
    for m in REDIRECT_RE.finditer(text):
        target = m.group(1).strip("'\"")
        if target.startswith("&"):
            continue
        cands.append((norm(target, scope.cwd, scope.home), "redirect"))
    tokens: list[str] = []
    for seg in split_segments(shell_words(text)):
        prose = prose_indices(seg)  # a sentence handed to a message flag is never opened
        tokens.extend(w for i, w in enumerate(seg) if i not in prose)
    for tok in tokens:
        for m in PATH_TOKEN.finditer(tok):
            token = m.group(1)
            if token in ("/", "~") and tok != token:
                continue
            if SLASH_COMMAND.match(token):
                continue
            if not looks_like_real_path(token):
                continue
            path = norm(token, scope.cwd, scope.home)
            if path == "/":
                continue
            cands.append((path, "path"))
    write_shaped = any(not segment_is_read_only(verb_of(seg)) for seg in segments(text)) or any(
        k == "redirect" for _, k in cands
    )
    return cands, write_shaped, home_readable(text)


# --- decisions ---------------------------------------------------------------------


def address_hint(path: str) -> str:
    parts = Path(path).parts
    drive = parts[2].lower() if len(parts) > 3 and parts[1] == "Volumes" else "<drive>"
    repo = "<repo>"
    for i, part in enumerate(parts):
        if part == "claude-code" and i + 2 < len(parts):
            repo = parts[i + 2]
            break
        if part == "Applications" and i + 1 < len(parts):
            repo = parts[i + 1]
            break
        if part == "github.com" and i + 2 < len(parts):
            repo = parts[i + 2]
            break
    return f"/alemax:send-msg {drive} {repo}"


# Set once decide() has classed the call, so a guard error after that point can fail
# closed for a write (design D6): `run_hook` reads it in its error path.
JUDGING = {"write": False}


def decide(tool: str, tool_input: dict, scope: Scope, env: dict) -> tuple[int, str]:
    if tool == "Bash":
        command = tool_input.get("command")
        if not isinstance(command, str) or not command.strip():
            return EXIT_ALLOW, ""
        cands, write_shaped, reader = bash_candidates(command, scope, env)
    elif tool in FILE_TOOLS:
        cands, write_shaped = file_tool_candidates(tool, tool_input, scope), tool in WRITE_TOOLS
        reader = not write_shaped
    else:
        return EXIT_ALLOW, ""
    JUDGING["write"] = write_shaped or any(kind in ("redirect", "write") for _, kind in cands)
    hint = ""
    for path, kind in cands:
        writes = kind in ("redirect", "write") or (kind == "path" and write_shaped)
        why = scope.prod_protected(path) if scope.env_label == "dev" and writes else None
        if why:
            return EXIT_BLOCK, (
                f"scope-guard: refused {tool} write to {path} — this clone is dev "
                f"({scope.env_source}: {scope.env_marker}) and a dev session never writes {why}"
                f"; ask the prod session — `{address_hint(path)}@prod` "
                f"(questions and proposals only)."
            )
        if scope.allowed(path) or (not writes and reader and scope.read_only_allowed(path)):
            continue
        what = f"`cd {path}`" if kind == "cd" else f"{tool} of {path}"
        allow_file = os.path.join(scope.root, ".local", "scope-allow.txt")
        hint = (
            f"scope-guard: refused {what} — outside this session's scope (root {scope.root}); "
            f"that repo has its own session: `{address_hint(path)} …` reaches it, never a direct read or write from here"
            f"{' — a compound command is judged as a whole, so run the rest with absolute paths from this root' if kind == 'cd' else ''}"
            f"; an operator-sanctioned exception is one line in {allow_file}."
        )
        return EXIT_BLOCK, hint
    return EXIT_ALLOW, ""


def evaluate(payload: dict, env: dict, default_cwd: str) -> tuple[int, str]:
    tool = payload.get("tool_name")
    tool_input = payload.get("tool_input")
    if isinstance(tool, str) and tool in WRITE_TOOLS and not isinstance(tool_input, dict):
        return EXIT_BLOCK, (
            f"scope-guard: refused {tool} (guard error: tool_input is not an object) — "
            "a write the guard cannot judge does not run"
        )
    if not isinstance(tool, str) or not isinstance(tool_input, dict):
        return EXIT_ALLOW, "scope-guard: note: no tool_name/tool_input in hook input — allowing"
    cwd = (
        payload.get("cwd")
        if isinstance(payload.get("cwd"), str) and payload.get("cwd")
        else default_cwd
    )
    scope = Scope(env, cwd)
    code, message = decide(tool, tool_input, scope, env)
    if scope.notes:
        message = "\n".join(([message] if message else []) + scope.notes)
    return code, message


def run_hook() -> int:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
        if not isinstance(payload, dict):
            raise ValueError("hook input is not a JSON object")
    except (ValueError, OSError) as exc:
        print(f"scope-guard: note: could not parse hook input ({exc}) — allowing", file=sys.stderr)
        return EXIT_ALLOW
    # The tool is known before anything that can fail, so an error while judging a write
    # refuses it (design D6). A read, and input the guard cannot parse, still fail open:
    # a guard defect must never stop a session from reading.
    tool = payload.get("tool_name")
    JUDGING["write"] = False
    try:
        code, message = evaluate(payload, dict(os.environ), os.getcwd())
    except Exception as exc:
        if tool in WRITE_TOOLS or (tool == "Bash" and JUDGING["write"]):
            print(
                f"scope-guard: refused (guard error: {type(exc).__name__}: {exc})", file=sys.stderr
            )
            return EXIT_BLOCK
        print(
            f"scope-guard: note: guard failed ({type(exc).__name__}: {exc}) — allowing",
            file=sys.stderr,
        )
        return EXIT_ALLOW
    if message:
        print(message, file=sys.stderr)
    return code


# --- self-test --------------------------------------------------------------------


def self_test() -> int:
    with tempfile.TemporaryDirectory(prefix="scope-guard-") as tmp:
        tmp = os.path.realpath(tmp)
        users = os.path.join(tmp, "Volumes", "T", "Users", "x")
        root = os.path.join(users, "claude-code", "o", "myrepo")
        other = os.path.join(users, "claude-code", "o", "other-repo")
        prod = os.path.join(users, "Applications", "myrepo")
        prod_data = os.path.join(users, "Documents", "myrepo")
        documents = os.path.join(users, "Documents")
        data_prod = os.path.join(documents, "myrepo-corpus")
        data_both = os.path.join(documents, "myrepo-vault")
        data_dev = os.path.join(documents, "myrepo-sandbox")
        data_var = os.path.join(documents, "myrepo-var")
        home = users  # $HOME is the operator's Users dir, so $HOME/Applications/<repo> is the prod clone
        tmpdir = os.path.join(tmp, "tmpdir")
        for d in (root, other, prod, prod_data, home, tmpdir):
            os.makedirs(os.path.join(d, ".local") if d in (root, prod) else d, exist_ok=True)
        os.makedirs(os.path.join(root, ".git"))
        wt = os.path.join(root, ".claude", "worktrees", "agent-1")
        os.makedirs(wt)
        with open(os.path.join(wt, ".git"), "w", encoding="utf-8") as fh:
            fh.write(f"gitdir: {root}/.git/worktrees/agent-1\n")
        with open(os.path.join(prod, ".local", "env"), "w", encoding="utf-8") as fh:
            fh.write(f"prod\ndata: {prod_data}\n")
        sibling = os.path.join(users, "claude-code", "o", "myrepo-claude-meta")
        far = "/Volumes/APP01/Users/x/claude-code/o/other-repo/CLAUDE.md"  # path-literal-ok: self-test fixture

        def env(**over: str) -> dict:
            base = {"CLAUDE_PROJECT_DIR": root, "HOME": home, "TMPDIR": tmpdir}
            base.update(over)
            return base

        def set_marker(text: str | None) -> None:
            p = os.path.join(root, ".local", "env")
            if text is None:
                if os.path.exists(p):
                    os.remove(p)
            else:
                with open(p, "w", encoding="utf-8") as fh:
                    fh.write(text)

        def set_allow(lines: list[str]) -> None:
            p = os.path.join(root, ".local", "scope-allow.txt")
            if not lines:
                if os.path.exists(p):
                    os.remove(p)
                return
            with open(p, "w", encoding="utf-8") as fh:
                fh.write("# operator exceptions\n" + "\n".join(lines) + "\n")

        def set_data(text: str | None) -> None:
            p = os.path.join(root, "data.yaml")
            if text is None:
                if os.path.exists(p):
                    os.remove(p)
                return
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(text)

        def call(
            tool: str, cwd: str = root, e: dict | None = None, **tool_input: str
        ) -> tuple[int, str]:
            return evaluate(
                {"tool_name": tool, "tool_input": tool_input, "cwd": cwd}, e or env(), cwd
            )

        failures: list[str] = []
        n = 0

        def check(name: str, got: tuple[int, str], want: int, contains: str = "") -> None:
            nonlocal n
            n += 1
            code, msg = got
            ok = code == want and (contains in msg)
            print(
                f"  {'PASS' if ok else 'FAIL'}  {name}  (exit {code}{' — ' + msg if msg and not ok else ''})"
            )
            if not ok:
                failures.append(
                    f"{name}: wanted exit {want} containing {contains!r}, got {code} {msg!r}"
                )

        # --- scope rule ---
        set_marker(None)
        set_allow([])
        check(
            "Read inside root → allow", call("Read", file_path=os.path.join(root, "CLAUDE.md")), 0
        )
        check(
            "Read of a sibling (other drive) → block, names send-msg",
            call("Read", file_path=far),
            2,
            "/alemax:send-msg app01 other-repo",
        )
        set_allow([far])
        check("same path in scope-allow → allow", call("Read", file_path=far), 0)
        set_allow([os.path.dirname(far)])
        check("scope-allow directory covers the file → allow", call("Read", file_path=far), 0)
        set_allow([])
        check(
            "Read of sibling on the same drive → block",
            call("Read", file_path=os.path.join(other, "CLAUDE.md")),
            2,
            "other-repo …` reaches it",
        )
        check(
            "Bash `cd /Users/x/foo && ls` → block",
            call("Bash", command="cd /Users/x/foo && ls"),
            2,
            "cd /Users/x/foo",
        )  # path-literal-ok: self-test fixture
        check("Bash `ls /tmp` → allow", call("Bash", command="ls /tmp"), 0)
        check(
            "Bash with 2>/dev/null and a URL → allow",
            call(
                "Bash", command="curl -s https://code.claude.com/docs/en/hooks 2>/dev/null | head"
            ),
            0,
        )
        check(
            "Bash `git -C <sibling> status` → block",
            call("Bash", command=f"git -C {other} status"),
            2,
            "other-repo",
        )
        check("Bash `cd ..` leaves the root → block", call("Bash", command="cd .. && ls"), 2, "cd ")
        check("Bash `cd sub` inside → allow", call("Bash", command="cd openspec && ls"), 0)
        check(
            "Bash `~/.claude/...` → allow", call("Bash", command="cat ~/.claude/settings.json"), 0
        )
        check(
            "Bash `~/.zshrc` (rest of HOME) → block",
            call("Bash", command="cat ~/.zshrc"),
            2,
            "send-msg",
        )
        check(
            "Bash $TMPDIR write → allow", call("Bash", command="printf x > $TMPDIR/scratch.txt"), 0
        )
        check(
            "Bash `sed s/a/b/` is not a path → allow",
            call("Bash", command="sed -n 's/foo/bar/p' README.md"),
            0,
        )
        check(
            "Bash ssh remote is not a path → allow",
            call("Bash", command="git remote add up git@github.com:o/r.git"),
            0,
        )
        check(
            "Write under .claude/worktrees → allow",
            call("Write", file_path=os.path.join(wt, "x.md")),
            0,
        )
        check(
            "Write from inside the worktree to the main checkout → allow (cwd = worktree)",
            call(
                "Write",
                cwd=wt,
                e=env(CLAUDE_PROJECT_DIR=root),
                file_path=os.path.join(root, "x.md"),
            ),
            0,
        )
        check(
            "Edit in <root>-claude-meta delivery worktree → allow",
            call("Edit", file_path=os.path.join(sibling, "HANDOFF.md")),
            0,
        )
        check(
            "Glob with an absolute sibling pattern → block",
            call("Glob", pattern=f"{other}/**/*.md"),
            2,
            "other-repo",
        )
        check(
            "Grep with path outside → block",
            call("Grep", pattern="x", path=os.path.join(users, "Documents")),
            2,
        )
        check(
            "Read /Volumes/<drive>/opt (toolchain) → allow",
            call("Read", file_path="/Volumes/T/opt/homebrew/bin/x"),
            0,
        )  # path-literal-ok: self-test fixture
        check("Agent tool → allow (not the guard's business)", call("Agent", prompt="x"), 0)
        # --- environment rule ---
        set_allow([prod, prod_data])
        check(
            "Edit under Applications/ with env=dev (inferred) → block even when scope-allow lists it",
            call("Edit", file_path=os.path.join(prod, "CLAUDE.md")),
            2,
            "myrepo@prod",
        )
        check(
            "Read under Applications/ with env=dev and scope-allow → allow (reads are the scope rule's)",
            call("Read", file_path=os.path.join(prod, "CLAUDE.md")),
            0,
        )
        check(
            "Bash write-shaped under prod data root (declared by prod's marker) with env=dev → block",
            call("Bash", command=f"cp x.db {prod_data}/db.sqlite"),
            2,
            "dev",
        )
        check(
            "Bash read-only under prod data root with env=dev + scope-allow → allow",
            call("Bash", command=f"ls -la {prod_data}"),
            0,
        )
        check(
            "Bash redirect into prod clone with env=dev → block",
            call("Bash", command=f"echo x >> {prod}/notes.md"),
            2,
            "dev",
        )
        # --- the dev→prod notes channel (design D8): only tracking-*.md and msg/** ---
        prod_local = os.path.join(prod, ".local")
        check(
            "dev Write to its prod clone's .local/tracking-12.md → allow (the channel)",
            call("Write", file_path=os.path.join(prod_local, "tracking-12.md"), content="x"),
            0,
        )
        check(
            "dev Write under its prod clone's .local/msg/ → allow (the channel)",
            call(
                "Write",
                file_path=os.path.join(prod_local, "msg", "2026-11-04-brief.md"),
                content="x",
            ),
            0,
        )
        check(
            "dev Bash redirect into its prod clone's tracking file → allow",
            call("Bash", command=f"echo x >> {prod_local}/tracking-12.md"),
            0,
        )
        check(
            "dev Write to its prod clone's .local/env → block (prod's marker)",
            call("Write", file_path=os.path.join(prod_local, "env"), content="dev\n"),
            2,
            "dev",
        )
        check(
            "dev Write to its prod clone's .local/scope-allow.txt → block (prod's widening)",
            call("Write", file_path=os.path.join(prod_local, "scope-allow.txt"), content="/\n"),
            2,
            "dev",
        )
        check(
            "dev Edit of its prod clone's .local/settings.local.proposed.json → block",
            call("Edit", file_path=os.path.join(prod_local, "settings.local.proposed.json")),
            2,
            "dev",
        )
        check(
            "dev Write to its prod clone's .local/resume.md → block (not the channel)",
            call("Write", file_path=os.path.join(prod_local, "resume.md"), content="x"),
            2,
            "dev",
        )
        other_prod = os.path.join(users, "Applications", "other-repo", ".local")
        set_allow([prod, prod_data, other_prod])
        check(
            "dev Write to ANOTHER repo's prod .local/tracking-1.md → block, even with scope-allow",
            call("Write", file_path=os.path.join(other_prod, "tracking-1.md"), content="x"),
            2,
            "dev",
        )
        set_allow([prod, prod_data])
        set_marker("prod\n")
        check(
            "Edit under Applications/ with env=prod (declared) → allow",
            call("Edit", file_path=os.path.join(prod, "CLAUDE.md")),
            0,
        )
        set_marker("dev\n")
        check(
            "Edit under Applications/ with env=dev (declared) → block",
            call("Edit", file_path=os.path.join(prod, "CLAUDE.md")),
            2,
            "declared",
        )
        set_marker(None)
        set_allow([])
        prod_env = env(CLAUDE_PROJECT_DIR=prod)
        check(
            "prod clone editing its own file → allow",
            call("Edit", cwd=prod, e=prod_env, file_path=os.path.join(prod, "CLAUDE.md")),
            0,
        )
        check(
            "prod clone editing the dev clone → block (scope)",
            call("Edit", cwd=prod, e=prod_env, file_path=os.path.join(root, "CLAUDE.md")),
            2,
            "myrepo …` reaches it",
        )
        # --- data.yaml: the tracked declaration of data trees ---
        set_marker(None)
        set_allow([documents])
        set_data(
            "# the project's data trees\n"
            "data:\n"
            f"  - name: corpus\n    kind: gitea\n    path: {data_prod}\n"
            "    remote: git@gitea.lan:o/data-myrepo.git\n    env: prod\n"
            f"  - name: vault\n    kind: local\n    path: {data_both}\n    env: both\n"
            f"  - name: sandbox\n    kind: local\n    path: {data_dev}\n    env: dev\n"
        )
        check(
            "Edit in an `env: prod` data.yaml tree with env=dev → block, names the tree",
            call("Edit", file_path=os.path.join(data_prod, "db.sqlite")),
            2,
            "`corpus`",
        )
        check(
            "…and the same refusal names data.yaml",
            call("Edit", file_path=os.path.join(data_prod, "db.sqlite")),
            2,
            "`data.yaml` declares it",
        )
        check(
            "Bash write-shaped into an `env: prod` tree with env=dev → block",
            call("Bash", command=f"cp x.db {data_prod}/db.sqlite"),
            2,
            "corpus",
        )
        check(
            "redirect into an `env: prod` tree with env=dev → block",
            call("Bash", command=f"echo x >> {data_prod}/notes.md"),
            2,
            "corpus",
        )
        check(
            "Read of an `env: prod` tree with env=dev + scope-allow → allow (reads are the scope rule's)",
            call("Read", file_path=os.path.join(data_prod, "db.sqlite")),
            0,
        )
        check(
            "Edit in an `env: both` tree with env=dev → allow",
            call("Edit", file_path=os.path.join(data_both, "notes.md")),
            0,
        )
        check(
            "Edit in an `env: dev` tree with env=dev → allow",
            call("Edit", file_path=os.path.join(data_dev, "notes.md")),
            0,
        )
        set_marker("prod\n")
        check(
            "Edit in the same `env: prod` tree when this clone is prod → allow",
            call("Edit", file_path=os.path.join(data_prod, "db.sqlite")),
            0,
        )
        set_marker(None)
        set_data(
            "data:\n  - name: corpus\n    kind: local\n    env: prod\n    path: $MYDATA/tree\n"
        )
        check(
            "`$VAR` in a prod tree's path expands → block",
            call(
                "Edit",
                e=env(MYDATA=data_var),
                file_path=os.path.join(data_var, "tree", "db.sqlite"),
            ),
            2,
            "corpus",
        )
        check(
            "an unset `$VAR` skips the tree with a note, never a guess and never a block",
            call("Edit", file_path=os.path.join(data_var, "tree", "db.sqlite")),
            0,
            "unset means stop and ask",
        )
        set_data(
            "data:\n  - name: corpus\n    kind: local\n    env: prod\n    nested:\n      a: b\n"
        )
        check(
            "malformed data.yaml → allow with a note (data-check.py is the loud check)",
            call("Edit", file_path=os.path.join(data_prod, "db.sqlite")),
            0,
            "scope-guard: note:",
        )
        set_data("data: []\n")
        check(
            "`data: []` → no deny rows, no note",
            call("Edit", file_path=os.path.join(data_prod, "x")),
            0,
        )
        set_data(None)
        set_allow([])
        # --- code inside a command is not a path list -----------------------------
        check(
            "a jq filter's `)/(` is not an absolute path",
            call("Bash", command='gh pr view 1 --jq "\\(.a)/\\(.b)"'),
            0,
        )
        check(
            "an `s/foo/bar/` substitution is not a path",
            call("Bash", command="sed -i '' 's/foo/bar/' README.md"),
            0,
        )
        check(
            "a URL's `//` is not a path",
            call("Bash", command="curl -s https://api.github.com/repos/o/r"),
            0,
        )
        check(
            "a heredoc BODY is data, not a path list",
            call("Bash", command="python3 - <<'PY'\n" + 'ROOT = "/not/a/real/path"\n' + "PY"),
            0,
        )
        check(
            "a redirect INTO an out-of-scope path still blocks, heredoc or not",
            call("Bash", command="cat > " + os.path.join(other, "f") + " <<'EOF'\nx\nEOF"),
            2,
        )
        check(
            "a slash-command name is not a path",
            call("Bash", command="echo 'run /alemax:complete-update next'"),
            0,
        )
        check(
            "a command name with a trailing colon is not a path",
            call("Bash", command="echo 'see /alemax: family'"),
            0,
        )
        check(
            "an absolute token whose first segment does not exist is not a path",
            call("Bash", command="echo '/nosuchroot/foo/bar'"),
            0,
        )
        check(
            "a real out-of-scope path under an existing root still blocks",
            call("Bash", command="grep x " + os.path.join(other, "CLAUDE.md")),
            2,
        )
        check(
            "a path quoted in a feedback sentence is prose, not a path",
            call(
                "Bash",
                command="uv run alemax feedback add --kind friction 'the folder becomes "
                + os.path.join(other, "plugins")
                + " here'",
            ),
            0,
        )
        check(
            "a path quoted in a commit message is prose, not a path",
            call("Bash", command="git commit -m 'moved from " + other + " to here'"),
            0,
        )
        check(
            "a single-word argument after a message flag is still a path",
            call("Bash", command="git commit -m " + os.path.join(other, "msg.txt")),
            2,
        )
        spaced = os.path.join(other, "Mobile Documents", "x")
        check(
            "a path quoted in a commit message after `git -C` is prose",
            call("Bash", command=f"git -C {root} commit -m 'moved from {other} to here'"),
            0,
        )
        check(
            "prose ends at `&&` — the next command's spaced path is checked",
            call("Bash", command=f"uv run alemax feedback add 'note' && rm -rf '{spaced}'"),
            2,
        )
        check(
            "prose ends at `;` written without spaces",
            call("Bash", command=f"git commit -m 'a b';cat '{spaced}'"),
            2,
        )
        check(
            "`touch -m` takes no message — its spaced path is checked",
            call("Bash", command=f"touch -m '{spaced}'"),
            2,
        )
        check(
            "`ls -m` takes no message — its spaced path is checked",
            call("Bash", command=f"ls -m '{spaced}'"),
            2,
        )
        check(
            "a `$(…)` inside a commit message is not prose",
            call("Bash", command=f"git commit -m \"x $(cat '{spaced}')\""),
            2,
        )
        claude_json = os.path.join(home, ".claude.json")
        check(
            "/doctor's read of ~/.claude.json → allow",
            call("Bash", command="jq empty " + claude_json),
            0,
        )
        check("Read of ~/.claude.json → allow", call("Read", file_path=claude_json), 0)
        check(
            "a write to ~/.claude.json is still refused",
            call("Write", file_path=claude_json),
            2,
        )
        check(
            "listing ~/.local/bin → allow",
            call("Bash", command="ls -la " + os.path.join(home, ".local", "bin")),
            0,
        )
        check(
            "`yq -i` on ~/.claude.json is a write → refused",
            call("Bash", command="yq -i '.x = 1' " + claude_json),
            2,
        )
        check(
            "`sort -o` into ~/.local/bin is a write → refused",
            call(
                "Bash",
                command="sort -o " + os.path.join(home, ".local", "bin", "claude") + " /dev/null",
            ),
            2,
        )
        check(
            "a reader piped into a writer on ~/.claude.json → refused",
            call("Bash", command=f"jq . {claude_json} | awk -i inplace 1 {claude_json}"),
            2,
        )
        # --- fail open for reads, closed for writes (design D6) ---
        check(
            "malformed hook input → exit 0 with a note",
            evaluate({"tool_name": "Read"}, env(), root),
            0,
            "note",
        )
        check(
            "malformed Edit (tool_input not an object) → exit 2",
            evaluate({"tool_name": "Edit", "tool_input": "x"}, env(), root),
            2,
            "guard error",
        )
        check(
            "malformed Read (tool_input not an object) → exit 0 with a note",
            evaluate({"tool_name": "Read", "tool_input": "x"}, env(), root),
            0,
            "note",
        )

        def hook_with_broken_guard(stdin: str) -> tuple[int, str]:
            """run_hook with evaluate() raising — the guard-error path."""
            import io

            def boom(*_a: object, **_k: object) -> tuple[int, str]:
                raise RuntimeError("synthetic guard defect")

            saved_eval, saved_in, saved_err = globals()["evaluate"], sys.stdin, sys.stderr
            globals()["evaluate"], sys.stdin, sys.stderr = boom, io.StringIO(stdin), io.StringIO()
            try:
                code = run_hook()
                return code, sys.stderr.getvalue()
            finally:
                globals()["evaluate"], sys.stdin, sys.stderr = saved_eval, saved_in, saved_err

        check(
            "guard error on an Edit → exit 2 (refused)",
            hook_with_broken_guard(
                json.dumps({"tool_name": "Edit", "tool_input": {"file_path": "x"}})
            ),
            2,
            "guard error",
        )
        check(
            "guard error on a Read → exit 0 with a note",
            hook_with_broken_guard(
                json.dumps({"tool_name": "Read", "tool_input": {"file_path": "x"}})
            ),
            0,
            "allowing",
        )
        check(
            "unparseable stdin → exit 0 with a note",
            hook_with_broken_guard("{not json"),
            0,
            "could not parse",
        )
        check(
            "no CLAUDE_PROJECT_DIR, cwd outside any repo → cwd is the root",
            call(
                "Read",
                cwd=tmpdir,
                e={"HOME": home, "TMPDIR": tmpdir},
                file_path=os.path.join(tmpdir, "a"),
            ),
            0,
        )

        print(f"scope-guard --self-test: {n - len(failures)}/{n} passed")
        for f in failures:
            print(f"  FAIL {f}")
        return 0 if not failures else 1


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["--self-test"]:
        return self_test()
    if argv[:1] in (["-h"], ["--help"]):
        print(__doc__)
        return 0
    return run_hook()


if __name__ == "__main__":
    sys.exit(main())
