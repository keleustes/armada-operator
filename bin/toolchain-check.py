#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""toolchain-check.py — every language version this repo declares, against the minimum.

Spec `toolchain-versions`. claude-meta holds itself and every project to a minimum Python,
Go and Java, and asks every Rust crate to pin its toolchain. This lists each declaration the
repo tracks — wherever it sits, so a project with `go/`, `python/`, `java/` and `rust/`
folders is read in full — with the version it declares and the minimum, and reports each
one below the minimum with the edit that fixes it. It never edits anything: a project's
versions are that project's to move (`/alemax:complete-update` relays this report).

What it reads (`git ls-files`, so `.venv/`, `target/` and other untracked trees are out):

  pyproject.toml     `[project] requires-python` lower bound · `[tool.ruff] target-version`
  ruff.toml          `target-version` (also `.ruff.toml`)
  .python-version    the first line
  *.py               an inline `# requires-python` script header
  go.mod             the `go` directive
  pom.xml            `maven.compiler.release`, else the compiler plugin's `<release>`,
                     else `<target>`; a pom that sets none inherits, and is not a finding
  Cargo.toml         the outermost crate or workspace in a folder tree; pinned when a
                     `rust-toolchain.toml` (or `rust-toolchain`) sits in its folder or above
  .golangci.yml      `version: "2"` at top level (also `.golangci.yaml`)

Findings (warnings by default; `--strict` promotes every one to a refusal):

  T1  Python below the minimum (requires-python, .python-version, a script header)
  T2  Go below the minimum
  T3  Java below the minimum
  T4  ruff target-version below the Python minimum — the Python meta delivers uses
      syntax that ruff rejects under an older target
  T5  a Rust crate with no rust-toolchain.toml
  T6  a .golangci.yml in the v1 schema, which golangci-lint v2 refuses

MINIMUM is the one machine-readable copy of the spec's table; a claude-meta test fails
when the two differ. Move both in the same change.

Usage:
  uv run --script bin/toolchain-check.py                 # report; exit 0 unless --strict finds
  uv run --script bin/toolchain-check.py --strict        # every finding refuses, exit 1
  uv run --script bin/toolchain-check.py --json          # declarations and findings
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tomllib
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

# The spec's table, minimum column. Rust has no minimum beyond a pin (None).
MINIMUM: dict[str, str | None] = {
    "python": "3.14",
    "go": "1.26",
    "java": "25",
    "rust": None,
}

SCRIPT_HEADER_RE = re.compile(r"^#\s*requires-python\s*=\s*[\"']([^\"']+)[\"']", re.M)
LOWER_BOUND_RE = re.compile(r"(>=|~=|==|>)\s*(\d+(?:\.\d+)*)")
VERSION_RE = re.compile(r"(\d+)\.(\d+)")
GO_DIRECTIVE_RE = re.compile(r"^go\s+(\d+\.\d+(?:\.\d+)?)\s*$", re.M)
GOLANGCI_V2_RE = re.compile(r"""^version:\s*["']?2(?:["']|\s|$)""", re.M)
RUFF_TARGET_RE = re.compile(r"^py(\d)(\d+)$")


@dataclass
class Decl:
    stack: str  # python | go | java | rust | ruff | golangci
    path: str  # repo-relative, POSIX
    what: str  # the field read, e.g. "requires-python"
    value: str  # as declared
    minimum: str  # as shown
    ok: bool
    code: str = ""
    fix: str = ""


def as_tuple(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", v))


def at_least(value: str, minimum: str) -> bool:
    got, want = as_tuple(value), as_tuple(minimum)
    return got[: len(want)] >= want


def tracked_files(repo: Path) -> list[str]:
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "ls-files", "-z"],
            capture_output=True,
            check=True,
        ).stdout
        return [p for p in out.decode("utf-8", "replace").split("\0") if p]
    except OSError, subprocess.CalledProcessError:
        skip = {".git", ".venv", "venv", "node_modules", "target", "__pycache__"}
        found = []
        for root, dirs, files in os.walk(repo):
            dirs[:] = [d for d in dirs if d not in skip]
            for f in files:
                found.append(Path(root, f).relative_to(repo).as_posix())
        return found


def lower_bound(spec: str) -> str | None:
    bounds = [m.group(2) for m in LOWER_BOUND_RE.finditer(spec) if m.group(1) != ">"]
    return max(bounds, key=as_tuple) if bounds else None


# --- python ----------------------------------------------------------------------------


def python_decl(rel: str, what: str, value: str) -> Decl:
    want = MINIMUM["python"] or ""
    ok = at_least(value, want)
    fix = "" if ok else f"raise {what} to {want}, then `uv lock` where a lockfile exists"
    return Decl("python", rel, what, value, want, ok, "" if ok else "T1", fix)


def ruff_decl(rel: str, target: str) -> Decl | None:
    m = RUFF_TARGET_RE.match(target.strip())
    if not m:
        return None
    value = f"{m.group(1)}.{m.group(2)}"
    want = MINIMUM["python"] or ""
    ok = at_least(value, want)
    wanted = "py" + want.replace(".", "")
    fix = "" if ok else f'set target-version = "{wanted}" (delivered Python uses {want} syntax)'
    return Decl("ruff", rel, "target-version", target, wanted, ok, "" if ok else "T4", fix)


def read_pyproject(repo: Path, rel: str) -> list[Decl]:
    try:
        data = tomllib.loads((repo / rel).read_text(encoding="utf-8"))
    except OSError, tomllib.TOMLDecodeError:
        return []
    out = []
    if (spec := data.get("project", {}).get("requires-python")) and (lb := lower_bound(spec)):
        out.append(python_decl(rel, "requires-python", f">={lb}"))
    if (target := data.get("tool", {}).get("ruff", {}).get("target-version")) and (
        d := ruff_decl(rel, target)
    ):
        out.append(d)
    return out


def read_ruff_toml(repo: Path, rel: str) -> list[Decl]:
    try:
        data = tomllib.loads((repo / rel).read_text(encoding="utf-8"))
    except OSError, tomllib.TOMLDecodeError:
        return []
    if (target := data.get("target-version")) and (d := ruff_decl(rel, target)):
        return [d]
    return []


def read_python_version(repo: Path, rel: str) -> list[Decl]:
    try:
        lines = (repo / rel).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in lines:
        line = line.strip()
        if line and not line.startswith("#") and (m := VERSION_RE.search(line)):
            return [python_decl(rel, ".python-version", f"{m.group(1)}.{m.group(2)}")]
    return []


def read_script_header(repo: Path, rel: str) -> list[Decl]:
    try:
        with (repo / rel).open(encoding="utf-8", errors="replace") as fh:
            head = "".join(fh.readline() for _ in range(40))
    except OSError:
        return []
    if "# /// script" not in head or not (m := SCRIPT_HEADER_RE.search(head)):
        return []
    if not (lb := lower_bound(m.group(1))):
        return []
    return [python_decl(rel, "script requires-python", f">={lb}")]


# --- go --------------------------------------------------------------------------------


def read_go_mod(repo: Path, rel: str) -> list[Decl]:
    try:
        m = GO_DIRECTIVE_RE.search((repo / rel).read_text(encoding="utf-8"))
    except OSError:
        return []
    if not m:
        return []
    want = MINIMUM["go"] or ""
    ok = at_least(m.group(1), want)
    fix = "" if ok else f"go mod edit -go={want}.<newest patch>, then go mod tidy"
    return [Decl("go", rel, "go", m.group(1), want, ok, "" if ok else "T2", fix)]


def read_golangci(repo: Path, rel: str) -> list[Decl]:
    try:
        text = (repo / rel).read_text(encoding="utf-8")
    except OSError:
        return []
    ok = bool(GOLANGCI_V2_RE.search(text))
    fix = "" if ok else "golangci-lint migrate (golangci-lint v2 refuses a v1 config)"
    return [
        Decl("golangci", rel, "schema", "v2" if ok else "v1", "v2", ok, "" if ok else "T6", fix)
    ]


# --- java ------------------------------------------------------------------------------


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child(el: ET.Element | None, name: str) -> ET.Element | None:
    if el is None:
        return None
    return next((c for c in el if _local(c.tag) == name), None)


def java_release(root: ET.Element) -> tuple[str, str] | None:
    found = _child(root, "properties")
    props = {_local(c.tag): (c.text or "").strip() for c in (found if found is not None else [])}

    def resolve(v: str) -> str:
        m = re.fullmatch(r"\$\{([^}]+)\}", v)
        return props.get(m.group(1), v) if m else v

    for key in ("maven.compiler.release",):
        if props.get(key):
            return key, resolve(props[key])
    build_plugins = _child(_child(root, "build"), "plugins")
    for plugin in build_plugins if build_plugins is not None else []:
        aid = _child(plugin, "artifactId")
        if aid is None or (aid.text or "").strip() != "maven-compiler-plugin":
            continue
        conf = _child(plugin, "configuration")
        for field in ("release", "target"):
            if (el := _child(conf, field)) is not None and (el.text or "").strip():
                return f"compiler {field}", resolve(el.text.strip())
    if props.get("maven.compiler.target"):
        return "maven.compiler.target", resolve(props["maven.compiler.target"])
    return None


def read_pom(repo: Path, rel: str) -> list[Decl]:
    try:
        root = ET.parse(repo / rel).getroot()
    except OSError, ET.ParseError:
        return []
    if not (found := java_release(root)):
        return []
    what, value = found
    value = value.removeprefix("1.") if value.startswith("1.") else value
    if not value.isdigit():
        return []
    want = MINIMUM["java"] or ""
    ok = int(value) >= int(want)
    fix = "" if ok else f"set {what} to {want}, and the CI java-version with it"
    return [Decl("java", rel, what, value, want, ok, "" if ok else "T3", fix)]


# --- rust ------------------------------------------------------------------------------


def read_crates(repo: Path, files: list[str]) -> list[Decl]:
    cargo = sorted(f for f in files if PurePosixPath(f).name == "Cargo.toml")
    pins = {
        str(PurePosixPath(f).parent)
        for f in files
        if PurePosixPath(f).name in ("rust-toolchain.toml", "rust-toolchain")
    }
    outer = []
    for f in cargo:
        parent = PurePosixPath(f).parent
        if not any(PurePosixPath(o).parent in parent.parents for o in outer):
            outer.append(f)
    out = []
    for f in outer:
        folder = PurePosixPath(f).parent
        chain = [folder, *folder.parents]
        pin = next((str(d) for d in chain if str(d) in pins), None)
        if pin is not None:
            channel = read_channel(repo, pin, files)
            out.append(Decl("rust", f, "rust-toolchain", channel, "a pin", True))
        else:
            fix = "add rust-toolchain.toml beside it (one channel, with rustfmt and clippy)"
            out.append(Decl("rust", f, "rust-toolchain", "unpinned", "a pin", False, "T5", fix))
    return out


def read_channel(repo: Path, folder: str, files: list[str]) -> str:
    base = "" if folder == "." else f"{folder}/"
    for name in ("rust-toolchain.toml", "rust-toolchain"):
        if f"{base}{name}" in files:
            try:
                text = (repo / f"{base}{name}").read_text(encoding="utf-8")
            except OSError:
                return "pinned"
            if m := re.search(r"""channel\s*=\s*["']([^"']+)["']""", text):
                return m.group(1)
            return text.strip().splitlines()[0] if text.strip() else "pinned"
    return "pinned"


# --- main ------------------------------------------------------------------------------

READERS = {
    "pyproject.toml": read_pyproject,
    "ruff.toml": read_ruff_toml,
    ".ruff.toml": read_ruff_toml,
    ".python-version": read_python_version,
    "go.mod": read_go_mod,
    "pom.xml": read_pom,
    ".golangci.yml": read_golangci,
    ".golangci.yaml": read_golangci,
}


def collect(repo: Path) -> list[Decl]:
    files = tracked_files(repo)
    decls: list[Decl] = []
    for rel in sorted(files):
        name = PurePosixPath(rel).name
        if reader := READERS.get(name):
            decls.extend(reader(repo, rel))
        elif name.endswith(".py"):
            decls.extend(read_script_header(repo, rel))
    decls.extend(read_crates(repo, files))
    order = {"python": 0, "ruff": 1, "go": 2, "golangci": 3, "java": 4, "rust": 5}
    return sorted(decls, key=lambda d: (order[d.stack], d.path))


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--repo", default=".", help="repo root (default: cwd)")
    ap.add_argument("--strict", action="store_true", help="promote every warning to a refusal")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    decls = collect(repo)
    findings = [d for d in decls if not d.ok]
    refusals = findings if args.strict else []
    warnings = [] if args.strict else findings

    if args.json:
        print(
            json.dumps(
                {
                    "repo": str(repo),
                    "minimum": MINIMUM,
                    "declarations": [d.__dict__ for d in decls],
                    "refusals": len(refusals),
                    "warnings": len(warnings),
                },
                indent=2,
            )
        )
        return 1 if refusals else 0

    print(
        f"toolchain-check: {repo} — {len(decls)} declaration(s); minimum python "
        f"{MINIMUM['python']} · go {MINIMUM['go']} · java {MINIMUM['java']} · rust pinned"
        f"{' [strict]' if args.strict else ''}"
    )
    for d in decls:
        mark = "ok   " if d.ok else "below"
        print(f"  {mark}  {d.stack:<8} {d.path}  {d.what} {d.value}  (minimum {d.minimum})")
    for d in refusals:
        print(f"REFUSE {d.path}: {d.code}: {d.stack} {d.what} {d.value} — fix: {d.fix}")
    for d in warnings:
        print(f"WARN {d.path}: {d.code}: {d.stack} {d.what} {d.value} — fix: {d.fix}")
    print(
        f"toolchain-check: {len(refusals)} refusal(s), {len(warnings)} warning(s) — "
        f"{'FAIL' if refusals else 'pass'}"
    )
    return 1 if refusals else 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    sys.exit(main())
