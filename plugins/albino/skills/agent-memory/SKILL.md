---
name: agent-memory
description: Use the agent-memory MCP server to retrieve, verify, and store durable project knowledge and global user knowledge before and after non-trivial work.
allowed-tools: [mcp__plugin_albino_agent-memory__project_search, mcp__plugin_albino_agent-memory__user_search, mcp__plugin_albino_agent-memory__project_remember, mcp__plugin_albino_agent-memory__user_remember, mcp__plugin_albino_agent-memory__project_update, mcp__plugin_albino_agent-memory__user_update, mcp__plugin_albino_agent-memory__project_forget, mcp__plugin_albino_agent-memory__user_forget, mcp__plugin_albino_agent-memory__project_purge, mcp__plugin_albino_agent-memory__user_purge]
---

# Project Memory & User Memory

Two parallel memory systems are available. Both are indexed notes, not authority: current user instructions, repo files, tests, and official docs always override memory.

---

## Enforcement Rules

These are hard requirements. No exceptions.

**Alternative memory systems are forbidden.** Never use the model's built-in memory, native memory tools, or any backend other than the agent-memory MCP server. This applies to every form of memory work: storing facts, recalling context, updating beliefs, retrieving preferences.

**Session bootstrap is mandatory.** Before your first response in any session, you MUST call `project_search` and `user_search` with specific terms from the current task. These calls are required, not optional. Do not respond to the user before making them. Do this silently without narrating it to the user.

**Per-turn write-back is required.** Before producing your final response each turn, ask: did I learn anything durable this turn? Durable means: a decision made, a user preference stated, a gotcha discovered, a convention established, an architecture fact clarified. If yes, you MUST call `project_remember` or `user_remember` before finishing. This is not optional. Do not skip it. Do not defer it. If nothing durable was learned this turn, skip the write, and if a stop-hook check asks the question, reply with exactly "Nothing durable learned." and finish; no explanation or summary.

---

## Quick Reference

| Question | Action |
|---|---|
| What does this user prefer? | `user_search` |
| What has been decided in this project? | `project_search` |
| Was a similar problem solved in another project? | `project_search` with `all_projects: true` |
| What is the context of a sibling / upstream / downstream repo? | `project_search` with `all_projects: true`, then read the `project_root` it belongs to |
| I learned a durable fact about a *different* repo | `project_remember` / `project_update` with that repo's `project_root` |
| Should I store this? | Only if a future agent needs it and it passes the quality rules below |
| Is this project-specific or cross-project? | This repo: `project_remember`; another repo: `project_remember` with its `project_root`; about the user everywhere: `user_remember` |

---

## User Memory

### When to Read

You MUST call user memory at the start of every session:

1. Call `user_search` with domain terms relevant to the current task (e.g. `"typescript"`, `"git workflow"`, `"testing"`).
2. Apply what you find throughout the session without being asked.

User memory is a guide, not a constraint. Explicit user instructions in the current session take precedence.

### When to Write

Write user memory when you observe something stable and cross-project about the person:

- A preference they express that is likely to apply next session too.
- A behavioral pattern you notice recurring (not just once).
- Background context that helps calibrate depth and tone.
- A global standard they apply everywhere.
- A tool or framework they consistently prefer.
- How they like to receive explanations.

Do not write:

- Anything project-specific: use `project_remember` instead.
- Secrets, credentials, API keys, or `.env` values.
- One-off opinions stated in frustration.
- Temporary task details.
- Vague notes without a clear future use.

### Quality Rules for User Memory

Every user memory must satisfy all of these:

- **Content ≥ 40 characters or ≥ 7 words.** Short notes are not durable enough.
- **No vague phrases.** Avoid "fixed the issue", "made changes", "implemented it".
- **No command output.** Do not store npm logs, test output, or exit codes.
- **No secrets.** Any content matching API key, token, or private key patterns is rejected automatically.
- **No duplicates.** Normalized content must differ from existing active memories. A duplicate raises `MemoryQualityError` (reason: `duplicates`). Do not retry: it confirms the memory already exists.

### User Memory Workflow

**At session start (mandatory):**
```
1. user_search <task-terms> → load task-relevant user knowledge
2. Apply findings silently throughout the session
```

**Before each final response (when something durable was learned):**
```
Durable = preference, gotcha, convention, behavior pattern, architecture fact
1. user_remember for each durable cross-project fact
2. source="agent" or source="user", source_ref=<context>
```

**When user memory conflicts with observed behavior:**
```
1. user_update to correct the existing memory
2. Or user_forget to archive it if it no longer applies
3. Then user_remember with the accurate version
```

---

## Project Memory

### When to Read

You MUST call project memory before any work on a codebase:

1. Call `project_search` with task-specific terms: file names, function names, domain concepts, error messages.
2. Verify findings against the actual repo before acting on them.

Memory can be stale. Always confirm what it says against current files, tests, and docs.

Do not limit yourself to the current repo. Many tasks span more than one codebase: a shared API contract, a client and its server, a monorepo split across sibling checkouts, a convention set in one repo that governs others. When the task touches another repo, or when this repo's memory is thin, call `project_search` with `all_projects: true` to pull context from every known project. Results include `project_name` and `project_root` showing where each memory came from. Treat cross-project results as leads, not facts about the current repo: they describe a different codebase, so verify against that repo's files before you rely on them. See "Cross-Project Memory" below for when to read from and write to another repo.

### When to Write

Write project memory when you learn something durable and non-obvious about a codebase:

- A decision that will affect how future work is done.
- A convention that is not obvious from reading the code.
- An architecture fact that takes real work to rediscover.
- A gotcha or recurring bug root cause.
- A setup or workflow step that is not in the README.
- A dependency constraint or quirk that caused problems.

Do not write:

- Secrets, tokens, credentials, or `.env` values.
- Raw command output or test results.
- Temporary task state ("I am currently working on X").
- Vague summaries without actionable content.
- Facts already obvious from `README.md`, `AGENTS.md`, or nearby code: unless the memory adds durable interpretation that is hard to infer.

### Quality Rules for Project Memory

Same rules as user memory:

- Content ≥ 40 characters or ≥ 7 words.
- No vague phrases, command output, or secrets.
- No duplicates of existing active memories. A second call with identical content raises `MemoryQualityError` (reason: `duplicates`) rather than silently doing nothing. Do not retry on this error: it confirms the memory already exists.

### Project Memory Workflow

**At task start (mandatory):**
```
1. project_search <task-terms> → load task-specific context
2. Verify findings against repo files before acting
```

**Before each final response (when something durable was learned):**
```
Durable = decision, convention, architecture fact, gotcha, workflow step, dependency quirk
1. project_remember for each durable repo-scoped fact
2. source="agent" or source="user", source_ref=<file path, PR, or test command>
```

**When memory is stale or wrong:**
```
1. Repo wins. Memory is a hint.
2. project_update to correct content
3. project_forget to archive if it no longer applies
4. Preserve useful source references when correcting
```

**During memory cleanup (periodic housekeeping):**
```
1. project_purge <days> → hard-delete archived project memories older than N days
2. user_purge <days>    → hard-delete archived user memories older than N days
3. Audit events are always preserved; only the memory rows are removed
```

---

## Cross-Project Memory

Project memory is not sealed off per repo. Every `project_*` tool takes a `project_root` argument, so you can read from and write to any known project, not just the current working directory. Use this when work legitimately spans repos: shared contracts, client/server pairs, split monorepos, or a convention defined in one repo that governs others.

### Reading Another Repo's Memory

Reach for cross-project context when:

- The task references another repo by name, or an interface shared with it (an API, an event schema, a protocol).
- You are changing something in this repo that a known sibling / upstream / downstream repo depends on.
- The current repo's memory is thin and a similar problem was likely solved elsewhere.

How:

```
1. project_search <task-terms> all_projects:true
2. Read project_name / project_root on each hit to see which repo it describes.
3. To go deeper on one repo, call project_search again with that repo's project_root.
4. Verify any cross-repo fact against that repo's actual files before acting: it is a lead, not ground truth for this repo.
```

### Writing to Another Repo's Memory

Sometimes the durable thing you learned belongs to a *different* repo than the one you are working in: you discovered a gotcha in a shared library while debugging here, or a decision made in this repo imposes a constraint on a downstream repo. Store it where a future agent working in *that* repo will find it.

How:

```
1. Get the target repo's project_root (from an all_projects:true search result, or a known checkout path).
2. project_remember content:<durable fact> project_root:<target repo root>
3. To correct an existing memory in another repo, project_update id:<id> project_root:<target repo root>.
```

When to write cross-project instead of to the current repo:

- The fact is about the *other* repo's code, conventions, or behavior, not this one.
- A change here creates a constraint or breakage risk that only matters when someone edits the other repo.

Guardrails:

- Only write to a repo you have confirmed exists (it appeared in an `all_projects` search, or you know its checkout path). Do not invent a `project_root`.
- Write the fact from the perspective of an agent working *in* the target repo, naming this repo explicitly when the fact is about a cross-repo relationship (e.g. "Consumed by <this-repo>; changing this field's shape breaks it").
- A fact that is genuinely about the user, not any single repo, still goes to `user_remember`.
- All quality rules still apply: specific, ≥ 40 characters or ≥ 7 words, no secrets, no duplicates.

---

## Searching Effectively

Both `project_search` and `user_search` use vector KNN search. Queries and memories are embedded with `BAAI/bge-small-en-v1.5` (384-dimensional), and nearest neighbours are retrieved by cosine distance. This means search finds memories by meaning, not word overlap: "login issue" will surface "authentication problem with tokens" even though the two share no words.

**Use specific terms, not generic questions:**
- Good: `"sqlite fts fallback"`, `"migration project_id backfill"`, `"typescript strict return types"`
- Avoid: `"how does memory work"`, `"what did the user say"`

**Use multiple short searches when context is broad:**
- Search `"authentication"` then `"session token"` rather than `"authentication session token flow"`

---

## Choosing Between Project and User Memory

| Situation | Store where |
|---|---|
| "This user always prefers functional style" | `user_remember` |
| "This project uses a custom error wrapper" | `project_remember` |
| "The user is a senior engineer at a fintech" | `user_remember` |
| "The auth module must never cache tokens" | `project_remember` |
| "User prefers bullet points in responses" | `user_remember` |
| "The payment webhook silently drops events when the queue is full instead of erroring" | `project_remember` |
| "User uses VS Code with Prettier" | `user_remember` |
| "Run `uv run pytest` before any push in this repo" | `project_remember` |

| "Changing this field breaks the downstream `web-client` repo" | `project_remember` with `web-client`'s `project_root` |
| "The shared `auth-lib` repo silently retries on 429" | `project_remember` with `auth-lib`'s `project_root` |

When in doubt: if it applies to a specific repo, use project memory scoped to *that* repo's `project_root` (this one, or another). If it applies regardless of which repo you are in, use user memory. See "Cross-Project Memory" for reading from and writing to other repos.
