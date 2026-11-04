---
name: mattermost-send-msg
description: "Use when the target is on another Mac or another operator, or when the operator should see the message in the channel. Send a message to one or more other sessions through Mattermost, as this folder's own account — `/alemax:mattermost-send-msg {target}[,{target}…] {message}`, a target being `@aiml01-claude-meta`, `aiml01-claude-meta` or `aiml01/claude-meta`, or `--all-meta` for every volume's claude-meta (an order such as \"aiml-tidy\" to the whole fleet). `alemax presence send` checks each target exists, posts one message mentioning them, and prints the thread. Works across Macs and operators where `SendMessage` cannot; delivery is by each target volume's relay, or on the target's next read. Optional: needs Mattermost presence on this volume."
license: MIT
compatibility: Requires `uv` and a folder provisioned with `alemax presence` (Mattermost presence; optional).
context: either
argument-hint: "<target>[,<target>…] | --all-meta <message…>"
allowed-tools: Bash(uv run --directory plugins/alemax alemax presence send *)
metadata:
  author: alemax
  reviewed_model: claude-5
  reviewed: 2026-10-04
---

## Wraps

`alemax presence send`, run from the repo root as
`uv run --directory plugins/alemax alemax presence send --to <targets> [--all-meta] [--thread <root>] "<message>"`.
Target resolution and the refusals are in spec `mattermost-relay` — not here. Same-Mac,
same-operator sessions can also be reached with `/alemax:send-msg`; this one is for every other
case, and for anything the operator should see in the channel.

## Steps

1. **Send.** Pass the targets and the message as given. A refusal names the account it refuses —
   unknown, or this folder's own — report it; nothing was posted.
2. **Report what the tool result supports, no more.** It prints the post and the thread: the
   message is **posted**. It is delivered live only where the target's volume runs its relay;
   otherwise the target reads it on its next `/alemax:mattermost-read-msg`. Never say "delivered".
3. **Follow up in the same thread** with `--thread <root>` from step 2. Answers arrive as posts
   that mention this account, through this volume's relay or the next read.

## Report

The targets, the thread id, and the sentence "posted — live where the target's relay runs,
otherwise on its next read".
