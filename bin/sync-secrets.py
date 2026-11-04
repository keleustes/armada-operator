#!/usr/bin/env python3
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""sync-secrets.py — keep a project's secret stores in step: Keychain → GitHub.

A project's secrets live in ONE source of truth, the macOS Keychain (service
`com.<ghhandle>.<project>`, written by `bin/set-secret.sh`, keys named by
`.env.example`). GitHub holds projections of it in TWO separate stores that
nothing keeps in sync for you (spec `private-repo-free-org`):

  actions     — read by workflow runs triggered by a push or a PR
  dependabot  — the ONLY store a Dependabot-triggered run can read; a token set in
                `actions` alone leaves every Dependabot PR red on the same step
                that is green on yours

  uv run --script bin/sync-secrets.py list                       # KEY x keychain/actions/dependabot, names only
  uv run --script bin/sync-secrets.py check [--app both]         # exit 1 when a Keychain key is missing from GitHub
  uv run --script bin/sync-secrets.py push KEY [KEY…] [--app both]   # dry-run: says what it would push
  uv run --script bin/sync-secrets.py push KEY --apply           # Keychain → `gh secret set`, value over stdin
  python3 bin/sync-secrets.py … works too on Python 3.14+ (no uv needed)

`--app actions|dependabot|both` (default `actions`) picks the GitHub store(s) for
`check` and `push`. A key whose `.env.example` description mentions `dependabot`
defaults to `both` — mark the private-deps token that way once and forget it.
`--repo OWNER/REPO` overrides the origin remote; `--service` overrides the
Keychain service; `--env-file` overrides `.env.example`.

Never prints, logs or passes a value on a command line: presence is read with
`security find-generic-password` (no `-w`) and `gh secret list`; a value crosses
only from `security … -w` into `gh secret set`'s stdin, in `push --apply`.

Exit 0 in sync / done · 1 drift or a refused push · 2 usage, tool or file error.
Companion to `bin/set-secret.sh` (writes the Keychain) — this script never does.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

APPS = ("actions", "dependabot")
EXIT_OK = 0
EXIT_DRIFT = 1
EXIT_ERROR = 2


class ToolError(Exception):
    pass


# --- repo, service, keys -------------------------------------------------------


def run(
    cmd: list[str], *, input_text: str | None = None, cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            cmd,
            input=input_text,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise ToolError(f"cannot run {cmd[0]}: {exc}") from exc


def repo_toplevel() -> Path:
    done = run(["git", "rev-parse", "--show-toplevel"])
    if done.returncode != 0:
        return Path.cwd()
    return Path(done.stdout.strip())


def main_checkout(toplevel: Path) -> Path:
    """The main checkout's root — what set-secret.sh names the service after.

    In a worktree session `--show-toplevel` is the worktree; the Keychain service
    was written from the main clone (`com.<ghhandle>.<its basename>`), so derive
    the same name from `--git-common-dir`'s parent.
    """
    done = run(["git", "rev-parse", "--git-common-dir"], cwd=toplevel)
    if done.returncode != 0:
        return toplevel
    common = Path(done.stdout.strip())
    if not common.is_absolute():
        common = toplevel / common
    return common.resolve().parent


def origin_owner_repo(toplevel: Path) -> tuple[str, str] | None:
    done = run(["git", "remote", "get-url", "origin"], cwd=toplevel)
    if done.returncode != 0:
        return None
    url = done.stdout.strip()
    match = re.search(r"[:/]([^/:]+)/([^/]+?)(?:\.git)?/?$", url)
    if not match:
        return None
    return match.group(1), match.group(2)


def env_keys(env_file: Path) -> dict[str, str]:
    """KEY → description, in file order. Same grammar as set-secret.sh."""
    keys: dict[str, str] = {}
    for line in env_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, sep, rest = stripped.partition("=")
        key = key.strip()
        if not sep or not key:
            continue
        keys[key] = rest.strip()
    return keys


# --- the stores ------------------------------------------------------------------


def keychain_has(service: str, key: str) -> bool:
    done = run(["security", "find-generic-password", "-s", service, "-a", key])
    return done.returncode == 0


def keychain_value(service: str, key: str) -> str:
    done = run(["security", "find-generic-password", "-s", service, "-a", key, "-w"])
    if done.returncode != 0:
        raise ToolError(f"{key}: not in Keychain service {service}")
    return done.stdout.rstrip("\n")


def gh_names(repo: str, app: str) -> set[str]:
    done = run(["gh", "secret", "list", "--repo", repo, "--app", app, "--json", "name"])
    if done.returncode != 0:
        raise ToolError(f"gh secret list --app {app} failed: {done.stderr.strip()}")
    try:
        return {row["name"] for row in json.loads(done.stdout or "[]")}
    except (ValueError, KeyError, TypeError) as exc:
        raise ToolError(f"gh secret list --app {app}: unreadable output ({exc})") from exc


def gh_set(repo: str, app: str, key: str, value: str) -> None:
    done = run(["gh", "secret", "set", key, "--repo", repo, "--app", app], input_text=value)
    if done.returncode != 0:
        raise ToolError(f"gh secret set {key} --app {app} failed: {done.stderr.strip()}")


def apps_for(key: str, description: str, chosen: str | None) -> tuple[str, ...]:
    if chosen == "both":
        return APPS
    if chosen in APPS:
        return (chosen,)
    if "dependabot" in description.lower():
        return APPS
    return ("actions",)


# --- commands ------------------------------------------------------------------------


def render_table(keys: dict[str, str], service: str, present: dict[str, set[str]]) -> list[str]:
    width = max((len(k) for k in keys), default=3)
    lines = [f"{'KEY'.ljust(width)}  keychain  actions  dependabot"]
    for key in keys:
        cells = [
            "set" if keychain_has(service, key) else "-",
            "set" if key in present["actions"] else "-",
            "set" if key in present["dependabot"] else "-",
        ]
        lines.append(f"{key.ljust(width)}  {cells[0]:<8}  {cells[1]:<7}  {cells[2]}")
    return lines


def cmd_list(keys: dict[str, str], service: str, repo: str) -> int:
    present = {app: gh_names(repo, app) for app in APPS}
    for line in render_table(keys, service, present):
        print(line)
    extra = (present["actions"] | present["dependabot"]) - set(keys)
    if extra:
        print(f"WARN on GitHub but not in .env.example: {', '.join(sorted(extra))}")
    return EXIT_OK


def cmd_check(keys: dict[str, str], service: str, repo: str, chosen: str | None) -> int:
    present = {app: gh_names(repo, app) for app in APPS}
    drift = False
    for key, description in keys.items():
        in_keychain = keychain_has(service, key)
        wanted = apps_for(key, description, chosen)
        if not in_keychain:
            print(f"MISSING {key}: not in Keychain ({service}) — bin/set-secret.sh {key}")
            drift = True
            continue
        missing = [app for app in wanted if key not in present[app]]
        if missing:
            print(
                f"DRIFT {key}: in Keychain, not in {', '.join(missing)} — bin/sync-secrets.py push {key} --apply"
            )
            drift = True
        else:
            print(f"ok {key}: keychain + {'+'.join(wanted)}")
    return EXIT_DRIFT if drift else EXIT_OK


def cmd_push(
    keys: dict[str, str], names: list[str], service: str, repo: str, chosen: str | None, apply: bool
) -> int:
    targets = list(keys) if names == ["--all"] else names
    unknown = [n for n in targets if n not in keys]
    if unknown:
        print(f"sync-secrets: not declared in .env.example: {', '.join(unknown)}", file=sys.stderr)
        return EXIT_ERROR
    status = EXIT_OK
    for key in targets:
        wanted = apps_for(key, keys[key], chosen)
        if not keychain_has(service, key):
            print(f"REFUSED {key}: not in Keychain ({service}) — bin/set-secret.sh {key} first")
            status = EXIT_DRIFT
            continue
        if not apply:
            print(f"would push {key} → {', '.join(wanted)} ({repo}); add --apply")
            continue
        value = keychain_value(service, key)
        for app in wanted:
            gh_set(repo, app, key, value)
            print(f"pushed {key} → {app} ({repo})")
    if not apply:
        print("dry-run: nothing pushed")
    return status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sync-secrets.py",
        description="Keychain → GitHub Actions / Dependabot secret stores (names only; values never shown).",
    )
    parser.add_argument("command", choices=("list", "check", "push"))
    parser.add_argument("names", nargs="*", help="push: KEY … or --all")
    parser.add_argument("--repo", help="OWNER/REPO (default: the origin remote)")
    parser.add_argument("--service", help="Keychain service (default: com.<ghhandle>.<project>)")
    parser.add_argument("--env-file", help="key list (default: <toplevel>/.env.example)")
    parser.add_argument(
        "--app",
        choices=(*APPS, "both"),
        help="GitHub store(s) for check/push (default: actions; both for keys whose description says dependabot)",
    )
    parser.add_argument("--apply", action="store_true", help="push: really call gh secret set")
    args = parser.parse_args(argv)

    if args.command != "push" and args.names:
        parser.error(f"{args.command} takes no KEY arguments")
    if args.command == "push" and not args.names:
        parser.error("push needs KEY … or --all")

    toplevel = repo_toplevel()
    owner_repo = origin_owner_repo(toplevel)
    repo = args.repo or (f"{owner_repo[0]}/{owner_repo[1]}" if owner_repo else None)
    if not repo:
        print("sync-secrets: no origin remote; pass --repo OWNER/REPO", file=sys.stderr)
        return EXIT_ERROR
    ghhandle = repo.split("/", 1)[0]
    service = args.service or f"com.{ghhandle}.{main_checkout(toplevel).name}"
    env_file = Path(args.env_file) if args.env_file else toplevel / ".env.example"
    if not env_file.is_file():
        print(f"sync-secrets: {env_file} not found", file=sys.stderr)
        return EXIT_ERROR

    try:
        keys = env_keys(env_file)
        print(f"repo {repo} · keychain service {service} · keys from {env_file}", file=sys.stderr)
        if not keys:
            print("sync-secrets: no keys declared in .env.example")
            return EXIT_OK
        if args.command == "list":
            return cmd_list(keys, service, repo)
        if args.command == "check":
            return cmd_check(keys, service, repo, args.app)
        return cmd_push(keys, args.names, service, repo, args.app, args.apply)
    except (OSError, ToolError) as exc:
        print(f"sync-secrets: {exc}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
