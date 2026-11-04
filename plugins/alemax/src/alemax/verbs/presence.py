"""`alemax presence` — a project's Mattermost account is active while a session runs in it.

Spec `mattermost-presence`. Each active
project in the volume's `projects.yaml` has `<volume>-<project>`; an extra named as an address,
`upstream/claude-meta`, has `upstream-claude-meta` — the canonical clone's drive in a send-msg
address, the one prefix that is not a volume. Claude Code's
`SessionStart`/`SessionEnd` hooks run `alemax presence hook`, which marks the account of
the project folder the session runs in as active, and inactive when the last session in
that folder ends.

    provision [--url U] [--team T] [--alias project=short …] [--extra name=path …]
              [--channel NAME] [--projects FILE] [--apply]
                      plan the accounts from projects.yaml; create them only with --apply
    hook              the SessionStart/SessionEnd hook: event JSON on stdin, prints nothing
    status            registered sessions, per account
    check             this volume's setup: what is there, what is missing, how to fix it
    who               live and stale sessions on every volume of this Mac (read-only)
    sweep             drop registrations whose Claude Code process is gone
    listen | roster | post | inbox    the relay and the mailbox — see presence_relay
    install [--meta CLONE] [--dry-run]   add the two hooks to ~/.claude/settings.json;
                                     they run the plugin from the volume's claude-meta clone
    uninstall [--dry-run]            remove exactly those two hooks

State lives under the volume's `$HOME`, outside any repo:
`~/.config/claude-presence/config.json` (server, team, the resolved account map — no
secrets) and `~/.local/state/claude-presence/` (the session registry and the hook log).
Tokens live only in the Keychain, service `claude-presence`, account = Mattermost
username; the operator's admin token is account `admin`. A token is never written to a
file, put in an argument list, printed or logged.

The registry is keyed by Claude Code PROCESS, not session id: `/clear` and `/resume` give
the same process a new session id, and a process is what a sweep can check is alive.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import json
import os
import pwd
import re
import shlex
import shutil
import socket
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..io import ERROR, FOUND, OK, die

SERVICE = "claude-presence"
ADMIN = "admin"
USERNAME_MAX = 22
USERNAME_RE = re.compile(r"^[a-z][a-z0-9._-]{2,21}$")
UPSTREAM = "upstream"  # the canonical clone's drive in a send-msg address; not a volume
TOKEN_RE = re.compile(r"^[a-z0-9]{20,64}$")
HOOK_MARK = "presence hook"
HOOK_TIMEOUT = 10
HTTP_TIMEOUT = 3.0
PROBE_TIMEOUT = 0.8  # one TCP connect before any request: a dead NAS costs this, not N timeouts
START_MATCHER = "startup|resume|clear|compact"
QUIET_END_REASONS = ("clear", "resume")  # the same process carries on
ACTIVE_EMOJI = "large_green_circle"

ENTRY_RE = re.compile(r"^\s+-\s+name:\s*(?P<val>[^#]+?)\s*(?:#.*)?$")
FIELD_RE = re.compile(r"^\s{3,}(?P<key>[a-z_]+):\s*(?P<val>[^#]*?)\s*(?:#.*)?$")


# --- where things live ----------------------------------------------------------------


def config_path(home: Path) -> Path:
    return home / ".config" / SERVICE / "config.json"


def state_dir(home: Path) -> Path:
    return home / ".local" / "state" / SERVICE


def now_utc() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def volume_from_home(home: Path) -> str | None:
    """`/Volumes/IAC01/Users/x` → `iac01`. None off a volume. Shape only, no filesystem."""
    parts = home.parts
    if len(parts) > 2 and parts[1] == "Volumes":
        return parts[2].lower()
    return None


def home_volume_mismatch(cwd: str, home: Path) -> str | None:
    """One clause naming a `$HOME` that is off the working folder's volume, else None.

    The same rule as the `home-volume-check.py` SessionStart hook (spec `session-home-volume`):
    a folder under `/Volumes/<X>` expects `$HOME` under `/Volumes/<X>` too. A wrong `$HOME`
    reads another volume's presence config, so "not provisioned" there is usually this, not a
    missing account.
    """
    here = Path(os.path.realpath(cwd)).parts
    if not (len(here) > 2 and here[1] == "Volumes"):
        return None
    vol = os.path.join(os.sep, "Volumes", here[2])
    real_home = os.path.realpath(home)
    hp = Path(real_home).parts
    if len(hp) > 2 and hp[1] == "Volumes" and hp[2] == here[2]:
        return None
    try:
        user = pwd.getpwuid(os.getuid()).pw_name
    except KeyError:
        user = os.environ.get("USER", "<user>")
    expected = os.path.join(vol, "Users", user)
    return (
        f"$HOME is {real_home}, not on {vol} where this folder is — the likely cause; "
        f"the expected $HOME is {expected} (set HOME, or AIML_VOLUME={vol}, and relaunch). "
    )


def alemax_prefix(meta: str) -> str:
    """How to run the plugin from the volume's claude-meta clone, from ANY folder.

    The hooks fire in every folder, and folders outside the meta system have no
    `plugins/alemax/` of their own, so both run the clone's copy — the same code every
    skill runs, current after every resync. No second installed copy.
    """
    uv = shutil.which("uv") or "uv"
    return (
        f"{shlex.quote(uv)} run --quiet --directory {shlex.quote(meta + '/plugins/alemax')} alemax"
    )


def log(home: Path, line: str) -> None:
    """Best effort. A hook that cannot log must still not fail."""
    with contextlib.suppress(OSError):
        d = state_dir(home)
        d.mkdir(parents=True, exist_ok=True)
        with (d / "hook.log").open("a", encoding="utf-8") as fh:
            fh.write(f"{now_utc()} {line}\n")


# --- projects.yaml and account names -------------------------------------------------


def parse_projects(text: str) -> list[dict[str, str]]:
    """The subset projects.yaml uses: a list of flat scalar fields. Comments skipped."""
    out: list[dict[str, str]] = []
    cur: dict[str, str] | None = None
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            continue
        if m := ENTRY_RE.match(line):
            if cur:
                out.append(cur)
            cur = {"name": m["val"].strip("\"'")}
        elif cur is not None and (m := FIELD_RE.match(line)):
            cur[m["key"]] = m["val"].strip("\"'")
    if cur:
        out.append(cur)
    return out


def derive_username(volume: str, project: str, aliases: dict[str, str]) -> tuple[str | None, str]:
    """(username, "") or (None, why). Never truncates: a clipped name can collide.

    An address-shaped extra, `<drive>/<folder>`, names its own prefix — `upstream/claude-meta`
    is `upstream-claude-meta`, as `alemax presence send` resolves that address. The drive is
    this volume or `upstream`: a volume never provisions another volume's names.
    """
    if "/" in project:
        drive, folder = project.lower().split("/", 1)
        if drive not in (volume, UPSTREAM):
            return None, f"{project!r} names drive {drive!r} — only {volume!r} or {UPSTREAM!r}"
        name = f"{drive}-{aliases.get(project, folder).lower()}"
    else:
        name = f"{volume}-{aliases.get(project, project).lower()}"
    if len(name) > USERNAME_MAX:
        return None, f"{name!r} is {len(name)} characters (max {USERNAME_MAX}) — add --alias"
    if not USERNAME_RE.match(name):
        return None, f"{name!r} has characters Mattermost rejects — add --alias"
    return name, ""


def desired_accounts(
    volume: str, projects: list[dict[str, str]], aliases: dict[str, str]
) -> tuple[list[dict[str, Any]], list[tuple[str, str]]]:
    """One account per active project; and the refused (project, why).

    claude-meta itself is not special: it is never in projects.yaml, so it comes in as
    an extra like any other folder outside the manifest, and gets `<volume>-claude-meta`.
    """
    want: list[dict[str, Any]] = []
    refused: list[tuple[str, str]] = []
    for p in projects:
        if p.get("status") != "active" or not p.get("path"):
            continue
        name, why = derive_username(volume, p["name"], aliases)
        if name is None:
            refused.append((p["name"], why))
            continue
        want.append(
            {
                "username": name,
                "display_name": f"{p['name']} @ {volume.upper()}",
                "project": p["name"],
                "path": p["path"],
            }
        )
    return want, refused


def plan(
    volume: str, want: list[dict[str, Any]], existing: list[dict[str, Any]]
) -> dict[str, list[dict[str, Any]]]:
    """What provisioning would do. Only accounts this volume owns are ever deactivated."""
    by_name = {b["username"]: b for b in existing}
    wanted = {w["username"] for w in want}
    out: dict[str, list[dict[str, Any]]] = {
        "create": [],
        "reactivate": [],
        "keep": [],
        "deactivate": [],
    }
    for w in want:
        b = by_name.get(w["username"])
        if b is None:
            out["create"].append(w)
        elif b.get("delete_at"):
            out["reactivate"].append({**w, "user_id": b["user_id"]})
        else:
            out["keep"].append({**w, "user_id": b["user_id"]})
    for b in existing:
        if (
            b["username"].startswith(f"{volume}-")
            and b["username"] not in wanted
            and not b.get("delete_at")
        ):
            out["deactivate"].append(b)
    return out


def account_for_cwd(cwd: str, accounts: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The deepest provisioned project folder containing cwd."""
    here = Path(cwd)
    best, depth = None, -1
    for a in accounts:
        if not a.get("path"):
            continue
        root = Path(a["path"])
        if (here == root or root in here.parents) and len(root.parts) > depth:
            best, depth = a, len(root.parts)
    return best


# --- the registry ---------------------------------------------------------------------


@contextlib.contextmanager
def registry(home: Path) -> Iterator[dict[str, Any]]:
    """Read-modify-write under an exclusive lock: two sessions can start at once."""
    d = state_dir(home)
    d.mkdir(parents=True, exist_ok=True)
    path = d / "sessions.json"
    with (d / "sessions.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except OSError, ValueError:
            data = {}
        data.setdefault("sessions", {})
        yield data
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(path)


def live_for(data: dict[str, Any], account: str, *, but: str | None = None) -> list[str]:
    return [k for k, v in data["sessions"].items() if v["account"] == account and k != but]


def register_session(home: Path, key: str, account: str, session_id: str, cwd: str) -> bool:
    """Record the process. True when the account had no other live process."""
    with registry(home) as data:
        first = not live_for(data, account)  # this process counts: /clear re-registers
        data["sessions"][key] = {
            "account": account,
            "session_id": session_id,
            "cwd": cwd,
            "since": now_utc(),
        }
    return first


def deregister_session(home: Path, key: str) -> tuple[str | None, bool]:
    """(account, now_empty). (None, False) when the process was never registered."""
    with registry(home) as data:
        entry = data["sessions"].pop(key, None)
        if entry is None:
            return None, False
        return entry["account"], not live_for(data, entry["account"])


def sweep_registry(home: Path, alive: Callable[[str], bool]) -> tuple[list[str], list[str]]:
    """Drop dead processes. (removed keys, accounts left with no live process)."""
    with registry(home) as data:
        dead = [k for k in data["sessions"] if not alive(k)]
        touched = {data["sessions"][k]["account"] for k in dead}
        for k in dead:
            del data["sessions"][k]
        emptied = sorted(a for a in touched if not live_for(data, a))
    return dead, emptied


# --- processes ------------------------------------------------------------------------


def _ps(pid: int, field: str) -> str:
    r = subprocess.run(
        ["ps", "-o", f"{field}=", "-p", str(pid)], capture_output=True, text=True, check=False
    )
    return r.stdout.strip()


def is_claude(pid: int) -> bool:
    return Path(_ps(pid, "comm")).name == "claude"


def session_pid(env: dict[str, str] | None = None) -> int | None:
    """The Claude Code process this hook belongs to: its inbox socket, else the parents."""
    env = os.environ if env is None else env
    sock = env.get("CLAUDE_CODE_MESSAGING_SOCKET", "")
    if m := re.search(r"/(\d+)\.sock$", sock):
        return int(m.group(1))
    pid = os.getppid()
    for _ in range(6):
        if pid <= 1:
            return None
        if is_claude(pid):
            return pid
        try:
            pid = int(_ps(pid, "ppid") or 0)
        except ValueError:
            return None
    return None


def alive_claude(key: str) -> bool:
    return key.isdigit() and is_claude(int(key))


def branch_of(cwd: str) -> str:
    r = subprocess.run(
        ["git", "-C", cwd, "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
        timeout=3,
    )
    return r.stdout.strip() if r.returncode == 0 else ""


# --- Keychain -------------------------------------------------------------------------


def keychain_store_cmd(account: str, token: str) -> tuple[list[str], str]:
    """(argv, stdin). The token is in stdin only — never in argv, so never in `ps`."""
    if account != ADMIN and not USERNAME_RE.match(account):
        die(f"refusing Keychain account name {account!r}")
    if not TOKEN_RE.match(token):
        die("refusing to store a token that is not a Mattermost token")
    return ["security", "-i"], f"add-generic-password -U -s {SERVICE} -a {account} -w {token}\n"


def keychain_store(account: str, token: str) -> None:
    argv, stdin = keychain_store_cmd(account, token)
    r = subprocess.run(argv, input=stdin, capture_output=True, text=True, check=False)
    if r.returncode != 0:
        die(f"Keychain refused the item for {account} (exit {r.returncode})")


def keychain_read(account: str) -> str | None:
    r = subprocess.run(
        ["security", "find-generic-password", "-s", SERVICE, "-a", account, "-w"],
        capture_output=True,
        text=True,
        check=False,
    )
    token = r.stdout.strip()
    return token if r.returncode == 0 and token else None


# --- Mattermost -----------------------------------------------------------------------

Transport = Callable[[str, str, dict[str, str], bytes | None], tuple[int, Any]]


def urllib_transport(method: str, url: str, headers: dict[str, str], body: bytes | None):
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            raw = resp.read()
            return resp.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw) if raw else None
        except ValueError:
            return e.code, None


class MattermostError(Exception):
    pass


def reachable(url: str) -> bool:
    """One short TCP connect to the server. False is the hook's cue to skip every request."""
    u = urllib.parse.urlsplit(url)
    port = u.port or (443 if u.scheme == "https" else 80)
    try:
        with socket.create_connection((u.hostname or "", port), timeout=PROBE_TIMEOUT):
            return True
    except OSError:
        return False


class Mattermost:
    def __init__(self, url: str, token: str, transport: Transport | None = None):
        self.base = url.rstrip("/") + "/api/v4"
        self._token = token
        self._send = transport or urllib_transport

    def call(self, method: str, path: str, body: Any = None) -> Any:
        headers = {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}
        data = json.dumps(body).encode() if body is not None else None
        status, payload = self._send(method, self.base + path, headers, data)
        if status >= 400:
            msg = payload.get("message") if isinstance(payload, dict) else ""
            raise MattermostError(f"{method} {path} → {status} {msg}".rstrip())
        return payload

    def team_by_name(self, name: str) -> dict[str, Any]:
        return self.call("GET", f"/teams/name/{name}")

    def bots(self) -> list[dict[str, Any]]:
        out, page = [], 0
        while True:
            batch = self.call("GET", f"/bots?include_deleted=true&page={page}&per_page=200")
            out.extend(batch or [])
            if not batch or len(batch) < 200:
                return out
            page += 1

    def create_bot(self, username: str, display_name: str) -> dict[str, Any]:
        desc = "Active while a Claude Code session runs in this project (alemax presence)"
        return self.call(
            "POST",
            "/bots",
            {"username": username, "display_name": display_name, "description": desc},
        )

    def enable_bot(self, user_id: str) -> None:
        self.call("POST", f"/bots/{user_id}/enable")

    def disable_bot(self, user_id: str) -> None:
        self.call("POST", f"/bots/{user_id}/disable")

    def create_token(self, user_id: str) -> str:
        return self.call("POST", f"/users/{user_id}/tokens", {"description": SERVICE})["token"]

    def channel_by_name(self, team_id: str, name: str) -> dict[str, Any]:
        return self.call("GET", f"/teams/{team_id}/channels/name/{name}")

    def add_to_channel(self, channel_id: str, user_id: str) -> None:
        self.call("POST", f"/channels/{channel_id}/members", {"user_id": user_id})

    def add_to_team(self, team_id: str, user_id: str) -> None:
        self.call("POST", f"/teams/{team_id}/members", {"team_id": team_id, "user_id": user_id})

    def set_status(self, user_id: str, status: str) -> None:
        self.call("PUT", f"/users/{user_id}/status", {"user_id": user_id, "status": status})

    def set_custom_status(self, user_id: str, text: str) -> None:
        self.call("PUT", f"/users/{user_id}/status/custom", {"emoji": ACTIVE_EMOJI, "text": text})

    def clear_custom_status(self, user_id: str) -> None:
        self.call("DELETE", f"/users/{user_id}/status/custom")

    def user_by_username(self, name: str) -> dict[str, Any]:
        return self.call("GET", f"/users/username/{name}")

    def search_users(self, term: str) -> list[dict[str, Any]]:
        return self.call("POST", "/users/search", {"term": term, "allow_inactive": False}) or []

    def posts_since(self, channel_id: str, since_ms: int) -> dict[str, Any]:
        return self.call("GET", f"/channels/{channel_id}/posts?since={since_ms}") or {}

    def thread(self, root_id: str) -> dict[str, Any]:
        return self.call("GET", f"/posts/{root_id}/thread") or {}

    def get_post(self, post_id: str) -> dict[str, Any]:
        return self.call("GET", f"/posts/{post_id}")

    def create_post(self, channel_id: str, message: str, root_id: str = "") -> dict[str, Any]:
        body = {"channel_id": channel_id, "message": message}
        if root_id:
            body["root_id"] = root_id
        return self.call("POST", "/posts", body)

    def patch_post(self, post_id: str, message: str) -> dict[str, Any]:
        return self.call("PUT", f"/posts/{post_id}/patch", {"message": message})


def load_config(home: Path) -> dict[str, Any] | None:
    try:
        return json.loads(config_path(home).read_text(encoding="utf-8"))
    except OSError, ValueError:
        return None


def save_config(home: Path, cfg: dict[str, Any]) -> None:
    p = config_path(home)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    tmp.replace(p)


def mark(
    cfg: dict[str, Any],
    account: dict[str, Any],
    active: bool,
    *,
    text: str = "",
    transport: Transport = urllib_transport,
    token_for: Callable[[str], str | None] = keychain_read,
) -> None:
    token = token_for(account["username"])
    if not token:
        raise MattermostError(f"no Keychain token for {account['username']}")
    mm = Mattermost(cfg["url"], token, transport)
    if active:
        mm.set_status(account["user_id"], "online")
        mm.set_custom_status(account["user_id"], text)
    else:
        mm.clear_custom_status(account["user_id"])
        mm.set_status(account["user_id"], "offline")


# --- the hook -------------------------------------------------------------------------


def handle_event(
    home: Path,
    event: dict[str, Any],
    *,
    pid: int | None,
    transport: Transport = urllib_transport,
    token_for: Callable[[str], str | None] = keychain_read,
    branch: Callable[[str], str] = branch_of,
    probe: Callable[[str], bool] = reachable,
    notices: list[str] | None = None,
    unread: Callable[..., int] | None = None,
) -> str:
    """Apply one hook event. Returns a short outcome for the log.

    `notices` collects the one context line a SessionStart may add (unread messages);
    the caller decides how to emit it. `unread` counts an account's unread messages.
    """
    cfg = load_config(home)
    if not cfg:
        return "unconfigured"
    name = event.get("hook_event_name")
    key = str(pid) if pid else f"session:{event.get('session_id', '?')}"
    by_name = {a["username"]: a for a in cfg.get("accounts", [])}

    if name == "SessionStart":
        cwd = event.get("cwd") or ""
        account = account_for_cwd(cwd, cfg.get("accounts", []))
        if account is None:
            return "not a project folder"
        first = register_session(
            home, key, account["username"], str(event.get("session_id", "")), cwd
        )
        if not (first or event.get("source") in ("startup", "resume")):
            return f"registered {account['username']}"
        if not probe(cfg["url"]):
            return f"registered {account['username']}, server unreachable (skipped)"
        b = branch(cwd)
        text = f"active on {cfg['volume']}" + (f" · {b}" if b else "")
        if pid:
            text += f" · sock {pid}"
        mark(cfg, account, True, text=text, transport=transport, token_for=token_for)
        if unread is not None and notices is not None:
            n = unread(home, cfg, account, transport=transport, token_for=token_for)
            if n:
                how = "run /alemax:mattermost-read-msg"
                if cfg.get("meta"):
                    how += f", or: {alemax_prefix(cfg['meta'])} presence inbox --mark-read"
                notices.append(
                    f"{n} unread Mattermost message(s) for @{account['username']} — {how}"
                )
        return f"active {account['username']}"

    if name == "SessionEnd":
        if event.get("reason") in QUIET_END_REASONS:
            return f"ignored end ({event.get('reason')})"
        username, empty = deregister_session(home, key)
        if username and empty and username in by_name:
            if not probe(cfg["url"]):
                return f"deregistered {username}, server unreachable (skipped)"
            mark(cfg, by_name[username], False, transport=transport, token_for=token_for)
            return f"inactive {username}"
        return f"deregistered {username or 'nothing'}"

    return f"ignored {name}"


def cmd_hook(a: argparse.Namespace) -> int:
    """Never fails a session, never prints: stdout would land in the session's context.

    The log is the only channel, so every line says what fired, where, and for which
    process — enough to tell a real session from a test, and a skip from a failure.
    """
    home = Path.home()
    ctx = "event=? pid=? cwd=?"
    notices: list[str] = []
    try:
        event = json.loads(sys.stdin.read() or "{}")
        pid = session_pid()
        how = event.get("source") or event.get("reason") or "-"
        ctx = (
            f"event={event.get('hook_event_name', '?')}/{how} pid={pid or '?'} "
            f"cwd={event.get('cwd', '?')}"
        )
        outcome = handle_event(
            home,
            event,
            pid=pid,
            transport=urllib_transport,
            token_for=keychain_read,
            branch=branch_of,
            probe=reachable,
            notices=notices,
            unread=_unread_counter(),
        )
        log(home, f"{ctx} -> {outcome}" + (f" (+{notices[0]})" if notices else ""))
    except Exception as e:  # the contract: never disrupt the session
        log(home, f"{ctx} -> error {type(e).__name__}: {e}")
    if notices:  # the one thing the hook may print: a single context line, as JSON
        out = {"hookEventName": "SessionStart", "additionalContext": notices[0]}
        print(json.dumps({"hookSpecificOutput": out}))
    return OK


def _unread_counter() -> Callable[..., int] | None:
    """The inbox lives in presence_relay; imported lazily so the hook never pays for it
    unless an account matched, and a broken relay module cannot break the hook."""
    try:
        from .presence_relay import unread_count
    except Exception:  # pragma: no cover — degrade to no notice, never to a failed hook
        return None
    return unread_count


# --- settings.json --------------------------------------------------------------------


def _is_ours(entry: dict[str, Any]) -> bool:
    return any(HOOK_MARK in h.get("command", "") for h in entry.get("hooks", []))


def without_hooks(settings: dict[str, Any]) -> dict[str, Any]:
    out = json.loads(json.dumps(settings))
    hooks = out.get("hooks", {})
    for ev in ("SessionStart", "SessionEnd"):
        if ev in hooks:
            hooks[ev] = [e for e in hooks[ev] if not _is_ours(e)]
            if not hooks[ev]:
                del hooks[ev]
    if "hooks" in out and not out["hooks"]:
        del out["hooks"]
    return out


def with_hooks(settings: dict[str, Any], exe: str) -> dict[str, Any]:
    out = without_hooks(settings)
    cmd = {"type": "command", "command": f"{exe} {HOOK_MARK}", "timeout": HOOK_TIMEOUT}
    hooks = out.setdefault("hooks", {})
    hooks.setdefault("SessionStart", []).append({"matcher": START_MATCHER, "hooks": [cmd]})
    hooks.setdefault("SessionEnd", []).append({"hooks": [dict(cmd)]})
    return out


def rewrite_settings(path: Path, change: Callable[[dict[str, Any]], dict[str, Any]], dry: bool):
    try:
        before = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except ValueError:
        die(f"{path} is not valid JSON — refusing to touch it")
    after = change(before)
    print(json.dumps(after.get("hooks", {}), indent=2))
    if dry:
        print("(dry run — nothing written)")
        return
    if path.exists():
        stamp = f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}"
        backup = path.with_name(f"{path.name}.bak-{stamp}")
        n = 1
        while backup.exists():  # never overwrite: the first backup is the pristine one
            backup = path.with_name(f"{path.name}.bak-{stamp}-{n}")
            n += 1
        backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        backup.chmod(path.stat().st_mode & 0o777)  # as private as the original
        print(f"backup: {backup}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(after, indent=2) + "\n", encoding="utf-8")
    print(f"wrote: {path}")


def cmd_install(a: argparse.Namespace) -> int:
    cfg = load_config(Path.home()) or {}
    meta = a.meta or cfg.get("meta")
    if not a.exe and not meta:
        die("no claude-meta clone recorded — run provision from it first, or pass --meta <clone>")
    prefix = a.exe or alemax_prefix(meta)
    rewrite_settings(
        Path.home() / ".claude" / "settings.json", lambda s: with_hooks(s, prefix), a.dry_run
    )
    return OK


def cmd_uninstall(a: argparse.Namespace) -> int:
    rewrite_settings(Path.home() / ".claude" / "settings.json", without_hooks, a.dry_run)
    return OK


# --- provision, status, sweep ---------------------------------------------------------


def meta_clone(a: argparse.Namespace) -> str:
    """The claude-meta clone provisioning runs from: --meta, else the current repo."""
    return (
        a.meta
        or subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=False
        ).stdout.strip()
    )


def projects_text(a: argparse.Namespace, volume: str) -> str:
    if a.projects:
        return Path(a.projects).read_text(encoding="utf-8")
    meta = meta_clone(a)
    r = subprocess.run(
        ["git", "-C", meta, "show", f"{volume}:projects.yaml"],
        capture_output=True,
        text=True,
        check=False,
    )
    if r.returncode != 0:
        die(f"cannot read {volume}:projects.yaml in {meta or '.'} — pass --projects FILE")
    return r.stdout


def cmd_provision(a: argparse.Namespace) -> int:
    home = Path.home()
    volume = a.volume or volume_from_home(home)
    if not volume:
        die("cannot tell the volume from $HOME — pass --volume")
    cfg = load_config(home) or {}
    url, team = a.url or cfg.get("url"), a.team or cfg.get("team")
    if not url or not team:
        die("first run needs --url and --team")
    aliases = {**cfg.get("aliases", {}), **dict(x.split("=", 1) for x in a.alias)}
    extras = {**cfg.get("extras", {}), **dict(x.split("=", 1) for x in a.extra)}
    channel = a.channel or cfg.get("channel")
    operator = a.operator or cfg.get("operator")
    meta = meta_clone(a) or cfg.get("meta") or ""
    if Path(meta).name != "claude-meta":
        die(
            f"run provision from the volume's claude-meta clone, or pass --meta (got {meta or 'no repo'})"
        )
    admin = keychain_read(ADMIN)
    if not admin:
        die(f"no admin token — run: security add-generic-password -U -s {SERVICE} -a {ADMIN} -w")
    mm = Mattermost(url, admin)
    projects = parse_projects(projects_text(a, volume)) + [
        {"name": n, "path": path, "status": "active"} for n, path in sorted(extras.items())
    ]
    want, refused = desired_accounts(volume, projects, aliases)
    p = plan(volume, want, mm.bots())

    for verb in ("create", "reactivate", "keep", "deactivate"):
        for x in p[verb]:
            print(f"{verb:<11} {x['username']:<23} {x.get('path') or ''}")
    for name, why in refused:
        print(f"{'refused':<11} {name}: {why}")
    if a.relay:
        print(f"{'relay':<11} {relay_username(volume):<23} (listener account, no folder)")
    if not a.apply:
        print("(dry run — add --apply to change the server)")
        return OK

    team_id = mm.team_by_name(team)["id"]
    accounts = []
    for x in p["create"]:
        bot = mm.create_bot(x["username"], x["display_name"])
        x = {**x, "user_id": bot["user_id"]}
        keychain_store(x["username"], mm.create_token(x["user_id"]))
        mm.add_to_team(team_id, x["user_id"])
        accounts.append(x)
    for x in p["reactivate"]:
        mm.enable_bot(x["user_id"])
        accounts.append(x)
    accounts.extend(p["keep"])
    for x in p["reactivate"] + p["keep"]:
        if not keychain_read(x["username"]):
            keychain_store(x["username"], mm.create_token(x["user_id"]))
            print(f"token      {x['username']} reissued (none in Keychain)")
        mm.add_to_team(team_id, x["user_id"])
    for b in p["deactivate"]:
        mm.disable_bot(b["user_id"])
    if channel:
        channel_id = mm.channel_by_name(team_id, channel)["id"]
        for x in accounts:
            mm.add_to_channel(channel_id, x["user_id"])  # API only: no websocket, no login
        print(f"channel    {len(accounts)} account(s) in ~{channel}")
    keep = ("username", "display_name", "project", "path", "user_id")
    born = {x["username"]: x.get("provisioned_at") for x in cfg.get("accounts", [])}
    now_ms = int(datetime.now(UTC).timestamp() * 1000)
    relay = cfg.get("relay")
    if a.relay:
        relay = provision_relay(mm, volume, team_id, channel)
    if relay and operator:  # one or more Mattermost usernames, comma-separated
        names = [n.strip() for n in operator.split(",") if n.strip()]
        relay["operator_ids"] = [mm.user_by_username(n)["id"] for n in names]
    save_config(
        home,
        {
            "url": url,
            "team": team,
            "volume": volume,
            "aliases": aliases,
            "extras": extras,
            "channel": channel,
            "operator": operator,
            "meta": meta,
            "relay": relay,
            "accounts": [
                {**{k: x[k] for k in keep}, "provisioned_at": born.get(x["username"]) or now_ms}
                for x in accounts
            ],
        },
    )
    print(f"wrote: {config_path(home)}")
    return OK


RELAY_USERNAME_RE = re.compile(r"^claude-[a-z][a-z0-9]*[0-9]$")  # volume: alnum, ends in a digit


def relay_username(volume: str) -> str:
    return f"claude-{volume}"


def provision_relay(mm: Mattermost, volume: str, team_id: str, channel: str | None):
    """Create or reactivate claude-<volume>, the volume's listener. Never a folder account,
    so the hook never touches it; its token lives in the Keychain like every other."""
    name = relay_username(volume)
    bot = next((b for b in mm.bots() if b["username"] == name), None)
    if bot is None:
        bot = mm.call(
            "POST",
            "/bots",
            {
                "username": name,
                "display_name": f"relay @ {volume.upper()}",
                "description": "This volume's Mattermost relay (alemax presence listen)",
            },
        )
        print(f"create      {name}")
    elif bot.get("delete_at"):
        mm.enable_bot(bot["user_id"])
        print(f"reactivate  {name}")
    if not keychain_read(name):
        keychain_store(name, mm.create_token(bot["user_id"]))
        print(f"token       {name} issued")
    mm.add_to_team(team_id, bot["user_id"])
    if channel:
        mm.add_to_channel(mm.channel_by_name(team_id, channel)["id"], bot["user_id"])
    return {"username": name, "user_id": bot["user_id"]}


def setup_findings(
    home: Path,
    *,
    keychain: Callable[[str], str | None] = keychain_read,
    probe: Callable[[str], bool] = reachable,
) -> list[tuple[bool, str, str]]:
    """(ok, item, how to fix) for everything a volume needs. Read-only; prints no secret.

    The checklist /alemax:mattermost-setup walks — for a new volume and for one still on
    the old `uv tool` copy alike.
    """
    run = "uv run --directory plugins/alemax alemax presence"
    out: list[tuple[bool, str, str]] = []
    vol = volume_from_home(home)
    out.append(
        (bool(vol), f"volume from $HOME: {vol or '?'}", "run from a volume's redirected $HOME")
    )
    out.append(
        (
            bool(keychain(ADMIN)),
            "admin token in Keychain (needed to provision)",
            f"create a personal access token as an admin, then: security add-generic-password -U -s {SERVICE} -a {ADMIN} -w",
        )
    )
    cfg = load_config(home)
    if not cfg:
        out.append(
            (
                False,
                "presence provisioned",
                f"{run} provision --url <url> --team <team> --channel rendezvous --relay --operator <you> --extra claude-meta=<this clone>",
            )
        )
        return out
    for key in ("url", "team", "channel", "operator", "meta"):
        out.append(
            (
                bool(cfg.get(key)),
                f"config records {key}: {cfg.get(key) or '-'}",
                f"{run} provision --{key} <value> --apply",
            )
        )
    out.append(
        (
            probe(cfg["url"]) if cfg.get("url") else False,
            "server reachable",
            "check the NAS and the URL",
        )
    )
    missing = [x["username"] for x in cfg.get("accounts", []) if not keychain(x["username"])]
    out.append(
        (
            not missing,
            f"{len(cfg.get('accounts', []))} account token(s) in Keychain"
            + (f", missing: {', '.join(missing)}" if missing else ""),
            f"{run} provision --apply",
        )
    )
    relay = cfg.get("relay") or {}
    out.append(
        (
            bool(relay) and bool(keychain(relay.get("username", ""))),
            f"relay account: {relay.get('username') or 'none'}",
            f"{run} provision --relay --operator <you> --apply",
        )
    )
    try:
        settings = json.loads((home / ".claude" / "settings.json").read_text(encoding="utf-8"))
    except OSError, ValueError:
        settings = {}
    cmds = [
        h.get("command", "")
        for ev in ("SessionStart", "SessionEnd")
        for e in settings.get("hooks", {}).get(ev, [])
        for h in e.get("hooks", [])
        if HOOK_MARK in h.get("command", "")
    ]
    meta = cfg.get("meta") or ""
    current = bool(meta) and len(cmds) == 2 and all(f"{meta}/plugins/alemax" in c for c in cmds)
    out.append(
        (
            current,
            f"hooks installed, running the plugin from {meta or 'the clone'}"
            if current
            else f"hooks: {len(cmds)} found, not running from the recorded clone",
            f"{run} install",
        )
    )
    # where `uv tool install` puts it — never PATH: under `uv run` the plugin itself is on PATH
    old = (home / ".local" / "bin" / "alemax").exists() or (
        home / ".local" / "share" / "uv" / "tools" / "alemax"
    ).exists()
    out.append((not old, "no leftover `uv tool` copy of alemax", "uv tool uninstall alemax"))
    return out


def cmd_check(a: argparse.Namespace) -> int:
    findings = setup_findings(Path.home())
    for ok, item, fix in findings:
        print(f"{'ok ' if ok else 'FIX'}  {item}" + ("" if ok else f"\n       → {fix}"))
    return OK if all(ok for ok, _, _ in findings) else FOUND


def who_rows(
    home: Path,
    alive: Callable[[str], bool] = lambda k: alive_claude(k),
    volumes: Path = Path("/Volumes"),
) -> list[dict[str, Any]]:
    """Live and stale registrations on every volume of this Mac, for this operator.

    Every volume's state sits under its own $HOME, and all of them are readable here — the
    cross-volume view ListAgents cannot give. Read-only.
    """
    rows = []
    op = home.name
    for state in sorted(volumes.glob(f"*/Users/{op}/.local/state/{SERVICE}/sessions.json")):
        vol_home = state.parents[3]
        try:
            sessions = json.loads(state.read_text(encoding="utf-8")).get("sessions", {})
        except OSError, ValueError:
            continue
        for pid, e in sorted(sessions.items()):
            rows.append(
                {
                    "volume": vol_home.parent.parent.name.lower(),
                    "account": e["account"],
                    "folder": e.get("cwd", ""),
                    "pid": pid,
                    "alive": alive(pid),
                    "since": e.get("since", ""),
                    "this_volume": vol_home == home,
                }
            )
    return rows


def cmd_who(a: argparse.Namespace) -> int:
    rows = who_rows(Path.home())
    if not rows:
        print("no presence registrations on this Mac")
        return OK
    for r in rows:
        state = "live " if r["alive"] else "STALE"
        here = "" if r["this_volume"] else "  (other volume — its own relay or hook clears it)"
        sock = f"uds:/tmp/cc-socks/{r['pid']}.sock" if r["alive"] else "no process — sweep"
        print(f"{state} {r['volume']:<7} @{r['account']:<23} {sock}{here}")
    stale_here = sum(1 for r in rows if r["this_volume"] and not r["alive"])
    return FOUND if stale_here else OK


def cmd_status(a: argparse.Namespace) -> int:
    home = Path.home()
    cfg = load_config(home)
    if not cfg:
        print(
            f"{home_volume_mismatch(os.getcwd(), home) or ''}presence is not provisioned on this volume"
        )
        return ERROR
    with registry(home) as data:
        sessions = dict(data["sessions"])
    for acct in cfg["accounts"]:
        keys = [k for k, v in sessions.items() if v["account"] == acct["username"]]
        flag = "active  " if keys else "inactive"
        print(f"{flag} {acct['username']:<23} {acct.get('path') or ''}")
        for k in keys:
            alive = "alive" if alive_claude(k) else "DEAD (sweep)"
            print(f"           pid {k} · {alive} · since {sessions[k]['since']}")
    return OK


def cmd_sweep(a: argparse.Namespace) -> int:
    home = Path.home()
    cfg = load_config(home)
    if not cfg:
        return OK
    dead, emptied = sweep_registry(home, alive_claude)
    by_name = {x["username"]: x for x in cfg["accounts"]}
    for k in dead:
        print(f"removed    pid {k}")
    for name in emptied:
        if name in by_name:
            try:
                mark(cfg, by_name[name], False)
                print(f"inactive   {name}")
            except MattermostError as e:
                print(f"failed     {name}: {e}")
    return OK


def register(ap: argparse.ArgumentParser) -> None:
    sub = ap.add_subparsers(dest="subcommand", required=True, metavar="SUBCOMMAND")

    s = sub.add_parser("provision", help="plan the accounts from projects.yaml; --apply to create")
    s.add_argument("--url", help="Mattermost server, e.g. http://192.168.1.96:8065")
    s.add_argument("--team", help="team name (URL slug)")
    s.add_argument("--volume", help="default: from $HOME")
    s.add_argument("--meta", help="claude-meta clone (default: current repo)")
    s.add_argument("--projects", help="projects.yaml to read instead of <volume>:projects.yaml")
    s.add_argument("--alias", action="append", default=[], help="project=short (repeatable)")
    s.add_argument(
        "--extra",
        action="append",
        default=[],
        help="name=path for a folder outside projects.yaml (repeatable, remembered)",
    )
    s.add_argument("--channel", help="channel every account joins, e.g. rendezvous (remembered)")
    s.add_argument("--relay", action="store_true", help="also provision claude-<volume>, the relay")
    s.add_argument(
        "--operator",
        help="Mattermost username(s) the relay takes orders from, comma-separated (remembered)",
    )
    s.add_argument("--apply", action="store_true", help="change the server")
    s.set_defaults(func=cmd_provision)

    sub.add_parser("hook", help="SessionStart/SessionEnd hook (stdin JSON)").set_defaults(
        func=cmd_hook
    )
    sub.add_parser("status", help="registered sessions per account").set_defaults(func=cmd_status)
    sub.add_parser("check", help="what this volume's setup has and lacks, with fixes").set_defaults(
        func=cmd_check
    )
    sub.add_parser("who", help="live and stale sessions on every volume of this Mac").set_defaults(
        func=cmd_who
    )
    sub.add_parser("sweep", help="drop registrations of dead processes").set_defaults(
        func=cmd_sweep
    )

    s = sub.add_parser("install", help="add the hooks to ~/.claude/settings.json")
    s.add_argument(
        "--meta", help="claude-meta clone to run from (default: the one recorded at provision)"
    )
    s.add_argument("--exe", help="override the whole command prefix (tests)")
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(func=cmd_install)

    s = sub.add_parser("uninstall", help="remove the hooks from ~/.claude/settings.json")
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(func=cmd_uninstall)

    from .presence_relay import register_relay  # relay subcommands: listen, roster, post, inbox

    register_relay(sub)
