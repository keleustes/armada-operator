"""The Claude ↔ Codex conversion rule table — one copy, in the package, printed on demand.

Three consumers each carried a `render_codex.py` with its own table, and the tables
disagreed. This is the one table (design D2). Each rule rewrites only what it matches
(D3); text no rule covers is copied, and whatever still reads as the other harness's
vocabulary afterwards is reported, never guessed.

Directions: `to_codex` turns a Claude body into a Codex draft; `to_claude` the reverse.
Rules that need to know the plugin family (a `$family-verb` pointer, a
`.agents/skills/family-verb/` path) take the set of known families so the split is
never guessed at a hyphen.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass

TO_CODEX = "to_codex"
TO_CLAUDE = "to_claude"

# Tokens that are one harness's and should not appear in the other's body. Used by the
# remaining-foreign scan after a draft and by `twin check`. Slash pointers and `$` pointers
# are matched by pattern, not listed here.
CLAUDE_TOOLS = ("TodoWrite", "ListAgents", "SendMessage", "ToolSearch", "AskUserQuestion")
CODEX_TOOLS = ("list_agents", "send_message", "update_plan", "apply_patch", "spawn_agent")

SLASH_POINTER = re.compile(r"(?<![\w/.:])/([a-z][a-z0-9-]*):([a-z][a-z0-9-]*)\b")
SKILL_DIR_VAR = re.compile(r"\$\{CLAUDE_SKILL_DIR\}/?")
CLAUDE_SKILL_PATH = re.compile(r"\.claude/skills/([a-z0-9-]+)/skills/([a-z0-9-]+)/")


@dataclass(frozen=True)
class Rule:
    kind: str
    direction: str
    pattern: str
    replacement: str | Callable[[re.Match], str]
    note: str

    def apply(self, text: str) -> tuple[str, list[int]]:
        """Rewrite `text`; return it and the 1-based line numbers where the rule fired."""
        fired: list[int] = []
        out_lines: list[str] = []
        for i, line in enumerate(text.split("\n"), 1):
            new, n = re.subn(self.pattern, self.replacement, line)
            if n:
                fired.append(i)
            out_lines.append(new)
        return "\n".join(out_lines), fired


def _dollar_pointer(families: Iterable[str]) -> re.Pattern[str]:
    fams = sorted(families, key=len, reverse=True)
    alt = "|".join(re.escape(f) for f in fams) if fams else r"[a-z][a-z0-9]*"
    return re.compile(rf"\$({alt})-([a-z][a-z0-9-]*)\b")


def _agents_path(families: Iterable[str]) -> re.Pattern[str]:
    fams = sorted(families, key=len, reverse=True)
    alt = "|".join(re.escape(f) for f in fams) if fams else r"[a-z][a-z0-9]*"
    return re.compile(rf"\.agents/skills/({alt})-([a-z][a-z0-9-]*)/")


def rules(direction: str, families: Iterable[str] = ()) -> list[Rule]:
    """The ordered table for one direction. Order matters: paths before pointers."""
    families = set(families)
    if direction == TO_CODEX:
        return [
            Rule(
                "path",
                TO_CODEX,
                CLAUDE_SKILL_PATH.pattern,
                r".agents/skills/\1-\2/",
                "Claude nested skill path → Codex flat prefixed path",
            ),
            Rule(
                "skill-dir",
                TO_CODEX,
                SKILL_DIR_VAR.pattern,
                "the skill's own directory (resolve this SKILL.md through any symlink)/",
                "${CLAUDE_SKILL_DIR} → working-directory wording",
            ),
            Rule(
                "pointer",
                TO_CODEX,
                SLASH_POINTER.pattern,
                r"$\1-\2",
                "/family:verb slash pointer → $family-verb",
            ),
            Rule(
                "tool",
                TO_CODEX,
                r"\bListAgents\b",
                "list_agents",
                "Claude ListAgents → Codex list_agents",
            ),
            Rule(
                "tool",
                TO_CODEX,
                r"\bSendMessage\b",
                "send_message",
                "Claude SendMessage → Codex send_message",
            ),
            Rule(
                "tool",
                TO_CODEX,
                r"\bTodoWrite\b",
                "the change's `tasks.md` checkboxes",
                "TodoWrite → the durable tracker every harness has",
            ),
            Rule(
                "tool",
                TO_CODEX,
                r"\bAskUserQuestion\b",
                "a question to the operator",
                "AskUserQuestion → plain question",
            ),
        ]
    if direction == TO_CLAUDE:
        return [
            Rule(
                "path",
                TO_CLAUDE,
                _agents_path(families).pattern,
                r".claude/skills/\1/skills/\2/",
                "Codex flat prefixed path → Claude nested skill path",
            ),
            Rule(
                "pointer",
                TO_CLAUDE,
                _dollar_pointer(families).pattern,
                r"/\1:\2",
                "$family-verb → /family:verb slash pointer",
            ),
            Rule(
                "tool",
                TO_CLAUDE,
                r"\blist_agents\b",
                "ListAgents",
                "Codex list_agents → Claude ListAgents",
            ),
            Rule(
                "tool",
                TO_CLAUDE,
                r"\bsend_message\b",
                "SendMessage",
                "Codex send_message → Claude SendMessage",
            ),
        ]
    raise ValueError(f"unknown direction {direction!r}")


def convert(
    text: str, direction: str, families: Iterable[str] = ()
) -> tuple[str, list[tuple[Rule, list[int]]]]:
    """Apply every rule of one direction, in order; return the text and the firing log."""
    log: list[tuple[Rule, list[int]]] = []
    for rule in rules(direction, families):
        text, fired = rule.apply(text)
        if fired:
            log.append((rule, fired))
    return text, log


def foreign(text: str, harness: str, families: Iterable[str] = ()) -> list[tuple[int, str]]:
    """(line, token) for every token of the OTHER harness's vocabulary found in a body
    meant for `harness`. Fenced code and inline code are scanned too — a foreign tool name
    in a command is still foreign."""
    hits: list[tuple[int, str]] = []
    if harness == "codex":
        tokens = [re.compile(rf"\b{t}\b") for t in CLAUDE_TOOLS] + [SLASH_POINTER, SKILL_DIR_VAR]
    elif harness == "claude":
        tokens = [re.compile(rf"\b{t}\b") for t in CODEX_TOOLS] + [_dollar_pointer(families)]
    else:
        raise ValueError(f"unknown harness {harness!r}")
    for i, line in enumerate(text.split("\n"), 1):
        for pat in tokens:
            for m in pat.finditer(line):
                hits.append((i, m.group(0)))
    return hits


def table() -> str:
    """The whole table, human-readable, for `alemax twin rules`."""
    out = ["direction   kind       pattern                                  note"]
    for direction in (TO_CODEX, TO_CLAUDE):
        for r in rules(direction, ("family",)):
            out.append(f"{direction:<11} {r.kind:<10} {r.pattern[:40]:<40} {r.note}")
    return "\n".join(out)
