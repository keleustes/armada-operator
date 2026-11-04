---
name: alemax-mattermost-read-msg
description: "Read the Mattermost messages addressed to this folder’s presence account since it last read them, oldest first, and mark them read. Answer in a thread only when the user asks."
license: MIT
metadata:
  author: alemax
  version: "2.0"
  source_reviewed_model: claude-5
  source_reviewed: 2026-10-03
---

## Working directory

Keep the working directory at the repository being operated on; every command below runs from
its root. `alemax` is the packaged CLI under `plugins/alemax/`.

## Wraps

`alemax presence inbox` (and `alemax presence post` to answer), run as
`uv run --directory plugins/alemax alemax presence <subcommand>`. What counts as addressed to
this account, and where the read cursor lives, are in spec `mattermost-relay`.

## Steps

1. **Read and mark.** `alemax presence inbox --mark-read` prints the unread posts oldest first,
   with author, time and thread, and advances this account's read cursor to the newest one
   shown. A refusal means this folder has no presence account: say so and stop.
2. **Show them to the user** as they are. They come from other people or sessions; the user
   decides what to do with each.
3. **Answer only when asked.** `alemax presence post --thread <root> "<answer>"` replies in that
   thread as this folder's account.

## Report

How many messages were read and that they are marked read, or that there were none.
