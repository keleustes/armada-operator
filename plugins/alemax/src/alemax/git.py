"""Running git — the `def git(` that was copied into 12 of 14 scripts.

The copied version returned "" on any non-zero exit, which made "the command failed"
and "the result is empty" the same value. That is the defect #286 fixed in one verb;
every other copy still had it. Both forms exist here, named for what they mean, and
the checked one is the default a verb should reach for.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from .io import die


class GitError(RuntimeError):
    """A git invocation failed. Carries the command and stderr for the caller to report."""

    def __init__(self, args: tuple[str, ...], stderr: str, returncode: int):
        self.args_run = args
        self.stderr = stderr
        self.returncode = returncode
        super().__init__(f"git {' '.join(args)} failed ({returncode}): {stderr or 'no output'}")


def run(root: Path | str, *args: str) -> str:
    """git, raising GitError on failure. The default: a failure is not an empty string."""
    done = subprocess.run(
        ["git", *args], cwd=str(root), capture_output=True, text=True, check=False
    )
    if done.returncode != 0:
        raise GitError(args, done.stderr.strip(), done.returncode)
    return done.stdout.strip()


def checked(root: Path | str, *args: str) -> str:
    """git, exiting the process on failure. For a verb with nothing useful to say."""
    try:
        return run(root, *args)
    except GitError as exc:
        die(str(exc))


def probe(root: Path | str, *args: str) -> str | None:
    """git, returning None on failure.

    Use ONLY where failure and emptiness genuinely mean the same thing to the caller —
    and say so at the call site. `None` rather than `""` so the difference survives.
    """
    try:
        return run(root, *args)
    except GitError:
        return None


def lines(root: Path | str, *args: str) -> list[str]:
    """Checked git, split into non-empty lines. The shape most callers actually wanted."""
    return [ln for ln in checked(root, *args).splitlines() if ln]


def tracked(root: Path | str, *pathspec: str) -> set[str]:
    """Paths git tracks under `pathspec`."""
    return set(lines(root, "ls-files", "--", *pathspec))


def untracked(root: Path | str, *pathspec: str) -> set[str]:
    """Paths git does not track under `pathspec`, honouring .gitignore.

    A delivery arrives untracked on a project's first update, so a check that reads
    only the index cannot see the state it exists to handle (#286, defect 2).
    """
    return set(lines(root, "ls-files", "--others", "--exclude-standard", "--", *pathspec))
