#!/usr/bin/env python3
# /// script
# requires-python = ">=3.14"
# dependencies = ["pyyaml>=6"]
# ///
"""Read-only structural audit of Codex documents, skills, and plugin resources.

ADOPTED VERBATIM from cloudison/photo-common, which wrote it against a real Codex port —
the only repo in the fleet that had one. It is not generated from `plugins/alemax/src/`
like the entry points beside it; it is a harness-specific asset, and it lives under
`templates/codex/scripts/` for that reason.

Two things it is NOT. It was written against **alemax 2.0**, so what it checks may lag what
this repo now renders. And unlike every other shipped script it declares a dependency
(`pyyaml`) in its PEP 723 header rather than being stdlib-only — that is fine for a leaf
script, which `uv run --script` resolves on its own, but it means this one verb cannot run
offline with a cold cache.

It was missing from the 2026-09-09 delivery: the Codex `lint-all` body named it and the
render shipped `claude_lint.py` beside it instead, because the body came from photo-common
and the entry points came from ENTRY_POINTS, and nothing checked the two agreed. A test now
does (`test_every_script_a_shipped_body_names_is_shipped`).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

import yaml

HELPER = re.compile(r"\$\{ALEMAX_SKILLS\}/([a-z0-9-]+/scripts/[\w.-]+)")
LINK = re.compile(r'(?<!!)\[[^\]]+\]\(([^\s)]+)(?:\s+"[^"]*")?\)')


def local_links(path: Path) -> list[str]:
    findings = []
    for link in LINK.findall(path.read_text()):
        if re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*:", link) or link.startswith(("#", "/")):
            continue
        target = link.split("#", 1)[0]
        if target and not (path.parent / target).exists():
            findings.append(f"{path}: missing local link {target}")
    return findings


def audit(repo: Path, verb: str) -> list[str]:
    findings: list[str] = []
    if verb in ("all", "docs"):
        docs = [repo / "AGENTS.md", repo / "README.md"]
        architecture = next(
            (repo / n for n in ("ARCHITECTURE.md", "architecture.md") if (repo / n).is_file()), None
        )
        if architecture:
            docs.append(architecture)
        else:
            findings.append(f"{repo}: missing architecture document")
        for doc in docs:
            if not doc.is_file():
                findings.append(f"{doc}: missing document")
            else:
                findings.extend(local_links(doc))
    if verb not in ("all", "skills"):
        return findings
    entries = list((repo / ".agents/skills").glob("*"))
    plugin_roots = set()
    manifests = sorted((repo / "plugins").glob("*/.codex-plugin/plugin.json"))
    # Also audit a standalone relocated plugin.
    if (repo / ".codex-plugin/plugin.json").is_file():
        manifests.append(repo / ".codex-plugin/plugin.json")
    for manifest in manifests:
        plugin_root = manifest.parent.parent.resolve()
        plugin_roots.add(plugin_root)
        try:
            data = json.loads(manifest.read_text())
            if not isinstance(data, dict) or data.get("name") != plugin_root.name:
                findings.append(f"{manifest}: plugin name must match its directory")
            skills = data.get("skills", "./skills/")
            if not isinstance(skills, str):
                raise ValueError("skills must be a relative path")
            skill_root = (plugin_root / skills).resolve()
            if not skill_root.is_relative_to(plugin_root) or not skill_root.is_dir():
                raise ValueError("skill directory missing or outside plugin")
            entries.extend(skill_root.glob("*"))
            if not list(skill_root.glob("*/SKILL.md")):
                findings.append(f"{manifest}: no skills found")
        except (OSError, ValueError, AttributeError) as exc:
            findings.append(f"{manifest}: invalid manifest: {exc}")
    seen_paths: set[Path] = set()
    names: dict[str, Path] = {}
    for entry in sorted(entries):
        path = entry / "SKILL.md"
        if not path.is_file():
            findings.append(f"{entry}: missing SKILL.md or broken link")
            continue
        path = path.resolve()
        if path in seen_paths:
            continue
        seen_paths.add(path)
        text = path.read_text()
        match = re.match(r"\A---\n(.*?)\n---(?:\n|$)", text, re.S)
        try:
            data = yaml.safe_load(match[1]) if match else None
            if not isinstance(data, dict):
                raise ValueError("missing YAML mapping frontmatter")
            name = data.get("name")
            if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
                raise ValueError("invalid skill name")
            if len(name) > 64 or name != path.parent.name:
                raise ValueError("name must match directory and be at most 64 characters")
            if not isinstance(data.get("description"), str) or not data["description"].strip():
                raise ValueError("missing description")
            if name in names:
                findings.append(f"{path}: duplicate name {name} also at {names[name]}")
            names[name] = path
            for key in ("context", "argument-hint", "allowed-tools"):
                if key in data:
                    findings.append(f"{path}: unconverted Claude frontmatter {key}")
        except (yaml.YAMLError, ValueError) as exc:
            findings.append(f"{path}: {exc}")
        for helper in HELPER.findall(text):
            target = path.parent.parent / helper
            if not target.is_file():
                findings.append(f"{path}: missing helper {helper}")
            owner = next((p for p in plugin_roots if path.is_relative_to(p)), None)
            if owner and not target.resolve().is_relative_to(owner):
                findings.append(f"{path}: helper escapes plugin {helper}")
        findings.extend(local_links(path))
    if not seen_paths:
        findings.append(f"{repo}: no Codex skills found")
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("verb", choices=("docs", "skills", "all"))
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()
    repo = args.repo
    if repo is None:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=False
        )
        repo = Path(result.stdout.strip()) if result.returncode == 0 else Path.cwd()
    repo = repo.resolve()
    if args.list:
        print(
            f"{args.verb}: Codex documents, skill discovery and resource references as applicable in {repo}"
        )
        return 0
    findings = audit(repo, args.verb)
    for finding in findings:
        print(finding)
    print(
        f"codex_lint {args.verb}: {len(findings)} finding(s)"
        + (" (strict)" if args.strict else " (advisory)")
    )
    return int(args.strict and bool(findings))


if __name__ == "__main__":
    raise SystemExit(main())
