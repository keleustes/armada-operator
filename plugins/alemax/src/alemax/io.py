"""Process exit and output — the `die` that was copied into 12 of 14 scripts.

Exit codes are a contract shared by every verb, and were previously re-invented per
script: 3 meant "several refs" in one and "nothing to trim" in another. Naming them
once is the point.
"""

from __future__ import annotations

import json
import sys
from typing import Any, NoReturn

OK = 0
"""Nothing to do, or the thing asked for is already true."""

ERROR = 1
"""The verb cannot proceed: wrong clone, incomplete state, a failed command."""

AMBIGUOUS = 2
"""Several candidates; the operator picks. Never resolved automatically."""

FOUND = 3
"""Something to act on. Not a failure — the verb has work to report."""


def die(msg: str, code: int = ERROR) -> NoReturn:
    """Stop with a message on stderr. Always prefixed, never silent."""
    print(f"alemax: {msg}", file=sys.stderr)
    raise SystemExit(code)


def emit(payload: dict[str, Any], *, as_json: bool, plain: str | None = None) -> None:
    """One place deciding machine-readable vs human output.

    Every verb grew its own `if a.json:` branch, and they drifted: some printed the
    payload and returned, some printed and fell through to the human lines as well.
    """
    if as_json:
        print(json.dumps(payload, indent=2))
    elif plain is not None:
        print(plain)
