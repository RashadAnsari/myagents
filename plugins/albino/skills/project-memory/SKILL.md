---
name: project-memory
description: Use the project-memory MCP server to retrieve, verify, and store durable project knowledge and global user knowledge before and after non-trivial work.
---

# Project Memory & User Memory

Two parallel memory systems are available. Both are indexed notes, not authority: current user instructions, repo files, tests, and official docs always override memory.

---

## User Memory (Global)

User memory is cross-project. It captures stable facts about the person you are working with: their preferences, behaviors, background, and style. Read it at the start of every session; update it when you observe something durable and new.

### Start Of Session

1. Read `memory://user/brief` to load preferences, behaviors, and context.
2. Call `user.search` for terms relevant to the current task or domain.
3. Apply what you learn — respect stated preferences, adapt to known workflows.

### End Of Session

Store only stable, cross-project facts:

- Consistent preferences (language, style, formatting, tools)
- Recurring behavioral patterns
- Background context (role, team, domain, experience level)
- Global conventions the user applies everywhere
- Preferred tools, frameworks, or configurations
- Communication and explanation style

**User memory kinds:** `preference`, `behavior`, `context`, `workflow`, `convention`, `tool_preference`, `communication`

Do not store:

- Anything project-specific — use project memory instead
- Secrets, credentials, or `.env` values
- Temporary opinions or one-off task details
- Vague notes without a clear future use

### Stale User Memory

If observed behavior contradicts a stored user memory, update it with `user.update` or archive it with `user.forget`.

---

## Project Memory (Per-Project)

Use project memory for non-trivial work on a specific codebase.

### Start Of Task

1. Read `memory://project/current/brief` when available.
2. Call `memory.search` with task-specific terms, file names, domains, and likely concepts.
3. Use returned memory to guide investigation, then verify against the repo before acting.
4. If memory mentions another checkout path for the same git remote, use `memory.possible_project_matches` and only link paths with `memory.link_project_paths` when explicitly appropriate.

### End Of Task

Store only durable, reusable knowledge:

- Project conventions
- Decisions that affect future implementation
- Architecture facts that are hard to rediscover
- Repeated gotchas or recurring bug root causes
- Important user preferences specific to this project
- Non-obvious setup or workflow details

**Project memory kinds:** `decision`, `convention`, `architecture`, `workflow`, `preference`, `gotcha`, `bug`, `dependency`, `testing`, `handoff`

Do not store:

- Secrets, tokens, credentials, cookies, private keys, or `.env` values
- Routine command output
- Temporary task state
- Vague summaries like "fixed the issue"
- One-off chatter
- Facts already obvious from `AGENTS.md`, `README.md`, or nearby code unless the memory adds durable interpretation

When storing memory, include `whyUsefulLater`. If you cannot explain why a future agent needs it, do not store it.

### Stale Or Conflicting Memory

If memory conflicts with the repo, the repo wins. Update stale memory with `memory.update` or archive it with `memory.forget`. Preserve useful source references when correcting memory.
