# Per-model advice — what Anthropic changed, and what it means for a CLAUDE.md or a skill here

_Fetched 2026-09-04. A **lookup**, not a rule: read the row for the model in use before rewriting an
instruction, and never rewrite one because a row exists. Advice about the repo is durable; advice about
the model is not. Delivered from claude-meta (`meta/docs/MODEL-ADVICE.md`, class M) — a local edit <!-- shipped-path-provenance -->
survives the 3-way merge, but say why in the commit or the next refresh will read as a conflict._

| model | since | what Anthropic changed | what it means for an artifact here |
|---|---|---|---|
| [Claude 5 family](https://claude.com/blog/the-new-rules-of-context-engineering-for-claude-5-generation-models) (`claude-opus-5`, `claude-fable-5-1`) | 2026-07-24 | "We removed over 80% of Claude Code's system prompt … with no measurable loss"; "our system prompt, skills, and user requests clash with each other" | A line written against the old system prompt now competes with a lean one and the model arbitrates every request. Prune what the harness already supplies — the skill and subagent rosters above all. Prune for **contradiction or redundancy, never for a token count**. |
| [Claude Fable 5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5) | current | "Skills developed for prior models are often too prescriptive for Claude Fable 5 and can degrade output quality"; a brief instruction steers most behaviours | Cut enumerated step lists from a skill body; keep the invocation and the report. Verification for long runs still stated explicitly (opposite of Opus 5, below). |
| [Claude Fable 5.1](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5-1) (`claude-fable-5-1`) | current, Claude Code ≥ 2.1.255 | Writes fewer user-facing updates than Fable 5; "audit your prompt for instructions that suppress narration … Remove lines like that before adding anything" | Remove narration-suppressing lines before asking for more narration. Do not fix or extend beyond the task; report the rest as a follow-up. |
| [Claude Opus 5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5) (`claude-opus-5`) | current | "verifies its own work without being told to … remove them"; "narrates readily … to tune narration down, describe the cadence and shape you want"; expands scope and delegates readily | Delete explicit verification steps and status scaffolding from bodies; state the cadence you want instead. Constrain scope and cap delegation for a narrow task. |
| [Claude Sonnet 5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-sonnet-5) (`claude-sonnet-5`) | current | "interprets prompts literally and explicitly … does not silently generalize"; forced interim status messages can go | State the scope explicitly — an instruction given for one item is not applied to the next. Delete "summarize every N tool calls" scaffolding. |
| [Claude Haiku 4.5](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) (`claude-haiku-4-5`) | current | Skill test matrix: "Claude Haiku … Does the Skill provide enough guidance?" | The row that pulls the other way: a body trimmed for Opus/Fable may leave Haiku without the steps. Write to the intersection and test on each model in use. |
| effort, every model | current | "effort level names don't correspond to the same amount of thinking across models" — re-run the sweep on Fable 5.1, on Opus 5 if defaults were carried over; Sonnet 5 respects the level strictly | An `effort` pin in frontmatter is model-bound. Re-check it on a model change; do not copy a level from one model's defaults to another. |
| [output length](https://code.claude.com/docs/en/output-styles), harness | Claude Code ≥ 2.1.237 | Built-in `outputStyle: "Concise"` — leads with the result, no preamble; read once at session start | The enforced brevity control is a settings key, not a CLAUDE.md line. It ships in `.claude/settings-template.json`; a "keep replies short" line in CLAUDE.md would be charged to every task and enforced by nothing. |

## How to use it

- On a model change, read the rows for the new model before touching an artifact. A session cannot
  detect a model change from the inside — the signal comes from outside.
- The row is evidence, not a verdict. This file never rewrites anything, and neither does the checker
  that names it (`bin/claude-md-check.py`).
- A ledger entry in `CLAUDE.md` admitted because one model got something wrong may carry
  `since <model-id>`; when a later model no longer makes the mistake, that is its `retire when`.
- This file is not imported by `CLAUDE.md` and costs a session nothing until it is opened. Keep it
  that way: one pointer in the routing paragraph is the whole cost.
