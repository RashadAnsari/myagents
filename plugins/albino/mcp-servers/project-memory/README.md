# Project Memory MCP Server

Local MCP server for durable memory. It stores two kinds of memory:

- **Project memory** — knowledge scoped to a specific codebase (decisions, conventions, gotchas).
- **User memory** — cross-project knowledge about the person you are working with (preferences, behaviors, context).

Both are local-first:

- Runs over MCP stdio.
- Stores memory in SQLite at `~/.myagents/project-memory/memory.sqlite`.
- Uses neural vector search (KNN via `sqlite-vec`) as the primary ranking method, with SQLite FTS5/BM25 as fallback.
- Rejects noisy, vague, duplicate, and secret-looking memories.
- Exposes tools, resources, and prompts through MCP.

## Startup

The Albino plugin registers this server in `plugins/albino/.mcp.json`.

The MCP host runs:

```bash
bash ./mcp-servers/project-memory/run.sh
```

`run.sh` does the runtime setup:

1. Finds `bun` in `PATH` or `~/.bun/bin/bun`.
2. Installs Bun with the official installer if Bun is missing.
3. Runs `bun install --frozen-lockfile`.
4. Starts `src/index.ts`.

Setup logs go to stderr so stdout remains reserved for MCP JSON-RPC.

## Storage

Default database path:

```text
~/.myagents/project-memory/memory.sqlite
```

Override the storage directory with:

```bash
MYAGENTS_MEMORY_DIR=/custom/memory/dir
```

When set, the database path becomes:

```text
/custom/memory/dir/memory.sqlite
```

The database files are ignored by git.

## Project Memory

Project memory is scoped to a single repository. It is identified by the normalized project root path and, when available, the git remote fingerprint.

### What Gets Stored

Good project memory:

- Stable project conventions.
- Decisions that affect future implementation.
- Non-obvious architecture facts.
- Repeated gotchas.
- Recurring bug root causes.
- Important user preferences for this project.
- Setup or workflow details that are hard to rediscover.

Bad project memory:

- Secrets, tokens, credentials, cookies, private keys, or `.env` values.
- Raw command output.
- Temporary task state.
- Vague summaries like "fixed the issue".
- Facts already obvious from current files unless the memory adds durable interpretation.

### Project Memory Kinds

| Kind           | Use                                                |
| -------------- | -------------------------------------------------- |
| `decision`     | Architecture or design decisions with rationale    |
| `convention`   | Coding style or naming rules for this project      |
| `architecture` | Structure, boundaries, or key module relationships |
| `workflow`     | Non-obvious build, test, or deploy steps           |
| `preference`   | User preferences specific to this project          |
| `gotcha`       | Surprising behavior or common pitfalls             |
| `bug`          | Root causes of recurring bugs                      |
| `dependency`   | Important dependency constraints or quirks         |
| `testing`      | Test patterns or coverage requirements             |
| `handoff`      | End-of-task learnings for the next agent           |

### Project Memory Tools

- `memory.remember` — Store durable project memory after quality and secret checks.
- `memory.search` — Search project memory with optional kind and tag filters.
- `memory.get` — Fetch one memory by id.
- `memory.project_brief` — Return compact conventions, decisions, pitfalls, and recent memory.
- `memory.update` — Correct, refine, or archive an existing memory.
- `memory.forget` — Archive by default or hard-delete when requested.
- `memory.capture_task_summary` — Store reusable end-of-task learnings.
- `memory.export_project` — Export project memory for backup or migration.
- `memory.import_project` — Import a project memory export.
- `memory.link_project_paths` — Explicitly link another checkout path to the same project memory.
- `memory.possible_project_matches` — Find same-git-remote paths without automatically linking them.

### Project Memory Resources

- `memory://project/current/brief` — Conventions, decisions, pitfalls, and recent memory.
- `memory://project/current/conventions` — Conventions and preferences.
- `memory://project/current/decisions` — Decisions and architecture.
- `memory://project/current/pitfalls` — Gotchas and bugs.
- `memory://project/current/recent` — Most recently updated memories.

### Project Memory Prompts

- `memory_bootstrap` — Fetch relevant memory before non-trivial work.
- `memory_handoff` — Store only durable learnings after a task.
- `memory_cleanup` — Review stale, contradictory, or low-confidence memory.

## User Memory

User memory is global — it is not scoped to any project. It stores stable facts about the person you are working with so agents can apply them across all sessions and repositories.

### What Gets Stored

Good user memory:

- Consistent coding and style preferences.
- Recurring behavioral patterns.
- Background context (role, team, domain, experience level).
- Global conventions the user applies everywhere.
- Preferred tools, frameworks, or configurations.
- Communication and explanation style preferences.

Bad user memory:

- Secrets, tokens, credentials, or `.env` values.
- Project-specific knowledge — use project memory instead.
- One-off task details or temporary opinions.
- Anything that does not help future agents understand this person.

### User Memory Kinds

| Kind              | Use                                                    |
| ----------------- | ------------------------------------------------------ |
| `preference`      | Coding style, language, formatting, output preferences |
| `behavior`        | Recurring habits and patterns the user exhibits        |
| `context`         | Role, team, domain, experience level, background       |
| `workflow`        | How the user structures their work processes           |
| `convention`      | Global standards applied across all projects           |
| `tool_preference` | Preferred tools, frameworks, CLIs, and configurations  |
| `communication`   | How the user prefers explanations and responses        |

### User Memory Tools

- `user.remember` — Store durable user memory after quality and secret checks.
- `user.search` — Search user memory with optional kind and tag filters.
- `user.get` — Fetch one user memory by id.
- `user.brief` — Return compact preferences, behaviors, context, and recent user memories.
- `user.update` — Correct, refine, or archive an existing user memory.
- `user.forget` — Archive by default or hard-delete when requested.
- `user.export` — Export all user memory for backup or migration.
- `user.import` — Import a user memory export with validation and deduplication.

### User Memory Resources

- `memory://user/brief` — All four categories of user memory.
- `memory://user/preferences` — Preferences, conventions, and tool preferences.
- `memory://user/behaviors` — Behaviors, workflows, and communication style.
- `memory://user/context` — Context entries.

### User Memory Prompts

- `user_memory_bootstrap` — Read user memory at the start of a session.
- `user_memory_update` — Store durable user-level learnings after a session.

## Search

Memory search uses a two-stage hybrid pipeline:

1. **Vector KNN (primary)** — The query and all memories are embedded using `Xenova/all-MiniLM-L6-v2` (a 384-dimension sentence transformer from `@huggingface/transformers`). Embeddings are stored in `sqlite-vec` virtual tables (`memory_vec`, `user_memory_vec`). At query time the nearest neighbours are retrieved by cosine distance using sqlite-vec's `MATCH` operator.

2. **FTS5/BM25 (fallback)** — If vector search returns no results (e.g. no embeddings have been generated yet), the query falls back to SQLite FTS5 with BM25 ranking, then to a SQL `LIKE` scan.

**Why vector search?**

Vector search finds memories by meaning, not word overlap. A query for "login issue" will surface a memory about "authentication problem with tokens" even though the two share no words, because the embedding model places them near each other in the 384-dimensional vector space.

**Model and caching**

The embedding model (~25 MB) is downloaded once on first use and cached locally by `@huggingface/transformers`. Subsequent starts load from cache with no network access required.

**Backfill**

On every startup, `backfillEmbeddings()` runs and generates embeddings for any memories that do not yet have one. This handles memories created before vector search was introduced and any records written during a failed embedding attempt.

## Development

From the repository root:

```bash
make format
make lint
make test
```

From this directory:

```bash
bun install
bun run format
bun run lint
bun run typecheck
bun test
```

Smoke test the stdio server:

```bash
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"smoke","version":"0.0.0"}}}' \
  | MYAGENTS_MEMORY_DIR=/tmp/myagents-memory-smoke bash ./run.sh
```

## Important Behavior

- Memory is a hint, not authority. Current user instructions, repo files, tests, and official docs override memory.
- Archived memories are excluded from normal search; pass `includeArchived: true` to include them.
- Hard delete removes the memory row but keeps an audit event.
- Project paths with the same git remote are only linked when `memory.link_project_paths` is called explicitly.
- The `MYAGENTS_MEMORY_DIR` environment variable overrides the storage directory; the database is placed directly inside it as `memory.sqlite`.
