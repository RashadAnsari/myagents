---
description: Search agent memory and forget entries matching the given description
allowed-tools: [Bash, AskUserQuestion, mcp__plugin_albino_agent-memory__project_search, mcp__plugin_albino_agent-memory__user_search, mcp__plugin_albino_agent-memory__project_forget, mcp__plugin_albino_agent-memory__user_forget]
---

## Task

Search agent memory and forget the entries that match.

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

## Step 5: Show matches and confirm

Print a numbered list of every match, grouped by scope:

**Project memory:**
```
1. [id=42] <summary> — <first 120 chars of content>
```

**User memory:**
```
3. [id=7] <summary> — <first 120 chars of content>
```

Then ask: "Forget all of these?"

Options:
- "Forget all" — forget every entry in both lists
- "Only project memories" — forget project entries only
- "Only user memories" — forget user entries only

If the user types something in Other (e.g. "only 1 and 3"), interpret it as a natural language selection against the numbered list and tell the user exactly which entries you will forget before proceeding. If ambiguous, ask once to clarify.

## Step 6: Forget the selected entries

For each selected **project memory**, call `mcp__plugin_albino_agent-memory__project_forget` with:
- `project_root`: `PROJECT_ROOT`
- `id`: numeric id of the entry
- `hard_delete`: `false` (soft-delete; reversible)
- `reason`: `"Forgotten via /forget: $ARGUMENTS"`

For each selected **user memory**, call `mcp__plugin_albino_agent-memory__user_forget` with:
- `id`: numeric id of the entry
- `hard_delete`: `false`
- `reason`: `"Forgotten via /forget: $ARGUMENTS"`

Run all forget calls in parallel.

## Step 7: Report

Tell the user how many memories were forgotten and list their summaries. Mention that the deletions are soft (reversible via `project.update archive:false` or `user.update archive:false`) unless the user requests permanent removal.
