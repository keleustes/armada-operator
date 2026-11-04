---
name: alemax-mattermost-send-msg
description: "Use when the target is on another Mac or another operator, or when the user should see the message in the channel. Send a message to one or more other sessions through Mattermost as this folder’s own account — named targets or every volume’s claude-meta — and report only that it was posted: live delivery depends on each target volume’s relay."
license: MIT
metadata:
  author: alemax
  version: "2.0"
  source_reviewed_model: claude-5
  source_reviewed: 2026-10-04
---

## Working directory

Keep the working directory at the repository being operated on; every command below runs from
its root. `alemax` is the packaged CLI under `plugins/alemax/`.

## Wraps

`alemax presence send`, run as
`uv run --directory plugins/alemax alemax presence send --to <targets> [--all-meta] [--thread <root>] "<message>"`.
Target resolution and refusals are in spec `mattermost-relay`.

## Steps

1. **Send.** Pass the targets and the message as given. A refusal names the account it refuses,
   unknown or this folder's own; nothing was posted.
2. **Report only what the result supports**: the message is posted, with its thread. It is
   delivered live only where the target's volume runs its relay; otherwise on the target's next
   read. Never say "delivered".
3. **Follow up in the same thread** with `--thread <root>`.

## Report

The targets, the thread id, and that it was posted — live where the target's relay runs,
otherwise on its next read.
