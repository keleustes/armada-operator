"""`alemax twin` — the other harness's body, drafted from this one; and a family's two
skill trees checked against each other.

`draft` writes ONCE, to a path that does not exist, and prints every rule that fired and
every line that still reads as the other harness. It is an authoring aid a person or a
session reviews before committing — never a render (spec `skill-twin-authoring`).

`check` reports what actually went wrong across the fleet: a skill with no twin, twins
that run different programs, one harness's vocabulary in the other's body, a script path
that resolves nowhere, and steps one twin has that the other lacks. Report by default;
`--strict` refuses. It replaces each project's `render_codex.py --check`.
"""

from __future__ import annotations

import argparse
import difflib
import re
import sys
import tomllib
from pathlib import Path

from .. import skillbody as sb
from .. import twin_rules as tr
from ..io import ERROR, FOUND, OK, die, emit
from ..repo import toplevel

# Placed anywhere in EITHER body: this pair differs in what it runs and how it is shaped
# on purpose (the Codex lint bodies run a Codex-only linter). Invocation and substance
# findings for the pair are reported under `intentional` — still visible, never refused.
# A single step is marked with `<!-- twin: intentional -->` on its own line instead.
INTENTIONAL_PAIR = re.compile(r"<!-- twin: intentional pair(?:\s*[—-][^>]*)? -->")
KINDS = (
    "missing_twin",
    "invocation_mismatch",
    "foreign_vocabulary",
    "dangling_script",
    "substance_drift",
    "intentional",
)


def root_for(a: argparse.Namespace) -> Path:
    return Path(a.root).resolve() if a.root else toplevel()


# ---------------------------------------------------------------- draft


def direction_of(path: Path, to: str | None) -> tuple[str, str]:
    """(from_harness, to_harness) from the path, or from --to when the path is ambiguous."""
    s = str(path)
    if to:
        return ("codex" if to == "claude" else "claude"), to
    if "/.claude/skills/" in s or "/templates/claude/" in s:
        return "claude", "codex"
    if "/.agents/skills/" in s or "/templates/codex/" in s:
        return "codex", "claude"
    die("cannot tell the harness from the path — pass --to claude|codex")


def family_verb(path: Path, harness: str, families: set[str]) -> tuple[str, str]:
    parts = path.resolve().parts
    if harness == "claude":
        # …/<family>/skills/<verb>/SKILL.md  or  …/templates/claude/skills/<verb>/SKILL.md
        if len(parts) >= 4 and parts[-3] == "skills":
            fam = parts[-4]
            if fam == "claude" and len(parts) >= 6 and parts[-5] == "templates":
                fam = parts[-6]  # plugins/<family>/templates/claude/skills/<verb>
            return fam, parts[-2]
        die(f"not a Claude skill path: {path}")
    name = parts[-2]
    split = sb.split_codex_name(name, families)
    if not split:
        die(f"not a Codex skill path: {path}")
    return split


def destination(root: Path, family: str, verb: str, to: str) -> Path:
    if to == "codex":
        return root / ".agents" / "skills" / f"{family}-{verb}" / "SKILL.md"
    return root / ".claude" / "skills" / family / "skills" / verb / "SKILL.md"


CLAUDE_ONLY = ("context", "argument-hint", "allowed-tools")


def convert_frontmatter(
    front: list[str], family: str, verb: str, to: str, commands: list[str]
) -> list[str]:
    """Codex: prefix the name, drop the Claude-only keys. Claude: strip the prefix, add the
    Claude-only keys with placeholders the author must fill (allowed-tools derived from
    the body's commands when there are any)."""
    if not front:
        front = ["---", f"name: {verb}", "---"]
    out: list[str] = []
    dropping = False
    for line in front:
        key = re.match(r"^([A-Za-z_-]+):", line)
        if key and key.group(1) in CLAUDE_ONLY and to == "codex":
            dropping = True
            continue
        if dropping and line.startswith((" ", "\t")) and line.strip():
            continue
        dropping = False
        if key and key.group(1) == "name":
            line = f"name: {family}-{verb}" if to == "codex" else f"name: {verb}"
        out.append(line)
    if to == "claude":
        present = {
            re.match(r"^([A-Za-z_-]+):", ln).group(1)
            for ln in out
            if re.match(r"^([A-Za-z_-]+):", ln)
        }
        extra: list[str] = []
        if "context" not in present:
            extra.append("context: either  # PLACEHOLDER — either | project | claude-meta-only")
        if "argument-hint" not in present:
            extra.append('argument-hint: "<PLACEHOLDER>"')
        if "allowed-tools" not in present:
            progs: set[str] = set()
            for c in commands:
                toks = sb.normalise(c).split()
                if toks[:3] == ["uv", "run", "--directory"]:
                    progs.add(" ".join(toks[:6]))
                elif toks[:2] == ["uv", "run"]:
                    progs.add(" ".join(toks[:4]))
                elif toks:
                    progs.add(" ".join(toks[:2]))
            tools = " ".join(f"Bash({p} *)" for p in sorted(progs)) or "Bash(PLACEHOLDER *)"
            extra.append(f"allowed-tools: {tools}  # PLACEHOLDER — review")
        close = len(out) - 1  # the trailing '---'
        out = out[:close] + extra + out[close:]
    return out


def cmd_draft(a: argparse.Namespace) -> int:
    root = root_for(a)
    src = Path(a.path)
    if not src.is_absolute():
        src = (Path.cwd() / src).resolve()
    if not src.is_file():
        die(f"no such skill body: {src}")
    frm, to = direction_of(src, a.to)
    families = set(sb.discover(root))
    family, verb = family_verb(src, frm, families)
    dest = destination(root, family, verb, to)
    if dest.exists() and not a.force:
        die(
            f"twin already exists: {dest}\n  (source {src})\n"
            "  a draft never overwrites a reviewed body; pass --force to replace it, "
            "and the diff is printed first"
        )
    text = src.read_text(encoding="utf-8")
    front, body = sb.split_frontmatter(text)
    body_text = "\n".join(body)
    commands = sb.invocations(body_text)
    new_body, log = tr.convert(body_text, tr.TO_CODEX if to == "codex" else tr.TO_CLAUDE, families)
    new_front = convert_frontmatter(front, family, verb, to, commands)
    from datetime import date

    note = (
        f"<!-- DRAFT twin, converted {date.today().isoformat()} by `alemax twin draft` from\n"
        f"     {src.relative_to(root) if src.is_relative_to(root) else src}.\n"
        "     Review before committing: the rule log and the remaining foreign lines were\n"
        "     printed at draft time; run `alemax twin check` to see them again. -->"
    )
    draft = "\n".join(new_front) + "\n" + note + "\n" + new_body
    draft = re.sub(r"\n{3,}", "\n\n", draft).rstrip("\n") + "\n"
    remaining = tr.foreign(new_body, to, families)
    if dest.exists():
        old = dest.read_text(encoding="utf-8")
        diff = difflib.unified_diff(
            old.splitlines(), draft.splitlines(), str(dest), "draft", lineterm=""
        )
        print("\n".join(diff))
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(draft, encoding="utf-8")
    payload = {
        "from": str(src),
        "to": str(dest),
        "direction": f"{frm} -> {to}",
        "rules_fired": [{"kind": r.kind, "note": r.note, "lines": lines} for r, lines in log],
        "remaining_foreign": [{"line": ln, "token": tok} for ln, tok in remaining],
    }
    lines_out = [f"drafted {dest}  ({frm} -> {to}, from {src})"]
    for r, lines in log:
        lines_out.append(f"  rule {r.kind:<10} {r.note}  lines {','.join(map(str, lines))}")
    if remaining:
        lines_out.append("  still reads as the other harness — rewrite by hand:")
        for ln, tok in remaining:
            lines_out.append(f"    line {ln}: {tok}")
    emit(payload, as_json=a.json, plain="\n".join(lines_out))
    return OK


# ---------------------------------------------------------------- check


def load_extra_rules(path: str | None) -> list[tr.Rule]:
    if not path:
        return []
    data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    out: list[tr.Rule] = []
    for row in data.get("rule", []):
        out.append(
            tr.Rule(
                row.get("kind", "custom"),
                row["direction"],
                row["pattern"],
                row["replacement"],
                row.get("note", "project rule"),
            )
        )
    return out


def check_family(root: Path, fam: sb.Family, families: set[str]) -> list[dict]:
    findings: list[dict] = []

    def add(kind: str, skill: sb.Skill, message: str, **detail) -> None:
        findings.append(
            {"kind": kind, "family": fam.name, "verb": skill.verb, "message": message, **detail}
        )

    for verb, skill in sorted(fam.skills.items()):
        if not skill.claude:
            add(
                "missing_twin",
                skill,
                f"{fam.name} {verb}: no Claude twin (Codex body at {skill.codex})",
            )
            continue
        if not skill.codex:
            add(
                "missing_twin",
                skill,
                f"{fam.name} {verb}: no Codex twin (Claude body at {skill.claude})",
            )
            continue
        ct = skill.claude.read_text(encoding="utf-8")
        xt = skill.codex.read_text(encoding="utf-8")
        _, cbody = sb.split_frontmatter(ct)
        _, xbody = sb.split_frontmatter(xt)
        cbody_t, xbody_t = "\n".join(cbody), "\n".join(xbody)
        # invocations. A body may declare that its harness runs a different program on
        # purpose (the Codex lint bodies run codex_lint.py, a Codex-only linter): the
        # marker moves the finding under `intentional`, where it stays visible.
        cprog = {sb.program(c) for c in sb.invocations(cbody_t)}
        xprog = {sb.program(c) for c in sb.invocations(xbody_t)}
        cprog = {p for p in cprog if p[0] != "other"}
        xprog = {p for p in xprog if p[0] != "other"}
        pair_intentional = bool(INTENTIONAL_PAIR.search(ct) or INTENTIONAL_PAIR.search(xt))
        if cprog != xprog and pair_intentional:
            add(
                "intentional",
                skill,
                f"{fam.name} {verb}: the twins run different programs, marked intentional",
                claude=sorted(f"{k}: {i}" for k, i in cprog),
                codex=sorted(f"{k}: {i}" for k, i in xprog),
            )
        elif cprog != xprog:
            add(
                "invocation_mismatch",
                skill,
                f"{fam.name} {verb}: the two bodies run different programs",
                claude=sorted(f"{k}: {i}" for k, i in cprog),
                codex=sorted(f"{k}: {i}" for k, i in xprog),
                claude_lines=[c for c in sb.invocations(cbody_t) if sb.program(c)[0] != "other"],
                codex_lines=[c for c in sb.invocations(xbody_t) if sb.program(c)[0] != "other"],
            )
        # foreign vocabulary
        for ln, tok in tr.foreign(xbody_t, "codex", families):
            add(
                "foreign_vocabulary",
                skill,
                f"{fam.name} {verb}: Codex body line {ln} carries `{tok}`",
                harness="codex",
                line=ln,
                token=tok,
            )
        for ln, tok in tr.foreign(cbody_t, "claude", families):
            add(
                "foreign_vocabulary",
                skill,
                f"{fam.name} {verb}: Claude body line {ln} carries `{tok}`",
                harness="claude",
                line=ln,
                token=tok,
            )
        # dangling scripts
        for harness, path, text in (("claude", skill.claude, ct), ("codex", skill.codex, xt)):
            for ln, rel in sb.script_paths(text):
                candidates = [root / rel, path.parent / rel]
                if not any(c.is_file() for c in candidates):
                    add(
                        "dangling_script",
                        skill,
                        f"{fam.name} {verb}: {harness} body line {ln} names `{rel}`, which does not exist",
                        harness=harness,
                        line=ln,
                        path=rel,
                    )
        # substance (D5): the shape, not the wording. Step COUNT — a reworded step is the
        # same step; an extra one is not. Programs run, by identity, when the invocation
        # check above did not already say so. Section headings are NOT compared: the two
        # harnesses' bodies organise their sections differently by convention ("Steps" on
        # Claude, "Workflow" on Codex), and a heading difference never once meant a
        # behaviour difference in the first run over 19 pairs.
        cs, xs = sb.structure(cbody_t), sb.structure(xbody_t)
        detail: dict = {}
        # a step marked intentional still counts as a step; it is just not a finding
        c_all = {n for n, _ in cs.steps} | {n for n, _ in cs.intentional}
        x_all = {n for n, _ in xs.steps} | {n for n, _ in xs.intentional}
        if len(c_all) != len(x_all):
            detail["steps_only_in_claude"] = [f"{n}. {s}" for n, s in cs.steps if n not in x_all]
            detail["steps_only_in_codex"] = [f"{n}. {s}" for n, s in xs.steps if n not in c_all]
            detail["step_count"] = f"claude {len(c_all)}, codex {len(x_all)}"
        already = any(
            f["kind"] in ("invocation_mismatch", "intentional") and f["verb"] == verb
            for f in findings
        )
        if cs.programs != xs.programs and not already:
            detail["programs_only_in_claude"] = sorted(
                f"{k}: {i}" for k, i in cs.programs - xs.programs
            )
            detail["programs_only_in_codex"] = sorted(
                f"{k}: {i}" for k, i in xs.programs - cs.programs
            )
        if detail:
            kind = "intentional" if pair_intentional else "substance_drift"
            msg = (
                "the twins differ in shape, marked intentional"
                if pair_intentional
                else "the twins differ in substance"
            )
            add(kind, skill, f"{fam.name} {verb}: {msg}", **detail)
        for n, s in cs.intentional + xs.intentional:
            add("intentional", skill, f"{fam.name} {verb}: step {n} marked intentional — {s}")
    return findings


def cmd_check(a: argparse.Namespace) -> int:
    root = root_for(a)
    fams = sb.discover(root, a.family or None)
    if a.family:
        missing = set(a.family) - set(fams)
        if missing:
            die(f"no such family here: {', '.join(sorted(missing))}")
    if not fams:
        die("no skill families found under .claude/skills/<family>/skills/ or .agents/skills/")
    families = set(sb.discover(root))
    findings: list[dict] = []
    for fam in fams.values():
        findings.extend(check_family(root, fam, families))
    real = [f for f in findings if f["kind"] != "intentional"]
    grouped = {k: [f for f in findings if f["kind"] == k] for k in KINDS}
    lines = [
        f"twin check: {len(fams)} famil{'y' if len(fams) == 1 else 'ies'}, {sum(len(f.skills) for f in fams.values())} skills, {len(real)} finding(s)"
    ]
    for kind in KINDS:
        if not grouped[kind]:
            continue
        lines.append(f"\n{kind} ({len(grouped[kind])})")
        for f in grouped[kind]:
            lines.append(f"  {f['message']}")
            for key in (
                "claude",
                "codex",
                "claude_lines",
                "codex_lines",
                "step_count",
                "steps_only_in_claude",
                "steps_only_in_codex",
                "programs_only_in_claude",
                "programs_only_in_codex",
            ):
                if f.get(key):
                    val = f[key]
                    lines.append(
                        f"    {key}: " + (val if isinstance(val, str) else " | ".join(val))
                    )
    emit(
        {"root": str(root), "findings": grouped, "count": len(real)},
        as_json=a.json,
        plain="\n".join(lines),
    )
    if real and a.strict:
        print(f"twin check: {len(real)} finding(s) — refused (--strict)", file=sys.stderr)
        return ERROR
    return FOUND if real else OK


def cmd_rules(a: argparse.Namespace) -> int:
    print(tr.table())
    return OK


SUBCOMMANDS = {
    "draft": (cmd_draft, "write the other harness's body from this one, once, never over a twin"),
    "check": (
        cmd_check,
        "a family's two trees: missing twins, different programs, foreign words, dangling scripts, drift",
    ),
    "rules": (cmd_rules, "print the Claude <-> Codex conversion rule table"),
}


def register(ap: argparse.ArgumentParser) -> None:
    ap.add_argument("--root", help="repo toplevel (default: git rev-parse --show-toplevel)")
    subs = ap.add_subparsers(dest="subcommand", required=True, metavar="SUBCOMMAND")
    for name, (fn, help_text) in SUBCOMMANDS.items():
        sp = subs.add_parser(name, help=help_text)
        if name == "draft":
            sp.add_argument("path", help="the skill body to convert (a SKILL.md on either harness)")
            sp.add_argument(
                "--to",
                choices=("claude", "codex"),
                help="target harness (inferred from the path when possible)",
            )
            sp.add_argument(
                "--force",
                action="store_true",
                help="replace an existing twin (its diff is printed first)",
            )
            sp.add_argument("--json", action="store_true", help="machine-readable output")
        elif name == "check":
            sp.add_argument(
                "--family",
                action="append",
                help="one family (repeatable); default: every family found",
            )
            sp.add_argument("--all", action="store_true", help="every family (the default)")
            sp.add_argument("--strict", action="store_true", help="exit non-zero on any finding")
            sp.add_argument("--rules", help="TOML with extra [[rule]] rows for this project")
            sp.add_argument("--json", action="store_true", help="machine-readable output")
        sp.set_defaults(func=fn)
