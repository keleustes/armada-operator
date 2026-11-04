"""Which clone am I in, and what is it — `project_root` / `meta_root` / stack detection.

Every verb answered this for itself, and they disagreed: one tested the directory
name, another the origin URL, a third both. A verb that guesses wrong writes into the
wrong repository, which is what Guardrail 4 exists to prevent.
"""

from __future__ import annotations

import re
from pathlib import Path

from . import git
from .io import die

STACK_MARKERS: dict[str, str | tuple[str, ...]] = {
    "go": "go.mod",
    "python": "pyproject.toml",
    "node": "package.json",
    "xcode": "xcode/project.yml",
    # A crate at the root, or in any top-level folder: rust/ when scaffolded, but the fleet
    # already has rust-blinkt/ beside go-blinkt/ (spec rust-stack). Globs, unlike the rest.
    "rust": ("Cargo.toml", "*/Cargo.toml"),
    # A Maven project at the root (iac-telco-networks, nrm-models) or in any top-level folder:
    # java/ when scaffolded, as in iac-models (spec java-stack).
    "java": ("pom.xml", "*/pom.xml"),
}

# A ci.yml job belongs to a stack when it USES that toolchain, not when it mentions it.
# `go\.mod` was decisive, so a comment naming the file claimed the job — and the one
# stack-agnostic job in the shipped ci.yml was reported as go-only (#288). One table for
# every verb: init and update each kept their own, and the two had already diverged.
STACK_HINTS = {
    # docker-buildx-check: the image-check job builds the images that only image-producing
    # stacks ship (spec container-image), so a stack without one sees it as foreign.
    "go": re.compile(
        r"setup-go|go-version-file|golangci|\bgo (?:build|test|vet|mod|run)\b|docker-buildx-check",
        re.I,
    ),
    "python": re.compile(r"setup-uv|setup-python|pyproject|pytest", re.I),
    "node": re.compile(r"setup-node|package\.json|npm |pnpm ", re.I),
    "xcode": re.compile(r"xcodegen|xcodebuild|runs-on:\s*macos", re.I),
    "rust": re.compile(
        r"rust-cache|cargo-deny|\bcargo (?:build|test|clippy|fmt)\b|docker-buildx-check", re.I
    ),
    "java": re.compile(r"setup-java|\bmvnw?\b", re.I),
}
JOB_RE = re.compile(r"^  (?P<job>[A-Za-z0-9_-]+):\s*$")
NEEDS_RE = re.compile(r"^\s*needs:\s*(?P<needs>.+?)\s*$")
COMMENT_OR_BLANK = re.compile(r"^\s*(?:#.*)?$")
META_REPO_NAME = "claude-meta"


def toplevel(start: Path | None = None) -> Path:
    """The git root containing `start` (default: cwd). Exits if there is none."""
    top = git.probe(start or Path.cwd(), "rev-parse", "--show-toplevel")
    if not top:
        die("not a git repository")
    return Path(top)


def origin_url(root: Path) -> str:
    """The origin remote, or "" when there is none — a fresh clone is not an error here."""
    return git.probe(root, "remote", "get-url", "origin") or ""


def is_meta_repo(root: Path) -> bool:
    """Is this a claude-meta clone, canonical or fork?

    Both conditions, deliberately: a project may be *named* claude-meta-something, and
    a meta clone may sit in a renamed directory. Requiring both was the behaviour that
    survived review; either alone produced a false positive in the fleet.
    """
    return META_REPO_NAME in origin_url(root) and root.name == META_REPO_NAME


def is_canonical(root: Path) -> bool:
    """Canonical has no `upstream` remote; a fork does. The manifests follow from this."""
    return is_meta_repo(root) and git.probe(root, "remote", "get-url", "upstream") is None


def stacks(root: Path) -> list[str]:
    """Which toolchains this repo actually has, by marker file."""
    return sorted(name for name, marker in STACK_MARKERS.items() if _has_marker(root, marker))


def _has_marker(root: Path, marker: str | tuple[str, ...]) -> bool:
    patterns = (marker,) if isinstance(marker, str) else marker
    return any(p.is_file() for pattern in patterns for p in root.glob(pattern))


def job_body(lines: list[str], start: int, end: int) -> str:
    """A job's own lines, minus trailing blanks and comments introducing the NEXT job.

    The body used to run to the next job header, so the section comment
    `# Go / operator jobs — gated on go.mod presence` fell inside `secret-scan` and the
    go hint matched the literal `go.mod`. A python project was told to delete the one
    stack-agnostic job in the file, invisibly: CI stays green, because the job that
    would have failed is gone (#288).
    """
    last = end
    while last > start and COMMENT_OR_BLANK.match(lines[last - 1]):
        last -= 1
    return "\n".join(lines[start:last])


def foreign_ci_jobs(text: str, have: set[str]) -> list[dict] | None:
    """The ci.yml jobs that belong only to stacks this project does not have.

    A job is foreign when the toolchains it uses are disjoint from `have` — so in a
    `python+xcode` project neither the python jobs nor the xcode job is. A job another
    job `needs:` is load-bearing regardless: `detect` is python-flavoured and every go
    job needs it. Returns None when the file has no `jobs:` block.
    """
    lines = text.splitlines()
    # Only the `jobs:` block holds jobs. Scanning the whole file matched the `on:`
    # triggers too, so `push:` was reported as a job and offered for trimming.
    jobs_at = next((i for i, ln in enumerate(lines) if ln.rstrip() == "jobs:"), None)
    if jobs_at is None:
        return None
    jobs_end = next(
        (i for i in range(jobs_at + 1, len(lines)) if lines[i][:1] not in ("", " ", "#")),
        len(lines),
    )
    bounds: list[tuple[str, int, int]] = []
    for i in range(jobs_at + 1, jobs_end):
        if m := JOB_RE.match(lines[i]):
            if bounds:
                bounds[-1] = (bounds[-1][0], bounds[-1][1], i)
            bounds.append((m["job"], i, jobs_end))
    depended_on: set[str] = set()
    for ln in lines[jobs_at:jobs_end]:
        if m := NEEDS_RE.match(ln):
            depended_on.update(n for n in (p.strip(" []'\"") for p in m["needs"].split(",")) if n)
    foreign = []
    for job, start, end in bounds:
        owners = {s for s, rx in STACK_HINTS.items() if rx.search(job_body(lines, start, end))}
        if owners and owners.isdisjoint(have) and job not in depended_on:
            foreign.append({"job": job, "line": start + 1, "stacks": sorted(owners)})
    return foreign


def require_project(root: Path | None = None) -> Path:
    """The project root, refusing on a meta clone.

    Guardrail 4: meta broadcasts, it never applies a delivery into a project — not even
    by driving the project's own verb from the meta side.
    """
    root = root or toplevel()
    if is_meta_repo(root):
        die(
            "this is the claude-meta clone — the consumer half runs in the PROJECT's own "
            "session (Guardrail 4). Meta stages; it never applies."
        )
    return root


def require_meta(root: Path | None = None) -> Path:
    """The meta root, refusing anywhere else."""
    root = root or toplevel()
    if not is_meta_repo(root):
        die("this verb runs in a claude-meta clone; this is not one")
    return root
