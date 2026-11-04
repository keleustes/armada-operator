"""The relay and the mailbox on top of `alemax presence` — spec `mattermost-relay`.

    listen [--once] [--interval S]   poll ~<channel>; print one JSON line per post this
                                     volume's relay must deliver with SendMessage
    roster                           rebuild and edit this volume's single roster post
    post [--thread ROOT] TEXT        post as the account of the current folder
    send --to T[,T…] | --all-meta [--thread ROOT] TEXT
                                     mention one or more accounts, as this folder's account
    inbox [--count|--json] [--mark-read]
                                     the current folder's unread messages

Everything except delivery is deterministic and lives here: polling, the allowlist, the
loop guard, "not running" replies and the roster. The relay SESSION is woken by
`Monitor` only for a line it must forward — the one step a script cannot do, because
the socket protocol is not published.

Who may be relayed: the operator, matched by user id; and the fleet's own bot accounts —
relays `claude-<vol>` and presence accounts `<vol>-<folder>` — recognised as bot accounts
with those names. Only an administrator can create or rename a bot, so a person cannot
pass as one by renaming themselves.

State, all under the volume's `~/.local/state/claude-presence/`, outside any repo:
`relay.json` (poll cursor, forwarded ids, per-thread hop counts, the roster post) and
`inbox.json` (one read cursor per account).
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..io import OK, die
from . import presence as pr

POLL_SECONDS = 5.0
SWEEP_EVERY_MS = 60_000
HOP_LIMIT = 6
FORWARDED_KEEP = 2000
MENTION_RE = re.compile(r"(?<![\w.-])@([a-z0-9][a-z0-9._-]*)")
# `<volume>-<folder>` (k8s01 too), or `upstream-<folder>` for the canonical clone
PRESENCE_USERNAME_RE = re.compile(r"^(?:[a-z][a-z0-9]*[0-9]|upstream)-[a-z0-9._-]+$")


# --- small helpers ----------------------------------------------------------------------


def now_ms() -> int:
    return int(datetime.now(UTC).timestamp() * 1000)


def mentions(text: str, known: set[str]) -> set[str]:
    """The known usernames a text mentions.

    Mattermost names may contain `.`, `-` and `_`, so `@iac01-claude-meta....time` is one
    token. For each `@token`, take the LONGEST known name that the token equals or begins
    with at a punctuation boundary — so `@name.` and `@name....more` both count, while
    `@name-other` is `name-other` when that account exists and never a stray `name`.
    """
    out: set[str] = set()
    for m in MENTION_RE.finditer(text or ""):
        token = m.group(1)
        cuts = [len(token)] + [i for i, ch in enumerate(token) if ch in "._-"]
        for cut in sorted(set(cuts), reverse=True):
            if token[:cut] in known:
                out.add(token[:cut])
                break
    return out


def _load(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    try:
        return {**default, **json.loads(path.read_text(encoding="utf-8"))}
    except OSError, ValueError:
        return dict(default)


def _save(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(path)


def relay_state_path(home: Path) -> Path:
    return pr.state_dir(home) / "relay.json"


def inbox_state_path(home: Path) -> Path:
    return pr.state_dir(home) / "inbox.json"


def live_pid(home: Path, username: str, alive: Callable[[str], bool]) -> str | None:
    """The newest live process registered for an account, or None."""
    with pr.registry(home) as data:
        rows = [(v.get("since", ""), k) for k, v in data["sessions"].items()]
        rows = [(since, k) for since, k in rows if data["sessions"][k]["account"] == username]
    for _since, key in sorted(rows, reverse=True):
        if alive(key):
            return key
    return None


def channel_id(mm: pr.Mattermost, cfg: dict[str, Any]) -> str:
    team = mm.team_by_name(cfg["team"])["id"]
    return mm.channel_by_name(team, cfg["channel"])["id"]


def _sorted_posts(payload: dict[str, Any]) -> list[dict[str, Any]]:
    posts = [p for p in (payload.get("posts") or {}).values() if not p.get("delete_at")]
    return sorted(posts, key=lambda p: (p["create_at"], p["id"]))


class Users:
    """user_id → user record, fetched once per run."""

    def __init__(self, mm: pr.Mattermost):
        self.mm, self.cache = mm, {}

    def get(self, uid: str) -> dict[str, Any]:
        if uid not in self.cache:
            try:
                self.cache[uid] = self.mm.call("GET", f"/users/{uid}")
            except pr.MattermostError:
                self.cache[uid] = {"id": uid, "username": "?", "is_bot": False}
        return self.cache[uid]


def allowed_author(user: dict[str, Any], operator_ids: list[str]) -> bool:
    if user.get("id") in operator_ids:
        return True
    name = user.get("username", "")
    return bool(user.get("is_bot")) and bool(
        pr.RELAY_USERNAME_RE.match(name) or PRESENCE_USERNAME_RE.match(name)
    )


# --- the roster -------------------------------------------------------------------------


def roster_text(home: Path, cfg: dict[str, Any], alive: Callable[[str], bool]) -> str:
    with pr.registry(home) as data:
        sessions = dict(data["sessions"])
    rows = []
    for acct in cfg.get("accounts", []):
        for pid, entry in sorted(sessions.items()):
            if entry["account"] == acct["username"] and alive(pid):
                folder = (acct.get("path") or "").split("/Users/", 1)[-1].split("/", 1)[-1]
                rows.append(
                    # no `@`: a mention would put the roster in every listed account's inbox
                    f"| `{acct['username']}` | `{folder}` | `uds:/tmp/cc-socks/{pid}.sock` |"
                )
    vol = cfg["volume"]
    head = (
        f"**{vol} roster** — live sessions, kept current by `@{pr.relay_username(vol)}`. "
        "Sockets are valid on this volume's Mac only; across Macs, mention the @account.\n\n"
    )
    if not rows:
        return head + "_no live sessions_"
    return head + "| account | folder | socket |\n|---|---|---|\n" + "\n".join(rows)


def refresh_roster(
    home: Path,
    cfg: dict[str, Any],
    mm: pr.Mattermost,
    cid: str,
    state: dict[str, Any],
    alive: Callable[[str], bool],
) -> str:
    """Edit the volume's one roster post; create it only when there is none."""
    text = roster_text(home, cfg, alive)
    if text == state.get("roster_text") and state.get("roster_post_id"):
        return "unchanged"
    if state.get("roster_post_id"):
        try:
            mm.patch_post(state["roster_post_id"], text)
            state["roster_text"] = text
            return "edited"
        except pr.MattermostError:
            pass  # deleted or not ours any more: fall through and create one
    state["roster_post_id"] = mm.create_post(cid, text)["id"]
    state["roster_text"] = text
    return "created"


# --- one poll ---------------------------------------------------------------------------


def poll_once(
    home: Path,
    cfg: dict[str, Any],
    mm: pr.Mattermost,
    *,
    alive: Callable[[str], bool] = pr.alive_claude,
    emit: Callable[[str], None] = print,
    clock: Callable[[], int] = now_ms,
    token_for: Callable[[str], str | None] = pr.keychain_read,
) -> list[dict[str, Any]]:
    """Process posts since the cursor. Returns the delivery records it emitted.

    Also sweeps this volume once a minute, so a session that died without a clean exit no
    longer leaves its account showing active until someone remembers to run `sweep`.
    """
    relay = cfg["relay"]
    operator_ids = relay.get("operator_ids", [])
    local = {a["username"] for a in cfg.get("accounts", [])}
    path = relay_state_path(home)
    state = _load(path, {"cursor": 0, "forwarded": [], "hops": {}, "notified": []})
    if not state["cursor"]:
        state["cursor"] = clock()  # first run: from now, never the channel's history
        _save(path, state)
    cid = channel_id(mm, cfg)
    users = Users(mm)
    forwarded = set(state["forwarded"])
    out: list[dict[str, Any]] = []
    payload = mm.posts_since(cid, state["cursor"])
    for post in _sorted_posts(payload):
        state["cursor"] = max(state["cursor"], post.get("update_at", post["create_at"]))
        if post["user_id"] == relay["user_id"] or (post.get("type") or "").startswith("system_"):
            continue
        author = users.get(post["user_id"])
        if not allowed_author(author, operator_ids):
            continue
        root = post.get("root_id") or post["id"]
        hops = state["hops"]
        hops[root] = 0 if post["user_id"] in operator_ids else hops.get(root, 0) + 1
        if hops[root] > HOP_LIMIT:
            if root not in state["notified"]:
                mm.create_post(
                    cid,
                    f"Relay `{relay['username']}`: {HOP_LIMIT} posts in a row without the "
                    "operator — forwarding paused in this thread until the operator posts.",
                    root,
                )
                state["notified"].append(root)
            continue
        targets = mentions(post["message"], local) - {author.get("username")}
        for target in sorted(targets):
            key = f"{post['id']}:{target}"
            if key in forwarded:
                continue
            pid = live_pid(home, target, alive)
            if pid is None:
                mm.create_post(
                    cid,
                    f"`{target}` is not running on {cfg['volume']}; it will see this when "
                    "it next runs `/alemax:mattermost-read-msg`.",
                    root,
                )
            else:
                rec = {
                    "post_id": post["id"],
                    "root_id": root,
                    "author": author.get("username"),
                    "target": target,
                    "socket": f"uds:/tmp/cc-socks/{pid}.sock",
                    "text": post["message"],
                    # runnable from the target's own folder, managed or not
                    # the asker's mention first, so their own relay wakes them with the answer
                    "reply": f"{pr.alemax_prefix(cfg['meta']) if cfg.get('meta') else 'alemax'}"
                    f' presence post --thread {root} "@{author.get("username")} <answer>"',
                }
                emit(json.dumps(rec))
                out.append(rec)
            forwarded.add(key)
    state["forwarded"] = sorted(forwarded)[-FORWARDED_KEEP:]
    if not state.get("swept_at") or clock() - state["swept_at"] >= SWEEP_EVERY_MS:
        _dead, emptied = pr.sweep_registry(home, alive)
        by_name = {a["username"]: a for a in cfg.get("accounts", [])}
        for name in emptied:
            if name in by_name:
                with contextlib.suppress(Exception):  # cannot mark now: the next sweep retries
                    pr.mark(cfg, by_name[name], False, transport=mm._send, token_for=token_for)
        state["swept_at"] = clock()
    refresh_roster(home, cfg, mm, cid, state, alive)
    _save(path, state)
    return out


# --- the inbox --------------------------------------------------------------------------


def inbox_items(
    home: Path, cfg: dict[str, Any], account: dict[str, Any], mm: pr.Mattermost
) -> list[dict[str, Any]]:
    """Posts for this account after its read cursor: mentions, and replies in threads it
    posted in. Oldest first. Never the account's own posts."""
    cursors = _load(inbox_state_path(home), {})
    if account["username"] in cursors:
        cursor = cursors[account["username"]]
    elif "provisioned_at" in account:
        cursor = account["provisioned_at"]
    else:  # provisioned before read cursors existed: start now, never the whole history
        cursor = now_ms()
    cid = channel_id(mm, cfg)
    users = Users(mm)
    in_thread: dict[str, bool] = {}
    items = []
    for post in _sorted_posts(mm.posts_since(cid, cursor)):
        if post["create_at"] <= cursor or post["user_id"] == account["user_id"]:
            continue
        hit = account["username"] in mentions(post["message"], {account["username"]})
        root = post.get("root_id")
        if not hit and root:
            if root not in in_thread:
                thread = mm.thread(root).get("posts") or {}
                in_thread[root] = any(p["user_id"] == account["user_id"] for p in thread.values())
            hit = in_thread[root]
        if hit:
            items.append(
                {
                    "id": post["id"],
                    "at": post["create_at"],
                    "author": users.get(post["user_id"]).get("username"),
                    "root_id": root or post["id"],
                    "text": post["message"],
                }
            )
    return items


def mark_read(home: Path, account: str, upto_ms: int) -> None:
    path = inbox_state_path(home)
    cursors = _load(path, {})
    cursors[account] = max(cursors.get(account, 0), upto_ms)
    _save(path, cursors)


def unread_count(
    home: Path,
    cfg: dict[str, Any],
    account: dict[str, Any],
    *,
    transport: pr.Transport | None = None,
    token_for: Callable[[str], str | None] = pr.keychain_read,
) -> int:
    """For the start hook. Zero when the channel or a token is missing — never raises."""
    if not cfg.get("channel"):
        return 0
    token = token_for(account["username"])
    if not token:
        return 0
    try:
        return len(inbox_items(home, cfg, account, pr.Mattermost(cfg["url"], token, transport)))
    except Exception:  # a failed count means no notice — never a failed activation
        return 0


# --- commands ---------------------------------------------------------------------------


def _relay_session(home: Path) -> tuple[dict[str, Any], pr.Mattermost]:
    cfg = pr.load_config(home)
    if not cfg or not cfg.get("relay") or not cfg.get("channel"):
        die(
            "no relay on this volume — run: alemax presence provision --relay --channel <name> --apply"
        )
    token = pr.keychain_read(cfg["relay"]["username"])
    if not token:
        die(f"no Keychain token for {cfg['relay']['username']} — re-run provision --relay --apply")
    return cfg, pr.Mattermost(cfg["url"], token)


def _folder_account(home: Path) -> tuple[dict[str, Any], dict[str, Any], pr.Mattermost]:
    cfg = pr.load_config(home)
    # A `$HOME` on another volume reads another volume's config: name it before provisioning
    # (spec `session-home-volume`). Empty when `$HOME` is right, so the message is unchanged.
    why = pr.home_volume_mismatch(os.getcwd(), home) or ""
    if not cfg:
        die(f"{why}presence is not provisioned on this volume")
    account = pr.account_for_cwd(os.getcwd(), cfg.get("accounts", []))
    if account is None:
        # Name the whole chain: the skills run from plugins/alemax, and a message naming only
        # that subdirectory reads as a path bug when the real cause is an unprovisioned clone.
        die(
            f"{why}no account to act as — neither {os.getcwd()} nor any folder above it is provisioned. "
            "Give a folder its own account from the volume's claude-meta fork: "
            "alemax presence provision --extra <name>=<folder> --apply"
        )
    if not cfg.get("channel"):
        die("no channel configured — run: alemax presence provision --channel <name> --apply")
    token = pr.keychain_read(account["username"])
    if not token:
        die(f"no Keychain token for {account['username']}")
    return cfg, account, pr.Mattermost(cfg["url"], token)


def resolve_target(name: str) -> str:
    """`@aiml01-claude-meta`, `aiml01-claude-meta` or `aiml01/claude-meta` → the username."""
    name = name.strip().lstrip("@")
    if "/" in name:
        vol, folder = name.split("/", 1)
        name = f"{vol}-{folder}"
    return name.lower()


def all_meta_accounts(mm: pr.Mattermost) -> list[str]:
    """Every volume's claude-meta presence account the server knows."""
    return sorted(
        u["username"]
        for u in mm.search_users("claude-meta")
        if u.get("is_bot")
        and PRESENCE_USERNAME_RE.match(u.get("username", ""))
        and u["username"].endswith("-claude-meta")
    )


def cmd_send(a: argparse.Namespace) -> int:
    home = Path.home()
    cfg, account, mm = _folder_account(home)
    targets = [resolve_target(t) for t in (a.to or "").split(",") if t.strip()]
    if a.all_meta:
        targets += [t for t in all_meta_accounts(mm) if t != account["username"]]
    targets = list(dict.fromkeys(targets))  # once each, in order
    if not targets:
        die("no target — name one or more with --to, or use --all-meta")
    if account["username"] in targets:  # the relay and the inbox both skip an author's own post
        die(
            f"`{account['username']}` is this folder's own account — a post never reaches its "
            "author; name another account"
        )
    for t in targets:
        try:
            mm.user_by_username(t)
        except pr.MattermostError:
            die(f"no Mattermost account `{t}` — check the roster in ~{cfg['channel']}")
    mentions_line = " ".join(f"@{t}" for t in targets)
    post = mm.create_post(channel_id(mm, cfg), f"{mentions_line} {a.text}", a.thread or "")
    root = a.thread or post["id"]
    print(f"posted {post['id']} as @{account['username']} → {mentions_line} (thread {root})")
    print(
        "delivered live only where the target's volume runs its relay; otherwise on its next read"
    )
    return OK


def cmd_listen(a: argparse.Namespace) -> int:
    home = Path.home()
    cfg, mm = _relay_session(home)

    def emit(line: str) -> None:
        print(line, flush=True)

    while True:
        try:
            poll_once(home, cfg, mm, emit=emit)
        except Exception as e:  # one line, then the next poll — never end the watch
            emit(json.dumps({"error": f"{type(e).__name__}: {e}"}))
        if a.once:
            return OK
        time.sleep(a.interval)


def cmd_roster(a: argparse.Namespace) -> int:
    home = Path.home()
    cfg, mm = _relay_session(home)
    path = relay_state_path(home)
    state = _load(path, {"cursor": 0, "forwarded": [], "hops": {}, "notified": []})
    print(refresh_roster(home, cfg, mm, channel_id(mm, cfg), state, pr.alive_claude))
    _save(path, state)
    return OK


def cmd_post(a: argparse.Namespace) -> int:
    home = Path.home()
    cfg, account, mm = _folder_account(home)
    post = mm.create_post(channel_id(mm, cfg), a.text, a.thread or "")
    print(f"posted {post['id']} as @{account['username']}")
    return OK


def cmd_inbox(a: argparse.Namespace) -> int:
    home = Path.home()
    cfg, account, mm = _folder_account(home)
    items = inbox_items(home, cfg, account, mm)
    if a.count:
        print(len(items))
    elif a.json:
        print(json.dumps(items, indent=2))
    elif not items:
        print(f"no unread messages for @{account['username']}")
    else:
        for it in items:
            at = datetime.fromtimestamp(it["at"] / 1000, UTC).strftime("%Y-%m-%d %H:%MZ")
            where = "" if it["root_id"] == it["id"] else f" (thread {it['root_id']})"
            print(f"{at} @{it['author']}{where} [{it['id']}]\n  {it['text']}")
    if a.mark_read and items:
        mark_read(home, account["username"], items[-1]["at"])
        print(f"marked {len(items)} read", file=sys.stderr)
    return OK


def register_relay(sub: Any) -> None:
    s = sub.add_parser("listen", help="the relay's poller: one JSON line per post to deliver")
    s.add_argument("--once", action="store_true", help="one poll, then exit")
    s.add_argument("--interval", type=float, default=POLL_SECONDS, help="seconds between polls")
    s.set_defaults(func=cmd_listen)

    sub.add_parser("roster", help="rebuild and edit this volume's roster post").set_defaults(
        func=cmd_roster
    )

    s = sub.add_parser("post", help="post as the account of the current folder")
    s.add_argument("--thread", help="root post id to reply in")
    s.add_argument("text")
    s.set_defaults(func=cmd_post)

    s = sub.add_parser("send", help="post to other accounts as this folder's account")
    s.add_argument("--to", help="target(s): @account, account or vol/folder, comma-separated")
    s.add_argument("--all-meta", action="store_true", help="also every volume's claude-meta")
    s.add_argument("--thread", help="root post id to continue")
    s.add_argument("text")
    s.set_defaults(func=cmd_send)

    s = sub.add_parser("inbox", help="this folder's unread messages")
    s.add_argument("--count", action="store_true", help="print the number only")
    s.add_argument("--json", action="store_true")
    s.add_argument("--mark-read", action="store_true", help="advance the read cursor")
    s.set_defaults(func=cmd_inbox)
