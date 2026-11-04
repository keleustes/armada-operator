"""`alemax msg` — the deterministic half of /alemax:send-msg (spec `session-messaging`).

Everything the skill used to do in shell lives here, so the operator can run it at a
prompt and a session runs it as one `uv run --script` line per step. Only the two
harness tools — `ListAgents` and `SendMessage` — stay in the skill body.

    self                                  this clone's address: drive, repo, env, root
    resolve <drive> <repo>[@env]          candidate clone roots for an address
    cache get <address> [--repo <root>]   cached session entries for an address
    cache set <address> key=value …       upsert an entry in .local/sessions.yaml
    log <status> <address> <id|reason> [--intent …]   append a ledger row to .local/sent.md
    queue <drive> <repo>[@env] [--kind …] [--supersedes <id>] [--file <envelope>]
                                          write the envelope to the sender's OWN outbox
    mark <drive> <repo>[@env] <id> <status>   set an outbox entry's status
    inbox [--peer <root> …]               read peers' outboxes addressed to this clone

An address is `<drive> <repo>` — `<drive>` is a volume name in lowercase (`aiml01`,
`app01`, …) or `upstream` for the canonical claude-meta clone — plus an optional `@env`
(`prod` | `dev`). A repo is looked for at
`/Volumes/<DRIVE>/Users/<operator>/{claude-code/*,upstream/github.com/*,Applications}/<repo>`
with `os.scandir`, never a shell glob (zsh's NOMATCH aborted three versions of the shell
form). The bare address is legal only while exactly one clone matches; two matches exit 2
and list both — pick one with `@env`. The env label comes from the clone itself: the first
word of `<root>/.local/env` when the clone declares it, else inferred (`prod` under
`Applications/`, `dev` elsewhere) and marked so. Never from a manifest.

`resolve` exit codes: OK one candidate · ERROR none · AMBIGUOUS two (pick with @env). `queue` exits 3 when a dev
clone addresses a prod clone with anything but a question or a proposal.

Writes only under the current repo's gitignored `.local/` (`sessions.yaml`, `sent.md`,
`outbox/`). `inbox` reads a peer's `.local/outbox/<this address>.md` at the peer roots it
is told about — a read, never a write, into another repo. Refuses to write when `.local`
is not gitignored here. Stdlib only; YAML is the flat list `sessions.yaml` already uses.
"""

from __future__ import annotations

import argparse
import os
import re
import secrets
import sys
from datetime import UTC, datetime
from pathlib import Path

from .. import git as gitmod
from ..io import die
from ..repo import toplevel
from ..scratch import local_dir

VOLUMES = Path("/Volumes")
CANONICAL_ORIGIN = "alemaxdesign/claude-meta"
ENVS = ("prod", "dev")
KINDS = ("question", "proposal", "instruction")
STATUS_ARROW = {
    "delivered": "→",
    "received": "←",
    "probe": "probe →",
    "failed": "failed →",
    "unconfirmed": "unconfirmed →",
    "held": "held →",
    "queued": "queued →",
}
OUTBOX_STATUSES = ("queued", "delivered", "superseded", "dropped")
ADDRESS_RE = re.compile(r"^([a-z0-9]+)/([A-Za-z0-9._-]+)(?:@(prod|dev))?$")


# --- plumbing ---------------------------------------------------------------


def now_utc() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_address(text: str) -> tuple[str, str, str | None]:
    m = ADDRESS_RE.match(text)
    if not m:
        die(f"bad address {text!r} — expected <drive>/<repo>[@prod|@dev]")
    return m.group(1), m.group(2), m.group(3)


def split_env(repo: str) -> tuple[str, str | None]:
    if "@" in repo:
        name, env = repo.split("@", 1)
        if env not in ENVS:
            die(f"bad env {env!r} — expected one of {', '.join(ENVS)}")
        return name, env
    return repo, None


def address_str(drive: str, repo: str, env: str | None) -> str:
    return f"{drive}/{repo}@{env}" if env else f"{drive}/{repo}"


# --- environments and candidates -------------------------------------------


def env_of(root: Path) -> tuple[str, str]:
    """Return (label, 'declared'|'inferred') for a clone root."""
    marker = root / ".local" / "env"
    try:
        first = marker.read_text(encoding="utf-8").split()
    except OSError:
        first = []
    if first and first[0] in ENVS:
        return first[0], "declared"
    return ("prod" if root.parent.name == "Applications" else "dev"), "inferred"


def subdirs(path: Path) -> list[Path]:
    try:
        with os.scandir(path) as it:
            return sorted(Path(e.path) for e in it if e.is_dir(follow_symlinks=True))
    except OSError:
        return []


def default_operator() -> str:
    """The operator account, from $HOME. One place, so a None never reaches a path join."""
    return os.path.basename(os.path.expanduser("~"))


def drive_base(drive: str, operator: str | None) -> Path | None:
    for vol in subdirs(VOLUMES):
        if vol.name.lower() == drive:
            base = vol / "Users" / (operator or default_operator())
            return base if base.is_dir() else None
    return None


def candidates(drive: str, repo: str, operator: str | None) -> list[Path]:
    found: list[Path] = []
    if drive == "upstream":
        if repo != "claude-meta":
            die("`upstream` addresses only claude-meta (the canonical clone)")
        for vol in subdirs(VOLUMES):
            d = (
                vol
                / "Users"
                / (operator or default_operator())
                / "claude-code"
                / "alemaxdesign"
                / "claude-meta"
            )
            if d.is_dir():
                found.append(d)
    else:
        base = drive_base(drive, operator)
        if base is None:
            return []
        for org in subdirs(base / "claude-code"):
            if (org / repo).is_dir():
                found.append(org / repo)
        for org in subdirs(base / "upstream" / "github.com"):
            if (org / repo).is_dir():
                found.append(org / repo)
        if (base / "Applications" / repo).is_dir():
            found.append(base / "Applications" / repo)
    seen: dict[Path, None] = {}
    for d in found:
        seen.setdefault(d.resolve(), None)
    return list(seen)


def describe(drive: str, repo: str, roots: list[Path]) -> list[tuple[str, Path, str, str]]:
    """One row per clone: (address, root, env, declared|inferred). The address carries
    `@env` only when it has to — two clones — or when the clone declares its env."""
    out = []
    for root in roots:
        env, how = env_of(root)
        qualify = len(roots) > 1 or how == "declared"
        out.append((address_str(drive, repo, env if qualify else None), root, env, how))
    return out


def resolve(
    drive: str, repo: str, env: str | None, operator: str | None
) -> list[tuple[str, Path, str, str]]:
    rows = describe(drive, repo, candidates(drive, repo, operator))
    if env:
        rows = [r for r in rows if r[2] == env]
    return rows


def main_clone_root(root: Path) -> Path:
    """A worktree under `<clone>/.claude/worktrees/…` answers as its clone."""
    common = gitmod.probe(root, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if common and Path(common).name == ".git":
        return Path(common).parent.resolve()
    return root


def self_identity(root: Path, operator: str | None) -> dict[str, str]:
    clone = main_clone_root(root)
    origin = gitmod.probe(clone, "remote", "get-url", "origin") or ""
    parts = clone.parts
    drive = parts[2].lower() if len(parts) > 2 and parts[1] == "Volumes" else "unknown"
    repo = clone.name
    if CANONICAL_ORIGIN in origin:
        drive, repo = "upstream", "claude-meta"
    env, how = env_of(clone)
    clones = candidates(drive, repo, operator) if drive != "unknown" else []
    address = address_str(drive, repo, env if len(clones) > 1 or how == "declared" else None)
    return {
        "drive": drive,
        "repo": repo,
        "env": env,
        "env_source": how,
        "clones": str(len(clones)),
        "root": str(clone),
        "worktree": str(root),
        "origin": origin,
        "branch": gitmod.probe(root, "rev-parse", "--abbrev-ref", "HEAD") or "",
        "address": address,
    }


# --- sessions.yaml (flat list of maps; hand-written, no third-party parser) ---


def yaml_scalar(raw: str) -> tuple[str, str | None]:
    """Return (value, trailing comment) for one `key: value  # comment` tail."""
    raw = raw.strip()
    if raw.startswith('"'):
        end = raw.find('"', 1)
        while end != -1 and raw[end - 1] == "\\":
            end = raw.find('"', end + 1)
        if end == -1:
            return raw.strip('"'), None
        value = raw[1:end].replace('\\"', '"')
        rest = raw[end + 1 :].strip()
        return value, (rest[1:].strip() if rest.startswith("#") else None)
    if " #" in raw:
        value, comment = raw.split(" #", 1)
        return value.strip(), comment.strip()
    return raw, None


def yaml_emit(value: str) -> str:
    if value in ("true", "false") or re.fullmatch(r"[A-Za-z0-9_./:@+-]+", value):
        return value
    return '"' + value.replace('"', '\\"') + '"'


def split_flow(inner: str) -> list[str]:
    """Split `a: 1, b: 'x, y'` on the commas that are not inside quotes."""
    parts, buf, quote = [], "", ""
    for ch in inner:
        if quote:
            if ch == quote:
                quote = ""
        elif ch in "\"'":
            quote = ch
        elif ch == ",":
            parts.append(buf)
            buf = ""
            continue
        buf += ch
    if buf.strip():
        parts.append(buf)
    return parts


def read_flow_row(stripped: str) -> dict[str, str] | None:
    """A hand-written `- { address: x, name: y }` row, or None if this is not one.

    Legal YAML the line parser could not see: it split on the first colon, so the key
    became `{ address` and every later field collapsed into the value. The next write
    then emitted that as one quoted scalar and the row's other fields were gone.
    """
    if not (stripped.startswith("{") and stripped.endswith("}")):
        return None
    entry: dict[str, str] = {}
    for part in split_flow(stripped[1:-1]):
        if ":" not in part:
            continue
        key, tail = part.split(":", 1)
        value, comment = yaml_scalar(tail)
        entry[key.strip()] = value.strip("'")
        if comment:
            entry["note"] = (entry["note"] + "; " + comment) if entry.get("note") else comment
    return entry or None


def read_cache(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    header: list[str] = []
    entries: list[dict[str, str]] = []
    if not path.exists():
        return [
            "# alemax-send-msg cache — address → session. Operator-private, gitignored."
        ], entries
    current: dict[str, str] | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if current is None and (stripped.startswith("#") or not stripped):
            header.append(line)
            continue
        if stripped == "sessions:" or stripped == "sessions: []":
            continue
        if stripped.startswith("- "):
            stripped = stripped[2:]
            if (flow := read_flow_row(stripped)) is not None:
                entries.append(flow)
                current = flow
                continue
            current = {}
            entries.append(current)
        if current is None or ":" not in stripped:
            continue
        key, tail = stripped.split(":", 1)
        value, comment = yaml_scalar(tail)
        current[key.strip()] = value
        if comment:
            current["note"] = (current["note"] + "; " + comment) if current.get("note") else comment
    return header, entries


def write_cache(path: Path, header: list[str], entries: list[dict[str, str]]) -> None:
    lines = [*list(header), "sessions:"]
    for entry in entries:
        first = True
        for key, value in entry.items():
            prefix = "  - " if first else "    "
            lines.append(f"{prefix}{key}: {yaml_emit(value)}")
            first = False
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def cache_matches(
    entries: list[dict[str, str]], address: str, repo: str | None
) -> list[dict[str, str]]:
    drive, name, env = parse_address(address)
    hits = []
    for e in entries:
        if repo and e.get("repo") and Path(e["repo"]).resolve() == Path(repo).resolve():
            hits.append(e)
            continue
        if not e.get("address"):
            continue
        e_drive, e_name, e_env = (
            parse_address(e["address"]) if ADDRESS_RE.match(e["address"]) else (None, None, None)
        )
        if (e_drive, e_name) == (drive, name) and (env is None or e_env in (None, env)):
            hits.append(e)
    return hits


# --- ledger and outbox ---------------------------------------------------------


def ledger_row(status: str, address: str, ident: str, intent: str | None) -> str:
    arrow = STATUS_ARROW[status]
    ts = now_utc()
    if status == "failed":
        return f'- {ts} {arrow} {address}: "{ident}"' + (f" — {intent}" if intent else "")
    if status == "received":
        return f"- {ts} {arrow} {address}: {ident}"
    body = f"- {ts} {arrow} {address}"
    if intent:
        body += f" — {intent}"
    if status == "queued":
        return body + f" — {ident}"
    return body + f" — msg {ident}"


def outbox_file(local: Path, drive: str, repo: str, env: str | None) -> Path:
    return local / "outbox" / (address_str(drive, repo, env).replace("/", "-") + ".md")


ENTRY_RE = re.compile(
    r"^## (?P<ts>\S+) → (?P<addr>\S+) · status: (?P<status>\S+) · kind: (?P<kind>\S+) · supersedes: (?P<sup>\S+) · id: (?P<id>[0-9a-f]{8})$"
)


def read_outbox(path: Path) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    if not path.exists():
        return entries
    current: dict[str, str] | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        m = ENTRY_RE.match(line)
        if m:
            current = dict(m.groupdict(), body="")
            entries.append(current)
        elif current is not None:
            current["body"] += line + "\n"
    return entries


def set_outbox_status(path: Path, entry_id: str, status: str) -> bool:
    if not path.exists():
        return False
    changed = False
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = ENTRY_RE.match(line)
        if m and m.group("id") == entry_id:
            line = line.replace(f"· status: {m.group('status')} ·", f"· status: {status} ·")
            changed = True
        out.append(line)
    if changed:
        path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return changed


# --- subcommands --------------------------------------------------------------


def cmd_self(a: argparse.Namespace) -> int:
    root = Path(a.root).resolve() if a.root else toplevel()
    for key, value in self_identity(root, a.operator).items():
        print(f"{key}={value}")
    return 0


def cmd_resolve(a: argparse.Namespace) -> int:
    repo, env = split_env(a.repo)
    rows = resolve(a.drive.lower(), repo, env, a.operator)
    for address, root, label, how in rows:
        print(f"{address}\t{root}\t{label} ({how})")
    if not rows:
        print(
            f"alemax_addr: no clone of {address_str(a.drive.lower(), repo, env)} under /Volumes/{a.drive.upper()}/Users/{a.operator}/{{claude-code/*,upstream/github.com/*,Applications}}",
            file=sys.stderr,
        )
        return 1
    if len(rows) > 1:
        print(
            f"alemax_addr: ambiguous — {len(rows)} clones match {a.drive.lower()}/{repo}; the bare address is illegal here, address one with @prod or @dev",
            file=sys.stderr,
        )
        return 2
    return 0


def cmd_cache(a: argparse.Namespace) -> int:
    root = Path(a.root).resolve() if a.root else toplevel()
    path = local_dir(root, write=(a.op == "set")) / "sessions.yaml"
    header, entries = read_cache(path)
    if a.op == "get":
        hits = cache_matches(entries, a.address, a.repo)
        # Callers take the first hit. File order put three dead rows ahead of the live
        # one, so the first hit was a socket that had stopped answering four days ago.
        hits.sort(key=lambda e: e.get("dead") == "true")
        for e in hits:
            print("- " + "\n  ".join(f"{k}: {yaml_emit(v)}" for k, v in e.items()))
        # A row whose address fails ADDRESS_RE is skipped by cache_matches, so a typo
        # makes a row invisible rather than wrong: the operator is told there is no
        # entry for an address they can see in the file. Name it instead.
        for e in entries:
            if (addr := e.get("address")) and not ADDRESS_RE.match(addr):
                print(
                    f"alemax: ignoring cache row with unparseable address {addr!r} "
                    f"— expected <drive>/<repo>[@prod|@dev]",
                    file=sys.stderr,
                )
        return 0 if hits else 1
    parse_address(a.address)
    fields: dict[str, str] = {"address": a.address}
    for kv in a.fields:
        if "=" not in kv:
            die(f"expected key=value, got {kv!r}")
        k, v = kv.split("=", 1)
        fields[k.strip()] = v
    fields.setdefault("verified_at", now_utc())
    # A row marked dead is history: it holds the socket that stopped answering and the
    # note saying why. Upserting a fresh probe onto it produced a row that claimed to be
    # live and dead at once, kept the stale `to:`, and carried a new verified_at — a
    # wrong route wearing a fresh timestamp. Unless this set is itself declaring a death,
    # a dead row is never the target; the probe becomes a new row beside it.
    target = None
    for e in entries:
        if e.get("dead") == "true" and "dead" not in fields:
            continue
        same_repo = (
            fields.get("repo")
            and e.get("repo")
            and Path(e["repo"]).resolve() == Path(fields["repo"]).resolve()
        )
        if same_repo or (not fields.get("repo") and e.get("address") == a.address):
            target = e
            break
    if target is None:
        entries.append(fields)
    else:
        target.update(fields)
    write_cache(path, header, entries)
    print(f"cached {a.address} → {path}")
    return 0


def cmd_log(a: argparse.Namespace) -> int:
    root = Path(a.root).resolve() if a.root else toplevel()
    path = local_dir(root, write=True) / "sent.md"
    if not path.exists():
        path.write_text("# Sent\n\n", encoding="utf-8")
    row = ledger_row(a.status, a.address, a.ident, a.intent)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(row + "\n")
    print(row)
    return 0


def cmd_queue(a: argparse.Namespace) -> int:
    root = Path(a.root).resolve() if a.root else toplevel()
    repo, env = split_env(a.repo)
    drive = a.drive.lower()
    rows = resolve(drive, repo, env, a.operator)
    if len(rows) > 1:
        die(
            f"ambiguous — {len(rows)} clones match {drive}/{repo}; queue to one with @prod or @dev",
            2,
        )
    if rows:
        env = rows[0][2]
    me = self_identity(root, a.operator)
    if me["env"] == "dev" and env == "prod" and a.kind not in ("question", "proposal"):
        die(
            "a dev clone sends a prod clone questions and proposals only — nothing that has dev's denials executed by prod's hands (kind must be question or proposal)",
            3,
        )
    if me["address"] == address_str(drive, repo, env) or (rows and rows[0][1] == Path(me["root"])):
        die("that address is this clone", 1)
    try:
        text = Path(a.file).read_text(encoding="utf-8") if a.file else sys.stdin.read()
    except OSError as exc:
        die(f"cannot read envelope: {exc}")
    if not text.strip():
        die("empty envelope — pass --file or pipe the envelope on stdin")
    local = local_dir(root, write=True)
    path = outbox_file(local, drive, repo, env)
    path.parent.mkdir(exist_ok=True)
    entry_id = secrets.token_hex(4)
    address = address_str(drive, repo, env)
    if a.supersedes:
        set_outbox_status(path, a.supersedes, "superseded")
    header = f"## {now_utc()} → {address} · status: queued · kind: {a.kind} · supersedes: {a.supersedes or 'none'} · id: {entry_id}"
    with path.open("a", encoding="utf-8") as fh:
        if path.stat().st_size == 0:
            fh.write(
                f"# Outbox → {address} (pull: the peer reads this file; nothing is written into its repo)\n\n"
            )
        fh.write(header + "\n\n" + text.rstrip("\n") + "\n\n")
    print(f"queued → {address} — {path} — id {entry_id}")
    return 0


def cmd_mark(a: argparse.Namespace) -> int:
    root = Path(a.root).resolve() if a.root else toplevel()
    repo, env = split_env(a.repo)
    path = outbox_file(local_dir(root, write=True), a.drive.lower(), repo, env)
    if not set_outbox_status(path, a.id, a.status):
        die(f"no entry {a.id} in {path}")
    print(f"{a.id} → {a.status} in {path}")
    return 0


def cmd_inbox(a: argparse.Namespace) -> int:
    root = Path(a.root).resolve() if a.root else toplevel()
    me = self_identity(root, a.operator)
    names = {f"{me['drive']}-{me['repo']}.md", f"{me['drive']}-{me['repo']}@{me['env']}.md"}
    peers: dict[Path, None] = {}
    _, entries = read_cache(local_dir(root) / "sessions.yaml")
    for e in entries:
        if e.get("repo") and e.get("foreign", "false") != "true":
            peers.setdefault(Path(e["repo"]), None)
    for p in a.peer:
        peers.setdefault(Path(p), None)
    peers.pop(root, None)
    peers.pop(Path(me["root"]), None)
    shown = 0
    for peer in peers:
        for name in sorted(names):
            for entry in read_outbox(peer / ".local" / "outbox" / name):
                if entry["status"] != "queued":
                    continue
                shown += 1
                print(
                    f"## from {peer} · {entry['ts']} · kind: {entry['kind']} · supersedes: {entry['sup']} · id: {entry['id']}"
                )
                print(entry["body"].rstrip("\n") + "\n")
    if not shown:
        print(f"no queued messages for {me['address']} in {len(peers)} peer outbox(es)")
    return 0


# --- main -----------------------------------------------------------------------


def register(ap: argparse.ArgumentParser) -> None:
    ap.add_argument("--root", help="repo toplevel (default: git rev-parse --show-toplevel)")
    ap.add_argument(
        "--operator",
        default=default_operator(),
        help="operator account (default: basename of $HOME)",
    )
    sub = ap.add_subparsers(dest="subcommand", required=True, metavar="SUBCOMMAND")

    sub.add_parser("self", help="this clone's address").set_defaults(func=cmd_self)

    s = sub.add_parser("resolve", help="candidate clone roots for <drive> <repo>[@env]")
    s.add_argument("drive")
    s.add_argument("repo")
    s.set_defaults(func=cmd_resolve)

    s = sub.add_parser("cache", help="read or upsert .local/sessions.yaml")
    s.add_argument("op", choices=("get", "set"))
    s.add_argument("address", help="<drive>/<repo>[@env]")
    s.add_argument("fields", nargs="*", help="key=value pairs (set)")
    s.add_argument("--repo", help="match by clone root instead of address (get)")
    s.set_defaults(func=cmd_cache)

    s = sub.add_parser("log", help="append a ledger row to .local/sent.md from the tool result")
    s.add_argument("status", choices=sorted(STATUS_ARROW))
    s.add_argument("address", help="<drive>/<repo>[@env] (session name in parentheses is fine)")
    s.add_argument("ident", help="message id, reason text (failed), or reply text (received)")
    s.add_argument("--intent", help="the one-line intent")
    s.set_defaults(func=cmd_log)

    s = sub.add_parser(
        "queue", help="write the envelope to this clone's .local/outbox/ (pull fallback)"
    )
    s.add_argument("drive")
    s.add_argument("repo", help="<repo>[@env]")
    s.add_argument("--kind", choices=KINDS, default="instruction")
    s.add_argument("--supersedes", help="id of an earlier outbox entry this one replaces")
    s.add_argument("--file", help="envelope file (default: stdin)")
    s.set_defaults(func=cmd_queue)

    s = sub.add_parser("mark", help="set an outbox entry's status")
    s.add_argument("drive")
    s.add_argument("repo", help="<repo>[@env]")
    s.add_argument("id")
    s.add_argument("status", choices=OUTBOX_STATUSES)
    s.set_defaults(func=cmd_mark)

    s = sub.add_parser("inbox", help="read peers' outboxes addressed to this clone (read-only)")
    s.add_argument(
        "--peer", action="append", default=[], help="a peer clone root to read (repeatable)"
    )
    s.set_defaults(func=cmd_inbox)
