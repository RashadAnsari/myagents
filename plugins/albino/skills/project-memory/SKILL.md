---
name: project-memory
description: Use the project-memory MCP server to retrieve, verify, and store durable project knowledge before and after non-trivial work.
---

# Project Memory

Use project memory for non-trivial project work. Memory is indexed notes, not authority: current user instructions, repo files, tests, and official docs override memory.

## Start Of Task

1. Read `memory://project/current/brief` when available.
2. Call `memory.search` with task-specific terms, file names, domains, and likely concepts.
3. Use returned memory to guide investigation, then verify against the repo before acting.
4. If memory mentions another checkout path for the same git remote, use `memory.possible_project_matches` and only link paths with `memory.link_project_paths` when explicitly appropriate.

## End Of Task

Store only durable, reusable knowledge:

- Project conventions
- Decisions that affect future implementation
- Architecture facts that are hard to rediscover
- Repeated gotchas or recurring bug root causes
- Important user preferences
- Non-obvious setup or workflow details

Do not store:

- Secrets, tokens, credentials, cookies, private keys, or `.env` values
- Routine command output
- Temporary task state
- Vague summaries like "fixed the issue"
- One-off chatter
- Facts already obvious from `AGENTS.md`, `README.md`, or nearby code unless the memory adds durable interpretation

When storing memory, include `whyUsefulLater`. If you cannot explain why a future agent needs it, do not store it.

## Stale Or Conflicting Memory

If memory conflicts with the repo, the repo wins. Update stale memory with `memory.update` or archive it with `memory.forget`. Preserve useful source references when correcting memory.
