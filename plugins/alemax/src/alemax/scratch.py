"""`.local/` — the gitignored operator scratch, and the atomic write into it.

Five verbs each carried their own version of "is `.local/` actually ignored here, and
how do I append without losing the file if the write fails". The gitignore check is not
ceremony: `.local/` holds feedback rows, session checkpoints and briefs, and committing
those to a project's history is not recoverable by deleting them later.
"""

from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path

from . import git
from .io import die

LOCAL = ".local"


def local_dir(root: Path, *, write: bool = False) -> Path:
    """`<root>/.local`, refusing to create it where it is not gitignored.

    A `/.local/` pattern only matches once the directory exists, so the check has to
    happen after `mkdir` — and the directory has to be removed again if the check
    fails, or a second run would find it present and conclude it was always fine.
    """
    local = root / LOCAL
    if not write:
        return local
    created = not local.exists()
    local.mkdir(exist_ok=True)
    if git.probe(root, "check-ignore", "-q", LOCAL) is None:
        if created:
            local.rmdir()
        die(
            f"{LOCAL}/ is not gitignored in {root} — add `{LOCAL}/` to .gitignore first; "
            "refusing to write"
        )
    return local


def atomic_write(path: Path, text: str) -> None:
    """Write via a temp file in the same directory, then rename.

    A partial write leaves the operator's accumulated notes truncated, and the failure
    that causes it (a full disk, a read-only mount) is exactly when they matter.
    """
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except OSError as exc:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        die(f"cannot write {path}: {exc}")


def append_block(path: Path, block: str) -> None:
    """Append one block, keeping exactly one blank line between blocks."""
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if existing and not existing.endswith("\n"):
        existing += "\n"
    atomic_write(path, existing + ("\n" if existing else "") + block.rstrip("\n") + "\n")


def one_line(text: str) -> str:
    """Collapse whitespace. A row's shape is line-based; a newline inside one breaks it."""
    return " ".join(text.split())
