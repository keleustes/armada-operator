#!/usr/bin/env python3
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""reconcile-settings.py — fold the tracked settings floor into settings.local.json.

A claude-meta-managed repo tracks `.claude/settings-template.json` — the FLOOR of
Claude Code settings every session of the repo needs (spec `settings-template`) —
and never a `.claude/settings.json`. Claude Code reads only `settings.local.json`
(gitignored, yours) and `settings.json`; the floor is inert until this script
folds it in. Each session reconciles its own local file:

  uv run --script bin/reconcile-settings.py check     # 0 in sync · 1 floor entries missing · 2 file error
  uv run --script bin/reconcile-settings.py diff      # unified diff local → reconciled; exit as check
  uv run --script bin/reconcile-settings.py apply     # write the reconciled local file
  uv run --script bin/reconcile-settings.py apply --stage   # write .local/settings.local.proposed.json instead

The floor is never the ceiling. For `permissions.allow`, `permissions.deny`,
`permissions.ask` and every `hooks.<event>` list: each template entry absent from
the local file is APPENDED (template order, exact-string / exact-object match);
a local entry absent from the template is NEVER removed — it is listed as
local-only, a candidate to promote into the floor. One exception: a local hook
entry that runs only hook files the floor ships (`.claude/hooks/<file>`), when the
template's entry for the same event runs that file differently, is SUPERSEDED —
replaced in place by the template's entry, and reported as `~ replaced`. Without
it, a floor that moved scope-guard from `python3 …` to `uv run --script …` left both
entries, and scope-guard ran twice on every call. Every other key is merged
shallowly: added when the local file lacks it, otherwise the local value wins.
Output is deterministic (2-space indent, key order stable, trailing newline).

`.claude/` is a protected path: the harness prompts for the write, or routes it
to the auto-mode classifier, whatever allow rules say. When `apply` is refused —
by the harness before it runs, or by the OS while it runs — `apply --stage`
writes the proposal under `.local/` and prints the one `cp` line the operator
runs. Exit 3 = staged, operator step pending.

Defaults: the template is `<toplevel>/.claude/settings-template.json`; the local
file is `<main checkout>/.claude/settings.local.json`, because Claude Code reads
it at the main checkout's root even in a worktree session. `--template` may name
a tracked `.claude/settings.json` to fold its rules into the local file before
`git rm`-ing it. A `Write(path)`, `NotebookEdit(path)`, `MultiEdit(path)` or
`Glob(path)` rule is accepted by Claude Code but never consulted (only `Edit` and
`Read` path rules are); the script warns when it meets one.
"""

from __future__ import annotations

import argparse
import copy
import difflib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

TEMPLATE_REL = Path(".claude") / "settings-template.json"
LOCAL_REL = Path(".claude") / "settings.local.json"
STAGE_REL = Path(".local") / "settings.local.proposed.json"
CP_LINE = "! cp .local/settings.local.proposed.json .claude/settings.local.json"

LIST_KEYS = ("allow", "deny", "ask")
HOOK_FILE_RE = re.compile(r"\.claude/hooks/([A-Za-z0-9_.-]+)")
INERT_RULE_PREFIXES = ("Write(", "NotebookEdit(", "MultiEdit(", "Glob(")

EXIT_OK = 0
EXIT_MISSING = 1
EXIT_FILE = 2
EXIT_STAGED = 3


class FileError(Exception):
    pass


# --- repo roots -------------------------------------------------------------


def git(*args: str) -> str | None:
    try:
        done = subprocess.run(["git", *args], check=True, capture_output=True, text=True)
    except OSError, subprocess.CalledProcessError:
        return None
    return done.stdout.strip()


def repo_roots() -> tuple[Path, Path]:
    """(toplevel of the cwd's worktree, root of the main checkout).

    Claude Code stores and reads `.claude/settings.local.json` at the MAIN
    checkout's root, resolved through worktrees; the template is read from the
    tree being worked on. Outside a git repo both are the cwd.
    """
    top = git("rev-parse", "--show-toplevel")
    if not top:
        return Path.cwd(), Path.cwd()
    toplevel = Path(top)
    common = git("rev-parse", "--path-format=absolute", "--git-common-dir")
    if common and Path(common).name == ".git":
        return toplevel, Path(common).parent
    return toplevel, toplevel


# --- json in / out ----------------------------------------------------------


def load(path: Path, *, required: bool) -> dict[str, Any]:
    if not path.exists():
        if required:
            raise FileError(f"{path}: not found")
        return {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise FileError(f"{path}: {exc.strerror}") from exc
    if not text.strip():
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise FileError(f"{path}: invalid JSON — {exc}") from exc
    if not isinstance(data, dict):
        raise FileError(f"{path}: top level must be a JSON object")
    return data


def dump(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def canon(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


# --- the reconcile ----------------------------------------------------------


class Report:
    def __init__(self) -> None:
        self.added: list[str] = []  # "+ <where>: <entry>"
        self.replaced: list[str] = []  # "~ <where>: replaced <old> -> <new>"
        self.local_only: list[str] = []  # "= <where> local-only: <entries>"
        self.kept: list[str] = []  # "= <key>: local wins"
        self.warnings: list[str] = []

    @property
    def missing(self) -> int:
        return len(self.added) + len(self.replaced)


def show(value: Any) -> str:
    return value if isinstance(value, str) else canon(value)


def merge_list(where: str, t_list: Any, l_parent: dict[str, Any], key: str, rep: Report) -> None:
    t_items = list(t_list or [])
    l_items = list(l_parent.get(key) or [])
    seen = {canon(e) for e in l_items}
    missing = [e for e in t_items if canon(e) not in seen]
    if missing:
        l_parent.setdefault(key, [])
        if l_parent[key] is None:
            l_parent[key] = []
        l_parent[key].extend(copy.deepcopy(missing))
        rep.added.extend(f"+ {where}: {show(e)}" for e in missing)
    t_seen = {canon(e) for e in t_items}
    extra = [e for e in l_items if canon(e) not in t_seen]
    if extra:
        rep.local_only.append(
            f"= {where} local-only (candidates to promote): " + ", ".join(show(e) for e in extra)
        )


def merge_permissions(t_perms: Any, merged: dict[str, Any], rep: Report) -> None:
    t_perms = t_perms or {}
    if not isinstance(t_perms, dict):
        rep.warnings.append("WARN template permissions is not an object; ignored")
        return
    l_perms = merged.get("permissions")
    if not isinstance(l_perms, dict):
        l_perms = {}
    for key, t_val in t_perms.items():
        if key in LIST_KEYS:
            merge_list(f"permissions.{key}", t_val, l_perms, key, rep)
        elif key not in l_perms:
            l_perms[key] = copy.deepcopy(t_val)
            rep.added.append(f"+ permissions.{key}: {show(t_val)}")
        elif canon(l_perms[key]) != canon(t_val):
            rep.kept.append(
                f"= permissions.{key}: local wins ({show(l_perms[key])}; template {show(t_val)})"
            )
    if l_perms:
        merged["permissions"] = l_perms


def merge_hooks(t_hooks: Any, merged: dict[str, Any], rep: Report) -> None:
    t_hooks = t_hooks or {}
    if not isinstance(t_hooks, dict):
        rep.warnings.append("WARN template hooks is not an object; ignored")
        return
    l_hooks = merged.get("hooks")
    if not isinstance(l_hooks, dict):
        l_hooks = {}
    for event, t_val in t_hooks.items():
        retire_superseded(f"hooks.{event}", t_val, l_hooks, event, rep)
        merge_list(f"hooks.{event}", t_val, l_hooks, event, rep)
    if l_hooks:
        merged["hooks"] = l_hooks


def hook_files(entry: Any) -> set[str]:
    """The `.claude/hooks/<file>` names a hook entry's commands run."""
    return set(HOOK_FILE_RE.findall(canon(entry)))


def retire_superseded(
    where: str, t_list: Any, l_parent: dict[str, Any], key: str, rep: Report
) -> None:
    """Replace, in place, a local hook entry the floor's own entry supersedes.

    Superseded: the local entry runs only hook files the template ships, and for one of
    them the template's entry differs. The hook file is meta's, so its command is too; a
    hook of the project's own (a file the floor does not ship) is never touched.
    """
    t_items = list(t_list or [])
    l_items = l_parent.get(key)
    if not t_items or not isinstance(l_items, list):
        return
    t_canon = {canon(e) for e in t_items}
    by_file: dict[str, Any] = {}
    for e in t_items:
        for f in hook_files(e):
            by_file.setdefault(f, e)
    out: list[Any] = []
    placed = {canon(e) for e in l_items if canon(e) in t_canon}
    for e in l_items:
        files = hook_files(e)
        if canon(e) in t_canon or not files or not files <= by_file.keys():
            out.append(e)
            continue
        new = by_file[sorted(files)[0]]
        rep.replaced.append(f"~ {where}: replaced {show(e)} -> {show(new)}")
        if canon(new) not in placed:
            out.append(copy.deepcopy(new))
            placed.add(canon(new))
    l_parent[key] = out


def merge_shallow(key: str, t_val: Any, merged: dict[str, Any], rep: Report) -> None:
    if key not in merged:
        merged[key] = copy.deepcopy(t_val)
        rep.added.append(f"+ {key}: {show(t_val)}")
        return
    l_val = merged[key]
    if isinstance(t_val, dict) and isinstance(l_val, dict):
        for sub, sub_val in t_val.items():
            if sub not in l_val:
                l_val[sub] = copy.deepcopy(sub_val)
                rep.added.append(f"+ {key}.{sub}: {show(sub_val)}")
            elif canon(l_val[sub]) != canon(sub_val):
                rep.kept.append(
                    f"= {key}.{sub}: local wins ({show(l_val[sub])}; template {show(sub_val)})"
                )
        return
    if canon(l_val) != canon(t_val):
        rep.kept.append(f"= {key}: local wins ({show(l_val)}; template {show(t_val)})")


def warn_inert_rules(label: str, data: dict[str, Any], rep: Report) -> None:
    perms = data.get("permissions")
    if not isinstance(perms, dict):
        return
    for key in LIST_KEYS:
        for rule in perms.get(key) or []:
            if isinstance(rule, str) and rule.startswith(INERT_RULE_PREFIXES):
                rep.warnings.append(
                    f"WARN {label} permissions.{key}: {rule} — a path rule for this "
                    "tool is accepted but never consulted; only Edit(path) and "
                    "Read(path) are checked"
                )


def reconcile(template: dict[str, Any], local: dict[str, Any]) -> tuple[dict[str, Any], Report]:
    rep = Report()
    merged = copy.deepcopy(local)
    for key, t_val in template.items():
        if key == "permissions":
            merge_permissions(t_val, merged, rep)
        elif key == "hooks":
            merge_hooks(t_val, merged, rep)
        else:
            merge_shallow(key, t_val, merged, rep)
    # local-only hook events the template does not mention at all
    l_hooks = local.get("hooks")
    t_hooks = template.get("hooks") or {}
    if isinstance(l_hooks, dict):
        for event, entries in l_hooks.items():
            if event not in t_hooks and entries:
                rep.local_only.append(
                    f"= hooks.{event} local-only (candidates to promote): "
                    f"{len(entries)} entr{'y' if len(entries) == 1 else 'ies'}"
                )
    warn_inert_rules("template", template, rep)
    warn_inert_rules("local", local, rep)
    return merged, rep


# --- cli ---------------------------------------------------------------------


def rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def print_report(rep: Report) -> None:
    for line in rep.added:
        print(f"  {line}")
    for line in rep.replaced:
        print(f"  {line}")
    for line in rep.kept:
        print(f"  {line}")
    for line in rep.local_only:
        print(f"  {line}")
    for line in rep.warnings:
        print(f"  {line}")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="reconcile-settings.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("command", choices=("check", "diff", "apply"))
    ap.add_argument(
        "--template",
        help="the floor (default: <toplevel>/.claude/settings-template.json; "
        "may name a tracked .claude/settings.json to fold it in)",
    )
    ap.add_argument(
        "--local",
        help="the file reconciled (default: <main checkout>/.claude/settings.local.json)",
    )
    ap.add_argument(
        "--stage",
        action="store_true",
        help="apply: write .local/settings.local.proposed.json and print the cp line "
        "instead of touching .claude/",
    )
    args = ap.parse_args(argv)

    toplevel, main_root = repo_roots()
    template_path = Path(args.template).resolve() if args.template else toplevel / TEMPLATE_REL
    local_path = Path(args.local).resolve() if args.local else main_root / LOCAL_REL
    # The staged proposal sits beside the local file's .claude/, never in some other repo.
    stage_root = local_path.parent.parent if local_path.parent.name == ".claude" else main_root
    stage_path = stage_root / STAGE_REL

    try:
        template = load(template_path, required=True)
        local = load(local_path, required=False)
    except FileError as exc:
        print(f"reconcile-settings: error: {exc}", file=sys.stderr)
        return EXIT_FILE

    merged, rep = reconcile(template, local)
    before = dump(local) if local_path.exists() else ""
    after = dump(merged)

    print(
        f"reconcile-settings: template={rel(template_path, main_root)} "
        f"local={rel(local_path, main_root)}"
        f"{'' if local_path.exists() else ' (absent — will be created)'}"
    )
    print_report(rep)

    if args.command == "check":
        if rep.missing:
            print(
                f"reconcile-settings: {rep.missing} template entr"
                f"{'y' if rep.missing == 1 else 'ies'} missing — run `apply`"
            )
            return EXIT_MISSING
        print("reconcile-settings: in sync")
        return EXIT_OK

    if args.command == "diff":
        diff = list(
            difflib.unified_diff(
                before.splitlines(keepends=True),
                after.splitlines(keepends=True),
                fromfile=rel(local_path, main_root),
                tofile=rel(local_path, main_root) + " (reconciled)",
            )
        )
        sys.stdout.writelines(diff)
        return EXIT_MISSING if diff else EXIT_OK

    # apply
    if before == after:
        print("reconcile-settings: nothing to do")
        return EXIT_OK
    if not args.stage:
        try:
            write_text(local_path, after)
        except OSError as exc:
            print(
                f"reconcile-settings: write to {rel(local_path, main_root)} refused "
                f"({exc.strerror}); staging instead",
                file=sys.stderr,
            )
        else:
            print(f"reconcile-settings: wrote {rel(local_path, main_root)}")
            return EXIT_OK
    try:
        write_text(stage_path, after)
    except OSError as exc:
        print(f"reconcile-settings: error: {stage_path}: {exc.strerror}", file=sys.stderr)
        return EXIT_FILE
    print(f"reconcile-settings: staged {rel(stage_path, stage_root)} — operator runs:")
    print(CP_LINE)
    if Path.cwd().resolve() != stage_root.resolve():
        print(f"  (from {stage_root})")
    return EXIT_STAGED


if __name__ == "__main__":
    sys.exit(main())
