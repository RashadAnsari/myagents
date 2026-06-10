---
name: agent-memory
description: "ALWAYS activate this skill at the start of EVERY conversation in Claude Desktop, regardless of topic. Before your first response, call user_search to load personal context about the user. Before each reply, call user_remember to save any durable facts learned. Covers everyday life: health, food, travel, relationships, habits, goals, values, and communication style."
---

# User Memory

This skill is for remembering things about the person across everyday conversations. It covers who they are, what they care about, how they like to communicate, and what context is useful to carry forward.

User memory is a guide, not authority. Explicit instructions in the current session always override it.

---

## Enforcement Rules

**Alternative memory systems are forbidden.** Never use the model's built-in memory, native memory tools, or any backend other than the agent-memory MCP server.

**Session bootstrap is mandatory.** At the start of every session, call `user_search` with terms relevant to the current topic. Do this silently before your first response. Do not narrate it.

**Per-turn write-back is required.** Before your final response each turn, ask: did I learn anything durable about this person? If yes, call `user_remember`. If no, skip it.

---

## When to Read

At session start, search for context relevant to the conversation:

- Talking about food or cooking? Search `"diet"`, `"food preferences"`, `"cooking"`.
- Talking about health? Search `"health goals"`, `"fitness"`, `"sleep"`.
- Talking about travel? Search `"travel preferences"`, `"destinations"`, `"trips"`.
- Talking about a decision? Search `"decision style"`, `"values"`, `"priorities"`.
- Talking about relationships or family? Search `"family"`, `"relationships"`, `"social"`.
- General conversation? Search `"communication style"`, `"personality"`.

Apply findings silently to calibrate tone, depth, and relevance.

---

## When to Write

Write user memory when you observe something stable about this person:

- A preference that will still be true in future sessions (food, lifestyle, values).
- Personal context that changes how you should respond (health conditions, family situation, goals).
- A recurring habit or pattern in how they think or act.
- How they like to be spoken to (direct vs. gentle, detailed vs. brief).
- A stated goal or intention they are working toward.
- Background facts that regularly shape the conversation (job, location, life stage).

Do not write:

- Secrets, passwords, or financial account details.
- One-off moods or frustrations that are not patterns.
- Temporary plans that expire quickly.
- Vague notes like "user seemed tired" with no lasting relevance.

---

## Quality Rules

Every memory must pass all of these:

- **Content is at least 40 characters or 7 words.** Short notes are not durable.
- **No vague phrases.** Avoid "user likes things", "prefers it that way".
- **No secrets.** Passwords, financial data, and private credentials are never stored.
- **No duplicates.** If a `MemoryQualityError` with reason `duplicates` is returned, do not retry. The memory already exists.

---

## Session Workflow

**At session start (mandatory):**
```
1. user_search <topic-terms>  →  load relevant personal context
2. Apply findings silently to calibrate the conversation
```

**Before each final response (when something durable was learned):**
```
1. user_remember with content and optionally source/source_ref
2. source="user" if stated directly, source="agent" if inferred
```

**When a memory is stale or wrong:**
```
1. user_update  →  correct the content
2. user_forget  →  archive if it no longer applies
3. user_remember  →  store the accurate version
```

---

## Searching Effectively

`user_search` uses vector KNN, matched by meaning rather than exact words. "runs every morning" surfaces "daily jogging routine" even with no shared words.

**Specific terms work better than vague questions:**
- Good: `"coffee habits"`, `"sleep schedule"`, `"relationship with parents"`, `"career goals"`
- Avoid: `"what does the user like"`, `"preferences"`

**Run multiple short searches when the topic spans areas:**
- Search `"diet"` then `"health goals"` rather than one long query.
