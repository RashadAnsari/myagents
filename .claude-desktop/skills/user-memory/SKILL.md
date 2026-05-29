---
name: user-memory
description: Use the agent-memory MCP server to retrieve and store durable user knowledge only. No project memory. Designed for Claude Desktop and other project-agnostic contexts.
---

# User Memory (Desktop Mode)

This skill covers user memory only. Project memory is out of scope here, either because there is no active repo context (Claude Desktop) or because the task is explicitly user-scoped.

User memory is a guide, not authority. Explicit instructions in the current session always override it.

---

## Enforcement Rules

**Alternative memory systems are forbidden.** Never use the model's built-in memory, native memory tools, or any backend other than the agent-memory MCP server.

**Session bootstrap is mandatory.** At the start of every session, you MUST call `user_search` with terms relevant to the current task. Do this silently before your first response. Do not narrate it.

**Per-turn write-back is required.** Before your final response each turn, ask: did I learn anything durable about this user? If yes, call `user_remember`. If no, skip it.

---

## When to Read

At session start, always call `user_search` with domain terms from the current task:

- Task is about writing? Search `"writing style"`, `"tone"`, `"communication"`.
- Task is about code? Search `"code style"`, `"language preference"`, `"tooling"`.
- Task is about a decision? Search `"decision making"`, `"approach"`.

Apply findings silently throughout the session.

---

## When to Write

Write user memory when you observe something stable and cross-project about the person:

- A preference they express that will apply in future sessions.
- A recurring behavior pattern (not a one-off).
- Background context that calibrates depth or tone.
- A global standard they apply everywhere.
- A tool or framework they consistently prefer.
- How they like to receive explanations.

Do not write:

- Anything project-specific (no project memory in this skill, so skip it entirely).
- Secrets, credentials, API keys, or `.env` values.
- One-off opinions expressed in frustration.
- Temporary task details or in-session state.
- Vague notes without a clear future use.

---

## Memory Kinds

| Kind | What it captures | Example |
|---|---|---|
| `preference` | Coding style, language, formatting | "User prefers two-space indentation in all TypeScript files." |
| `behavior` | Recurring habits and patterns | "User always opens a scratch file before writing production code." |
| `context` | Role, team, domain, experience | "User is a senior backend engineer at a fintech startup." |
| `workflow` | Work process structure | "User reviews full diffs before merging; expects clear change summaries." |
| `convention` | Global standards across projects | "User applies kebab-case to all file names and CSS class names." |
| `tool_preference` | Preferred tools and configs | "User prefers VS Code with the ESLint and Prettier extensions." |
| `communication` | Explanation and response style | "User prefers bullet points over prose in technical summaries." |

---

## Quality Rules

Every user memory must pass all of these:

- **Content is at least 40 characters or 7 words.** Short notes are not durable.
- **`whyUsefulLater` is required.** Explain exactly how a future agent benefits. If you cannot, skip it.
- **No vague phrases.** Avoid "fixed the issue", "made changes", "implemented it".
- **No command output.** Do not store logs, test output, or exit codes.
- **No secrets.** API keys, tokens, and private keys are rejected automatically.
- **No duplicates.** If a `MemoryQualityError` with reason `duplicates` is returned, do not retry. The memory already exists.

---

## Session Workflow

**At session start (mandatory):**
```
1. user_search <task-terms>  →  load task-relevant user knowledge
2. Apply findings silently
```

**Before each final response (when something durable was learned):**
```
1. user_remember with kind, content, whyUsefulLater
2. source="user" if the user stated it directly, source="agent" if inferred
```

**When a memory is stale or wrong:**
```
1. user_update  →  correct the content or lower confidence
2. user_forget  →  archive if it no longer applies at all
3. user_remember  →  store the accurate version
```

---

## Searching Effectively

`user_search` uses vector KNN. Queries are matched by meaning, not word overlap. "login issue" surfaces "authentication problem with tokens" even with no shared words.

**Specific terms work better than generic questions:**
- Good: `"typescript strict types"`, `"bullet point responses"`, `"vim keybindings"`
- Avoid: `"what does the user like"`, `"preferences"`

**Run multiple short searches when the task spans domains:**
- Search `"communication style"` then `"code formatting"` rather than one long query.

**Use kind filters when the category is clear:**
- `kinds: ["preference", "convention"]` when checking style rules.
- `kinds: ["communication"]` when calibrating response format.
