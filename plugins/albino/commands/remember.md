---
description: Save something to agent memory - picks project or user scope automatically from context
allowed-tools: [Bash, mcp__plugin_albino_agent-memory__project_remember, mcp__plugin_albino_agent-memory__user_remember]
---

## Task

Save one or more durable memories using the agent-memory MCP server.

Subject: $ARGUMENTS

## Step 1: Determine what to remember

**If `$ARGUMENTS` is not empty**, use it as the subject. Enrich it with any relevant details from the current conversation: decisions made, conventions stated, preferences expressed, gotchas discovered, or architecture facts established. Produce a concrete, specific memory content (at least 40 characters) - do not store the raw argument text verbatim if it is vague.

**If `$ARGUMENTS` is empty**, scan the full conversation history and identify every durable learning from this session worth storing. A learning is durable if a future agent in a fresh session would benefit from it. Skip anything temporary, vague, or already obvious from reading the code. If nothing qualifies, tell the user and stop.

## Step 2: Classify each item as project or user memory

For each item, decide scope using this rule:

- **Project memory** - the fact is meaningful only in this repository: architecture decisions, code conventions, non-obvious workflow steps, dependency quirks, recurring bug root causes, gotchas, testing requirements, or handoff notes.
- **User memory** - the fact applies regardless of which project you are in: coding preferences, global conventions, background context, tool choices, communication style, or recurring behavioral patterns.

When in doubt: if removing the project would make the fact meaningless, it is project memory. If it still applies anywhere, it is user memory.

## Step 3: Get the project root (for project memories only)

If any item is classified as project memory, run:

```bash
git rev-parse --show-toplevel
```

Store as `PROJECT_ROOT`.

## Step 4: Store each memory

For **project memory**, call `mcp__plugin_albino_agent-memory__project_remember` with:
- `project_root`: value of `PROJECT_ROOT`
- `content`: specific, concrete content - at least 40 characters, no secrets, no command output
- `source`: `"user"` if the user explicitly told you, `"agent"` if you inferred it

For **user memory**, call `mcp__plugin_albino_agent-memory__user_remember` with:
- `content`: specific, concrete content - at least 40 characters, no secrets
- `source`: `"user"` if explicitly stated, `"agent"` if inferred

If a call returns a `MemoryQualityError` with reason `duplicates`, note that the memory already exists and skip it. Do not retry.

## Step 5: Report

After all calls complete, tell the user what was saved. For each saved memory show: scope (project or user) and a brief description of the content. If a duplicate was detected, say so. If nothing qualified to save, explain briefly.
