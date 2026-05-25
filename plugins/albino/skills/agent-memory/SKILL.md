---
name: agent-memory
description: Use the agent-memory MCP server to retrieve, verify, and store durable project knowledge and global user knowledge before and after non-trivial work.
---

# Project Memory & User Memory

Two parallel memory systems are available. Both are indexed notes, not authority: current user instructions, repo files, tests, and official docs always override memory.

---

## Quick Reference

| Question | Action |
|---|---|
| What does this user prefer? | `user.brief` or `user.search` |
| What has been decided in this project? | `project.brief` or `project.search` |
| Should I store this? | Only if a future agent needs it and it passes the quality rules below |
| Is this project-specific or cross-project? | Project-specific → `project.remember`, cross-project → `user.remember` |

---

## User Memory

### When to Read

Read user memory at the start of every non-trivial session:

1. Read `memory://user/brief` for the full picture: preferences, behaviors, context, and communication style.
2. Call `user.search` with domain terms relevant to the current task (e.g. `"typescript"`, `"git workflow"`, `"testing"`).
3. Apply what you find throughout the session without being asked: this is the point of having it.

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

- Anything project-specific: use `project.remember` instead.
- Secrets, credentials, API keys, or `.env` values.
- One-off opinions stated in frustration.
- Temporary task details.
- Vague notes without a clear future use.

### User Memory Kinds and Examples

| Kind | What it captures | Example |
|---|---|---|
| `preference` | Coding style, language, formatting | "User prefers two-space indentation in all TypeScript files." |
| `behavior` | Recurring habits and patterns | "User always opens a scratch file before writing production code." |
| `context` | Role, team, domain, experience | "User is a senior backend engineer at a fintech startup." |
| `workflow` | Work process structure | "User reviews full diffs before merging; expects clear change summaries." |
| `convention` | Global standards across projects | "User applies kebab-case to all file names and CSS class names." |
| `tool_preference` | Preferred tools and configs | "User prefers VS Code with the ESLint and Prettier extensions." |
| `communication` | Explanation and response style | "User prefers bullet points over prose in technical summaries." |

### Quality Rules for User Memory

Every user memory must satisfy all of these:

- **Content ≥ 40 characters or ≥ 7 words.** Short notes are not durable enough.
- **`whyUsefulLater` required.** Explain exactly how a future agent benefits. If you cannot, do not store it.
- **No vague phrases.** Avoid "fixed the issue", "made changes", "implemented it".
- **No command output.** Do not store npm logs, test output, or exit codes.
- **No secrets.** Any content matching API key, token, or private key patterns is rejected automatically.
- **No duplicates.** Normalized content must differ from existing active memories. A duplicate raises `MemoryQualityError` (reason: `duplicates`). Do not retry: it confirms the memory already exists.

### User Memory Workflow

**At session start:**
```
1. user.brief              → load preferences, behaviors, context
2. user.search <task-terms> → load task-relevant user knowledge
3. Apply findings silently throughout the session
```

**At session end (when something durable was learned):**
```
1. Identify stable facts observed about the user
2. Check: is this cross-project? (if not, use project.remember instead)
3. user.remember for each durable fact
4. Include a clear whyUsefulLater
5. Optionally: source="agent" or source="user", source_ref=<context>
```

**When user memory conflicts with observed behavior:**
```
1. user.update to correct the existing memory
2. Or user.forget to archive it if it no longer applies
3. Then user.remember with the accurate version
```

---

## Project Memory

### When to Read

Read project memory before non-trivial work on a codebase:

1. Read `memory://project/current/brief` for conventions, decisions, pitfalls, and recent entries.
2. Call `project.search` with task-specific terms: file names, function names, domain concepts, error messages.
3. Use findings to guide investigation: but verify against the actual repo before acting on them.

Memory can be stale. Always confirm what it says against current files, tests, and docs.

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

### Project Memory Kinds and Examples

| Kind | What it captures | Example |
|---|---|---|
| `decision` | Architectural or design decisions with rationale | "Chose SQLite over Postgres because the tool is local-first and single-user." |
| `convention` | Naming, style, or structure rules | "All MCP tool handlers must call `jsonResult()` for consistent response format." |
| `architecture` | Module boundaries, data flow, key relationships | "The store layer owns all SQL; the service layer handles validation and business logic." |
| `workflow` | Non-obvious build, test, or deploy steps | "Run `uv sync` before tests; the lockfile must not change." |
| `preference` | User preferences specific to this project | "User wants all new files to use named exports, never default exports." |
| `gotcha` | Surprising behavior or traps | "sqlite-vec must be loaded before any DDL runs; loading after table creation silently skips vector indexing." |
| `bug` | Root causes of recurring issues | "WAL files cause read contention when the db is opened twice in the same process." |
| `dependency` | Constraint or quirk of a library or tool | "Zod v4 changed `.optional()` chaining semantics; do not upgrade without testing." |
| `testing` | Test patterns or required coverage | "Integration tests use InMemoryTransport; never use real stdio in tests." |
| `handoff` | End-of-task learnings for the next agent | "Switched memory search to vector-only (KNN via sqlite-vec); removed the FTS fallback entirely." |

### Quality Rules for Project Memory

Same rules as user memory:

- Content ≥ 40 characters or ≥ 7 words.
- `whyUsefulLater` required and meaningful.
- No vague phrases, command output, or secrets.
- No duplicates of existing active memories. A second call with identical content raises `MemoryQualityError` (reason: `duplicates`) rather than silently doing nothing. Do not retry on this error: it confirms the memory already exists.

### Project Memory Workflow

**At task start:**
```
1. project.brief           → load conventions, decisions, pitfalls
2. project.search <task-terms>     → load task-specific context
3. Verify findings against repo files before acting
```

**At task end (when something durable was learned):**
```
1. Identify what would help the next agent on this codebase
2. project.remember
3. Include whyUsefulLater: if you cannot explain it, skip it
4. Optionally: source="agent" or source="user", source_ref=<file path, PR, or test command>
```

**When memory is stale or wrong:**
```
1. Repo wins. Memory is a hint.
2. project.update to correct content or lower confidence
3. project.forget to archive if it no longer applies
4. Preserve useful source references when correcting
```

**During memory cleanup (periodic housekeeping):**
```
1. project.purge <days>  → hard-delete archived project memories older than N days
2. user.purge <days>    → hard-delete archived user memories older than N days
3. Audit events are always preserved; only the memory rows are removed
```

---

## Searching Effectively

Both `project.search` and `user.search` use vector KNN search. Queries and memories are embedded with `BAAI/bge-small-en-v1.5` (384-dimensional), and nearest neighbours are retrieved by cosine distance. This means search finds memories by meaning, not word overlap: "login issue" will surface "authentication problem with tokens" even though the two share no words.

**Use specific terms, not generic questions:**
- Good: `"sqlite fts fallback"`, `"migration project_id backfill"`, `"typescript strict return types"`
- Avoid: `"how does memory work"`, `"what did the user say"`

**Use multiple short searches when context is broad:**
- Search `"authentication"` then `"session token"` rather than `"authentication session token flow"`

**Use kind filters when you know the category:**
- `kinds: ["gotcha", "bug"]` when looking for pitfalls
- `kinds: ["preference", "convention"]` when checking style rules

**Use tag filters when tags are likely:**
- `tags: ["typescript"]` to filter to typed-language memories

---

## Choosing Between Project and User Memory

| Situation | Store where |
|---|---|
| "This user always prefers functional style" | `user.remember` → `preference` |
| "This project uses a custom error wrapper" | `project.remember` → `convention` |
| "The user is a senior engineer at a fintech" | `user.remember` → `context` |
| "The auth module must never cache tokens" | `project.remember` → `decision` |
| "User prefers bullet points in responses" | `user.remember` → `communication` |
| "sqlite-vec extension requires uv-managed Python on macOS for extension loading" | `project.remember` → `gotcha` |
| "User uses VS Code with Prettier" | `user.remember` → `tool_preference` |
| "Run `uv run pytest` before any push in this repo" | `project.remember` → `workflow` |

When in doubt: if it applies only to this repo, use project memory. If it applies regardless of which repo you are in, use user memory.

---

## Prompts

The server exposes MCP prompts you can invoke directly to get structured instructions injected into a task. Use these when you want the memory workflow spelled out explicitly rather than relying on the skill prose.

| Prompt | When to use | Key parameter |
|---|---|---|
| `project_bootstrap` | Before starting a non-trivial task on a codebase | `task` (optional description) |
| `project_handoff` | After completing a task to decide what to store | `task_summary`, `tests_run` |
| `project_cleanup` | During housekeeping to find and fix stale entries | `topic` (optional focus area) |
| `user_bootstrap` | At session start to load the user's preferences | none |
| `user_update` | At session end to store new user knowledge | `session_summary` |

These prompts are shortcuts: they return the same guidance this skill describes, formatted as ready-to-follow instructions.

---

## Confidence Levels

| Level | When to use |
|---|---|
| `high` | Confirmed by direct observation or explicit user statement |
| `medium` | Inferred from behavior or indirect evidence (default) |
| `low` | Uncertain; should be verified before relying on it |

Lower confidence when memory conflicts with current evidence rather than archiving it immediately: it may still be useful as a starting point.
