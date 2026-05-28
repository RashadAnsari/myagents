---
name: agent-memory
description: Use the agent-memory MCP server to retrieve, verify, and store durable project knowledge and global user knowledge before and after non-trivial work.
---

# Project Memory & User Memory

Two parallel memory systems are available. Both are indexed notes, not authority: current user instructions, repo files, tests, and official docs always override memory.

---

## Enforcement Rules

These are hard requirements. No exceptions.

**Alternative memory systems are forbidden.** Never use the model's built-in memory, native memory tools, or any backend other than the agent-memory MCP server. This applies to every form of memory work: storing facts, recalling context, updating beliefs, retrieving preferences.

**Session bootstrap is mandatory.** Before your first response in any session, you MUST call `project.search` and `user.search` with specific terms from the current task. These calls are required, not optional. Do not respond to the user before making them. Do this silently without narrating it to the user.

**Per-turn write-back is required.** Before producing your final response each turn, ask: did I learn anything durable this turn? Durable means: a decision made, a user preference stated, a gotcha discovered, a convention established, an architecture fact clarified. If yes, you MUST call `project.remember` or `user.remember` before finishing. This is not optional. Do not skip it. Do not defer it. If nothing durable was learned this turn, skip the write.

---

## Quick Reference

| Question | Action |
|---|---|
| What does this user prefer? | `user.search` |
| What has been decided in this project? | `project.search` |
| Should I store this? | Only if a future agent needs it and it passes the quality rules below |
| Is this project-specific or cross-project? | Project-specific: `project.remember`, cross-project: `user.remember` |

---

## User Memory

### When to Read

You MUST call user memory at the start of every session:

1. Call `user.search` with domain terms relevant to the current task (e.g. `"typescript"`, `"git workflow"`, `"testing"`).
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

**At session start (mandatory):**
```
1. user.search <task-terms> → load task-relevant user knowledge
2. Apply findings silently throughout the session
```

**Before each final response (when something durable was learned):**
```
Durable = decision, preference, gotcha, convention, architecture fact, behavior pattern
1. user.remember for each durable cross-project fact
2. Include a clear whyUsefulLater
3. source="agent" or source="user", source_ref=<context>
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

You MUST call project memory before any work on a codebase:

1. Call `project.search` with task-specific terms: file names, function names, domain concepts, error messages.
2. Verify findings against the actual repo before acting on them.

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
| `decision` | Architectural or design decisions with rationale | "Chose REST over GraphQL because the client team is familiar with REST and the API surface is small and stable." |
| `convention` | Naming, style, or structure rules | "All API error responses must include a `code` field with a machine-readable string; never return just an HTTP status." |
| `architecture` | Module boundaries, data flow, key relationships | "Business logic lives in `src/services/`; `src/api/` only handles request parsing and response formatting. Never put DB calls in API handlers." |
| `workflow` | Non-obvious build, test, or deploy steps | "Run `npm run db:migrate` before running tests locally; the test suite does not auto-migrate." |
| `preference` | User preferences specific to this project | "User wants all new React components in `src/components/` as named exports, never default exports." |
| `gotcha` | Surprising behavior or traps | "Prisma `findUnique` silently returns null instead of throwing when a record is not found; always check the return value." |
| `bug` | Root causes of recurring issues | "The date picker breaks on Safari when the locale prop is omitted; always pass an explicit locale." |
| `dependency` | Constraint or quirk of a library or tool | "Day.js `isBetween` plugin must be explicitly imported and registered before use; it is not included by default." |
| `testing` | Test patterns or required coverage | "E2E tests must call `resetDb()` before each test; the suite shares a database and is order-dependent without it." |
| `handoff` | End-of-task learnings for the next agent | "Migrated auth from JWT in localStorage to httpOnly cookies; old JWT validation code removed from `src/middleware/auth.ts`." |

### Quality Rules for Project Memory

Same rules as user memory:

- Content ≥ 40 characters or ≥ 7 words.
- `whyUsefulLater` required and meaningful.
- No vague phrases, command output, or secrets.
- No duplicates of existing active memories. A second call with identical content raises `MemoryQualityError` (reason: `duplicates`) rather than silently doing nothing. Do not retry on this error: it confirms the memory already exists.

### Project Memory Workflow

**At task start (mandatory):**
```
1. project.search <task-terms> → load task-specific context
2. Verify findings against repo files before acting
```

**Before each final response (when something durable was learned):**
```
Durable = decision, convention, architecture fact, gotcha, workflow step, dependency quirk
1. project.remember for each durable repo-scoped fact
2. Include whyUsefulLater: if you cannot explain it, skip it
3. source="agent" or source="user", source_ref=<file path, PR, or test command>
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
1. project.purge <days> → hard-delete archived project memories older than N days
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
| "The payment webhook silently drops events when the queue is full instead of erroring" | `project.remember` → `gotcha` |
| "User uses VS Code with Prettier" | `user.remember` → `tool_preference` |
| "Run `uv run pytest` before any push in this repo" | `project.remember` → `workflow` |

When in doubt: if it applies only to this repo, use project memory. If it applies regardless of which repo you are in, use user memory.

---

## Confidence Levels

| Level | When to use |
|---|---|
| `high` | Confirmed by direct observation or explicit user statement |
| `medium` | Inferred from behavior or indirect evidence (default) |
| `low` | Uncertain; should be verified before relying on it |

Lower confidence when memory conflicts with current evidence rather than archiving it immediately: it may still be useful as a starting point.
