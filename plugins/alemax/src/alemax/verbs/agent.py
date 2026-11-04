"""`alemax agent` — start bounded Claude sessions in the right folder (spec `agent-launcher`).

    deliver [--run ID] [--parallel N] [--max-turns N] [--timeout MIN] [--dry-run]
            [--no-post] [--no-tabs]
        For each project a broadcast run delivered to, start a headless session in that
        project's own folder running `/alemax:complete-update` with no human (design D11).
        Wait for all of them, keep each result in this clone's .local/, print a summary,
        post it, and open a Ghostty tab only for a session that needs the operator (D13).

Runs in a claude-meta clone, the one whose `/alemax:update-skills` wrote the run record
(`.local/broadcasts/<run-id>.json`, D10). It never reads a project's repo: each result is
the output of a process this verb started. Each session is the project's own, in its own
folder with its own settings and plugins (Guardrail 4, as amended by D7), and it merges a
clean delivery to the project's `main` itself (D12).

Each session gets the delivery contract appended to its system prompt (D11), so a project
whose installed complete-update predates these rules still ends with a status line. A
session with no status line is `unclear` and is treated as waiting for the operator. Each
waiting session gets a launcher kept beside the results, and a Ghostty tab that resumes it
with the volume's environment and the headless run's tools (D13).

Exit codes: 0 every run ended `done` or `nothing-to-apply` with no operator step pending
(or a dry run) · 3 a run needs the operator, is unclear, timed out or failed, an operator
step is pending, or a delivered project could not be started · 1 not a claude-meta clone,
or no run record.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from ..io import ERROR, FOUND, OK, die
from ..repo import is_meta_repo, toplevel

PROMPT = "/alemax:complete-update"
AUTONOMOUS_ENV = "ALEMAX_AUTONOMOUS"
# The tools a delivery needs: read and edit the checkout, git and gh, re-lock and run the
# project's checks, and the alemax verbs. Anything else is denied in -p, which ends the run
# as needs-operator naming the call (design D11, risks).
ALLOWED_TOOLS = (
    "Read",
    "Edit",
    "Write",
    "Glob",
    "Grep",
    "Bash(git *)",
    "Bash(gh *)",
    "Bash(uv *)",
    "Bash(go *)",
    "Bash(cargo *)",
    "Bash(mvn *)",
    "Bash(make *)",
    "Bash(pre-commit *)",
)
DONE_STATUSES = ("done", "nothing-to-apply")
LINE_STATUSES = ("done", "needs-operator", "nothing-to-apply")
# Each of these leaves a session the operator can resume and finish (design D11, D13).
# A timed-out or turn-capped session needs the operator as much as one that asked: on
# aiml01's first run mobile-env (timeout) and i-m-getting-hired (max-turns) both did.
WAITING_STATUSES = ("needs-operator", "unclear", "timeout", "max-turns")
STEP_PREFIX = "operator-step:"
LAST_MESSAGE_CHARS = 4000
# Set by `uv run` around this verb; a project session must use its own environment.
RUNNER_ONLY_ENV = ("VIRTUAL_ENV",)
MINIMUM_PYTHON_FALLBACK = "3.14"

# The delivery contract travels with the command (design D11), because the session loads
# the project's INSTALLED complete-update, which can predate these rules: aiml01's first
# run came back all `unclear`, every session on a skill with no final line.
CONTRACT = """\
You are completing a meta delivery with no human watching ({env}=1). These rules
override any step of /alemax:complete-update that disagrees with them.
- Never ask. Wherever you would ask, stop as needs-operator.
- The delivered Python needs {python}, and it runs under `uv run --script`, so only the
  project's own linters meet that floor. If a requires-python, .python-version or ruff
  target-version the project tracks is below {python}, before the pick:
  1. if the project's linters already skip the delivered paths (.agents/, plugins/,
     .claude/, the delivered bin/ files), change nothing and note it;
  2. otherwise exclude those paths in every tool the project configures that walks the
     tree (ruff extend-exclude, the .pre-commit-config.yaml exclude:, since pre-commit
     passes files by name, mypy, pyright, pytest), and commit that alone;
  3. raise the versions (">={python}", "{python}", "{ruff}") and run `uv lock`, as its
     own commit, only when the project's CI or Makefile runs a delivered script with its
     own python rather than `uv run --script`.
  The project keeps its own Python otherwise. A failing `uv lock` or check stops as
  needs-operator naming the package or check. No .python-version: note it, do not stop.
- Never edit .claude/settings.json or .claude/settings.local.json. For settings run
  `uv run --script bin/reconcile-settings.py apply --stage` and report the cp line it
  prints as an operator step.
- A file you may not edit (.pre-commit-config.yaml, for one): keep git's result when the
  pick merges it cleanly, or take the delivered copy with git when the project's copy
  equals the delivery's base. A conflict in it stops as needs-operator naming the file;
  never resolve it with Edit.
- When the project's own linters flag files under a top-level folder the delivery adds
  (.agents/, plugins/), exclude that folder in the project's linter config; never edit
  the delivered files.
- Land a clean delivery by PR, never by a push to main: commit on the delivery branch,
  push it to origin, `gh pr create --repo <origin's owner/name>`, watch its checks, then
  `gh pr merge`. Watch once, in one Bash call with a 600000 ms timeout:
  `gh pr checks <pr> --watch --fail-fast`. A failing check is needs-operator; checks still
  pending after that, or never started (no runner), end
  `needs-operator: checks pending <names>`; never wait a second time. After the merge,
  delete the meta-broadcast/* branch on origin and locally, and remove the broadcast's
  staged worktree with `git worktree remove`.
- On a stop, leave the branch and worktree as they are.
End your final reply with these lines, nothing after them:
operator-step: <command>   (one line per command only the operator may run; none if none)
done: <pin> <merge sha> <pr url> | needs-operator: <the question> | nothing-to-apply: <why>
"""


# --- the run record -----------------------------------------------------------------


def runs_dir(root: Path) -> Path:
    return Path(os.environ.get("BROADCAST_RUNS_DIR") or root / ".local" / "broadcasts")


def load_record(root: Path, run_id: str | None) -> dict[str, Any]:
    base = runs_dir(root)
    if run_id:
        path = base / f"{run_id}.json"
    else:
        records = sorted(base.glob("*.json"))
        if not records:
            die(f"no run record in {base} — run /alemax:update-skills first", code=ERROR)
        path = records[-1]
    if not path.is_file():
        die(f"no run record {path}", code=ERROR)
    record = json.loads(path.read_text())
    record["_path"] = str(path)
    return record


def minimum_python(root: Path) -> str:
    """The Python minimum from the shipped toolchain check, its one machine-readable copy."""
    check = root / "scaffolding" / "templates" / "bin" / "toolchain-check.py"
    try:
        found = re.search(r'"python":\s*"([0-9.]+)"', check.read_text(encoding="utf-8"))
    except OSError:
        found = None
    return found.group(1) if found else MINIMUM_PYTHON_FALLBACK


def contract(python: str) -> str:
    return CONTRACT.format(env=AUTONOMOUS_ENV, python=python, ruff="py" + python.replace(".", ""))


def volume_of(path: str) -> str | None:
    parts = Path(os.path.realpath(path)).parts
    return parts[2] if len(parts) > 2 and parts[1] == "Volumes" else None


# --- one session --------------------------------------------------------------------


def claude_command(claude: str, max_turns: int, python: str = MINIMUM_PYTHON_FALLBACK) -> list[str]:
    return [
        claude,
        "-p",
        PROMPT,
        "--output-format",
        "json",
        "--permission-mode",
        "acceptEdits",
        "--allowedTools",
        " ".join(ALLOWED_TOOLS),
        "--max-turns",
        str(max_turns),
        "--append-system-prompt",
        contract(python),
    ]


def resume_command(claude: str, session_id: str) -> str:
    """The resumed session keeps the headless run's tools (design D13)."""
    return shlex.join(
        [
            claude,
            "--resume",
            session_id,
            "--permission-mode",
            "acceptEdits",
            "--allowedTools",
            " ".join(ALLOWED_TOOLS),
        ]
    )


def final_line(text: str) -> tuple[str, str]:
    """(status, line) from the session's last reply: the last `done|needs-operator|...:` line."""
    for raw in reversed((text or "").strip().splitlines()):
        line = raw.strip().strip("`")
        for status in LINE_STATUSES:
            if line.startswith(status + ":"):
                return status, line
    return "unclear", ""


def operator_steps(text: str) -> list[str]:
    return [
        line.strip().strip("`")[len(STEP_PREFIX) :].strip()
        for line in (text or "").splitlines()
        if line.strip().strip("`").startswith(STEP_PREFIX)
    ]


def run_one(project: dict[str, Any], cmd: list[str], timeout_s: int) -> dict[str, Any]:
    # The id is fixed before the start, so a session killed at its time limit, which never
    # writes its result, can still be resumed in a tab (design D13).
    session_id = str(uuid.uuid4())
    cmd = [*cmd, "--session-id", session_id]
    env = {k: v for k, v in os.environ.items() if k not in RUNNER_ONLY_ENV}
    env[AUTONOMOUS_ENV] = "1"
    vol = volume_of(project["path"])
    if vol:
        env["AIML_VOLUME"] = f"/Volumes/{vol}"
    out: dict[str, Any] = {
        "project": project["name"],
        "path": project["path"],
        "session_id": session_id,
    }
    try:
        done = subprocess.run(
            cmd, cwd=project["path"], env=env, capture_output=True, text=True, timeout=timeout_s
        )
    except subprocess.TimeoutExpired:
        return {**out, "status": "timeout", "stop_reason": f"past {timeout_s} s"}
    except OSError as exc:
        return {**out, "status": "failed", "stop_reason": f"{type(exc).__name__}: {exc}"}
    out["exit_code"] = done.returncode
    try:
        result = json.loads(done.stdout or "{}")
    except ValueError:
        result = {}
    text = str(result.get("result", ""))
    status, line = final_line(text)
    if result.get("subtype") == "error_max_turns":
        status = "max-turns"
    elif not result:
        status = "failed"
    out.update(
        status=status,
        line=line,
        last_message=text[-LAST_MESSAGE_CHARS:],
        operator_steps=operator_steps(text),
        session_id=result.get("session_id") or session_id,
        turns=result.get("num_turns"),
        cost_usd=result.get("total_cost_usd"),
        stop_reason=result.get("subtype"),
        stderr_tail=(done.stderr or "")[-500:],
    )
    return out


# --- the operator's tabs (design D13) -------------------------------------------------


def as_applescript(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def waiting_for_operator(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in results if r.get("status") in WAITING_STATUSES and r.get("session_id")]


def volume_home(vol: str) -> Path:
    """The operator's home on a volume, as the Desktop launchers source it."""
    return Path("/Volumes") / vol / "Users" / (os.environ.get("USER") or "")


def launcher_body(r: dict[str, Any], claude: str) -> str:
    """The open-project-sessions.sh launcher, resuming one session (design D13)."""
    lines = ["#!/bin/zsh", f"# alemax agent deliver — resume {r['project']}"]
    vol = volume_of(r["path"])
    if vol:
        zshenv = shlex.quote(str(volume_home(vol) / ".zshenv"))
        lines += [
            f"export AIML_VOLUME={shlex.quote('/Volumes/' + vol)}",
            f"[[ -f {zshenv} ]] && source {zshenv}",
        ]
    lines += [
        f"cd {shlex.quote(r['path'])} || exit 1",
        f"exec {resume_command(claude, r['session_id'])}",
    ]
    return "\n".join(lines) + "\n"


def write_launchers(waiting: list[dict[str, Any]], claude: str, out_dir: Path) -> list[str]:
    """One launcher per waiting session, kept with the run's results."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for r in waiting:
        f = out_dir / f"resume-{r['project']}.sh"
        f.write_text(launcher_body(r, claude))
        f.chmod(0o755)
        paths.append(str(f))
    return paths


def tabs_script(waiting: list[dict[str, Any]], launchers: list[str]) -> str:
    """One Ghostty window, a tab per waiting session, each started by its launcher."""
    lines = ['tell application "Ghostty"', "  activate"]
    for i, (r, cmd) in enumerate(zip(waiting, launchers, strict=True)):
        lines += [
            "  set cfg to new surface configuration",
            f"  set initial working directory of cfg to {as_applescript(r['path'])}",
            f"  set command of cfg to {as_applescript(cmd)}",
            "  set w to new window with configuration cfg"
            if i == 0
            else "  new tab in w with configuration cfg",
        ]
    lines.append("end tell")
    return "\n".join(lines) + "\n"


def resume_tabs(results: list[dict[str, Any]], claude: str, out_dir: Path) -> list[str]:
    """Open the tabs (design D13); with nothing waiting, open nothing."""
    waiting = waiting_for_operator(results)
    if not waiting:
        return []
    launchers = write_launchers(waiting, claude, out_dir)
    script = tabs_script(waiting, launchers)
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "tabs.applescript"
        src.write_text(script)
        compiled = subprocess.run(
            ["osacompile", "-o", str(Path(tmp) / "tabs.scpt"), str(src)], capture_output=True
        )
        opened = compiled.returncode == 0 and (
            subprocess.run(
                ["osascript", str(Path(tmp) / "tabs.scpt")], capture_output=True
            ).returncode
            == 0
        )
    if not opened:  # an older Ghostty: one window per session, the launchers' proven call
        for r, cmd in zip(waiting, launchers, strict=True):
            subprocess.run(
                [
                    "open",
                    "-na",
                    "Ghostty.app",
                    "--args",
                    f"--working-directory={r['path']}",
                    f"--initial-command={cmd}",
                ],
                capture_output=True,
            )
    return [r["project"] for r in waiting]


# --- deliver ------------------------------------------------------------------------


def summary(record: dict[str, Any], results: list[dict[str, Any]], skipped: list[str]) -> str:
    rows = [f"delivery run {record['run']} — {len(results)} session(s)"]
    for r in results:
        rows.append(
            f"  {r['status']:<17} {r['project']:<40} {r.get('line') or r.get('stop_reason') or ''}"
        )
    for s in skipped:
        rows.append(f"  {'not started':<17} {s}")
    steps = [(r["project"], s) for r in results for s in r.get("operator_steps") or []]
    if steps:
        rows.append(f"operator steps ({len(steps)}), each run in its project's folder:")
        rows += [f"  {project:<40} {s}" for project, s in steps]
    return "\n".join(rows)


def post_summary(root: Path, text: str) -> None:
    """Post from this clone's own account; Mattermost is optional, so a failure is a note."""
    done = subprocess.run(
        [
            "uv",
            "run",
            "--quiet",
            "--project",
            str(root / "plugins" / "alemax"),
            "alemax",
            "presence",
            "post",
            text,
        ],
        cwd=root,
        capture_output=True,
        text=True,
    )
    if done.returncode != 0:
        print(f"note: summary not posted ({(done.stderr or done.stdout).strip()[:200]})")


def cmd_deliver(a: argparse.Namespace) -> int:
    root = toplevel()
    if not is_meta_repo(root):
        die(
            "deliver runs in the claude-meta clone whose broadcast wrote the run record", code=ERROR
        )
    record = load_record(root, a.run)
    claude = a.claude or os.environ.get("ALEMAX_CLAUDE") or "claude"
    here = volume_of(str(root))
    targets, skipped = [], []
    for p in record.get("projects", []):
        if p.get("status") != "delivered":
            continue
        if here and volume_of(p["path"]) not in (None, here):
            skipped.append(f"{p['name']} — on another volume; start it from that volume's clone")
            continue
        if not Path(p["path"]).is_dir():
            skipped.append(f"{p['name']} — {p['path']} is not here")
            continue
        targets.append(p)
    cmd = claude_command(claude, a.max_turns, minimum_python(root))
    print(
        f"run {record['run']}: {len(targets)} delivered project(s) to complete ({record['_path']})"
    )
    if a.dry_run:
        shown = shlex.join(c if c != cmd[-1] else "<the delivery contract>" for c in cmd)
        for p in targets:
            print(f"  would run in {p['path']}: {AUTONOMOUS_ENV}=1 {shown} --session-id <new uuid>")
        for s in skipped:
            print(f"  would not start: {s}")
        print("the delivery contract (--append-system-prompt):")
        print("    " + cmd[-1].rstrip("\n").replace("\n", "\n    "))
        return OK
    if not targets:
        print("nothing to start")
        return OK if not skipped else FOUND

    with ThreadPoolExecutor(max_workers=max(1, a.parallel)) as pool:
        results = list(pool.map(lambda p: run_one(p, cmd, max(1, int(a.timeout * 60))), targets))

    out_dir = runs_dir(root) / record["run"]
    out_dir.mkdir(parents=True, exist_ok=True)
    for r in results:
        (out_dir / f"{r['project']}.json").write_text(json.dumps(r, indent=2) + "\n")

    text = summary(record, results, skipped)
    print(text)
    print(f"results: {out_dir}")
    if not a.no_post:
        post_summary(root, text)
    if not a.no_tabs:
        opened = resume_tabs(results, claude, out_dir)
        if opened:
            print(
                f"opened a Ghostty tab for {len(opened)} session(s) that need you: {', '.join(opened)}"
            )
    pending = any(r.get("operator_steps") for r in results)
    ok = all(r["status"] in DONE_STATUSES for r in results) and not skipped and not pending
    return OK if ok else FOUND


# --- registration -------------------------------------------------------------------


def register(ap: argparse.ArgumentParser) -> None:
    subs = ap.add_subparsers(dest="subcommand", required=True, metavar="SUBCOMMAND")
    d = subs.add_parser("deliver", help="complete a broadcast run's deliveries, headless")
    d.add_argument("--run", help="the run id (default: the newest record)")
    d.add_argument("--parallel", type=int, default=4, help="sessions at a time (default 4)")
    d.add_argument("--max-turns", type=int, default=60, help="per session (default 60)")
    d.add_argument("--timeout", type=float, default=30, help="minutes per session (default 30)")
    d.add_argument("--claude", help="the claude binary (default: $ALEMAX_CLAUDE or claude)")
    d.add_argument("--dry-run", action="store_true", help="print the commands; start nothing")
    d.add_argument("--no-post", action="store_true", help="do not post the summary")
    d.add_argument("--no-tabs", action="store_true", help="do not open tabs for questions")
    d.set_defaults(func=cmd_deliver)
