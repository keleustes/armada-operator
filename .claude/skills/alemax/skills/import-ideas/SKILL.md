---
name: import-ideas
description: Use after dictating ideas on mobile and wanting to triage them on the desktop. Drain an Obsidian vault of mobile-captured ideas — `alemax vault` resolves the vault (`users.yaml ideas_on_the_go_vault`, else Obsidian's iCloud container), walks it for `ideas-on-the-go(-{project})?.md`, routes each file by its filename (cross-cutting → canonical claude-meta · existing-project → that project · unknown → offer to bootstrap it), lists the pending rows, and rewrites each consumed row atomically. Per row the only question is import or skip-personal; the filename already decided the route.
license: MIT
compatibility: Requires git, gh, and `uv`. No yq. Meta-repo clone, or a project clone with `--only <project>`.
context: claude-meta-only
argument-hint: "[--dry-run] [--only <project>]"
allowed-tools: Bash(uv run --directory plugins/alemax alemax vault *)
metadata:
  author: alemax
  reviewed_model: claude-5
  reviewed: 2026-11-04
---

## Wraps

`alemax vault` — `annotate`, `scan`, `vault`. Run it from the repo root as
`uv run --directory plugins/alemax alemax vault <subcommand> …`. `--help` documents every flag.

Exit codes, branching and the reasoning behind each rule are in spec `mobile-capture`
and the module's own docstrings. This body carries what a session must decide, and what
to report — restating the code here is how the two drift.

## Context

`claude-meta-only`, because a full run reads `projects.yaml` and routes to several repos.
`--only <project>` relaxes that: from a project clone it drains just that project's
`ideas-on-the-go-<project>.md` — the file `init-project.sh` seeds into the vault.

## Steps

1. **`vault`.** It resolves the vault from `users.yaml`, else Obsidian's iCloud container, and
   says which. A vault it cannot find is reported, never guessed at.
2. **`scan --json`.** Each file routes by its filename: cross-cutting goes to canonical, a
   `-<project>` suffix goes to that project. A suffix naming a project not in the manifest is a
   question for the operator, not a silent drop.
3. **Show the routing table and confirm.** The operator sees where every idea will land before
   anything is written. Files captured on mobile are terse; ask rather than expand them yourself.
4. **Land them** — canonical ideas by PR (Guardrail 2), project ideas in that project's own
   `openspec/ideas.md`.
5. **`annotate`, only after they have landed.** A vault file marked imported that never arrived
   is lost, and the phone is the only other copy.

## Not for

Deleting or reorganising vault files — this only flips `- [ ]` to `- [x]` in place, and never
touches a row it did not import. Draining a project's file from meta and *applying* it there:
routing writes to that project's clone through its own PR, and nothing here commits to a
project's `main` (Guardrail 4). A row whose PR never opened stays pending — that is what makes a
re-run safe, so never stamp ahead of the PR.
