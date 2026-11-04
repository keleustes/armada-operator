"""`alemax <verb> <subcommand>` — one surface, so a skill names a command not a path.

A skill body used to name `uv run --script .claude/skills/alemax/skills/<n>/scripts/<f>.py`,
which meant moving an implementation edited nineteen documents.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable

from .verbs import (
    agent,
    broadcast,
    burner,
    collect,
    dependabot,
    diagnose,
    feedback,
    ideas,
    init,
    leaves,
    lint,
    msg,
    newproj,
    presence,
    tidy,
    twin,
    update,
    vault,
)

VERBS: dict[str, Callable[[argparse.ArgumentParser], None]] = {
    "agent": agent.register,
    "broadcast": broadcast.register,
    "burner": burner.register,
    "collect": collect.register,
    "dependabot": dependabot.register,
    "diagnose": diagnose.register,
    "feedback": feedback.register,
    "ideas": ideas.register,
    "init": init.register,
    "leaves": leaves.register,
    "lint": lint.register,
    "msg": msg.register,
    "newproj": newproj.register,
    "presence": presence.register,
    "tidy": tidy.register,
    "twin": twin.register,
    "update": update.register,
    "vault": vault.register,
}


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="alemax", description=__doc__)
    verbs = ap.add_subparsers(dest="verb", required=True, metavar="VERB")
    for name, register in VERBS.items():
        register(verbs.add_parser(name))
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
