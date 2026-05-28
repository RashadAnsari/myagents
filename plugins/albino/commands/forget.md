---
description: Search agent memory and forget entries matching the given description
allowed-tools: [Bash, mcp__plugin_albino_agent-memory__project_search, mcp__plugin_albino_agent-memory__user_search, mcp__plugin_albino_agent-memory__project_forget, mcp__plugin_albino_agent-memory__user_forget]
---

## Task

Search agent memory and forget every entry that matches.

Subject: $ARGUMENTS

## Step 1: Validate input

If `$ARGUMENTS` is empty or missing, stop immediately and tell the user:

```
Usage: /forget <what to forget>
Example: /forget my preference for two-space indentation
Example: /forget the Prisma migration workflow
```

## Step 2: Get the project root

Run:

```bash
git rev-parse --show-toplevel
```

Store as `PROJECT_ROOT`.

## Step 3: Search both memory stores in parallel

Run both at the same time:

1. `mcp__plugin_albino_agent-memory__project_search` with `project_root: PROJECT_ROOT`, `query: $ARGUMENTS`, `k: 10`
2. `mcp__plugin_albino_agent-memory__user_search` with `query: $ARGUMENTS`, `k: 10`

After results arrive, filter each list: keep only entries whose `content` or `summary` is meaningfully related to `$ARGUMENTS`. Discard unrelated results that surfaced only because of distant semantic similarity.

Store the filtered results as `PROJECT_MATCHES` and `USER_MATCHES`.

## Step 4: Handle no matches

If both lists are empty after filtering, stop and tell the user:

```
No memory found matching: <$ARGUMENTS>
```

## Step 5: Forget all matches

Immediately forget every entry in `PROJECT_MATCHES` and `USER_MATCHES` without asking for confirmation.

For each **project memory**, call `mcp__plugin_albino_agent-memory__project_forget` with:
- `project_root`: `PROJECT_ROOT`
- `id`: numeric id of the entry
- `hard_delete`: `false` (soft-delete; reversible)
- `reason`: `"Forgotten via /forget: $ARGUMENTS"`

For each **user memory**, call `mcp__plugin_albino_agent-memory__user_forget` with:
- `id`: numeric id of the entry
- `hard_delete`: `false`
- `reason`: `"Forgotten via /forget: $ARGUMENTS"`

Run all forget calls in parallel.

## Step 6: Report

Tell the user how many memories were forgotten and list their summaries. Mention that the deletions are soft (reversible via `project.update archive:false` or `user.update archive:false`) unless the user requests permanent removal.
