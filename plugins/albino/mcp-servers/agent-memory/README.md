# Project Memory MCP Server

Local MCP server for durable memory. It stores two kinds of memory:

- **Project memory**: knowledge scoped to a specific codebase (decisions, conventions, gotchas).
- **User memory**: cross-project knowledge about the person you are working with (preferences, behaviors, context).

Both are local-first:

- Runs over MCP stdio.
- Stores memory in SQLite at `~/.myagents/agent-memory/memory.sqlite`.
- Uses neural vector search (KNN via `sqlite-vec`) for semantic retrieval.
- Rejects noisy, vague, duplicate, and secret-looking memories.
- Exposes tools, resources, and prompts through MCP.

## Startup

The Albino plugin registers this server in `plugins/albino/.mcp.json`.

The MCP host runs the `agent-memory` entrypoint via `run-with-uv.sh`:

```bash
scripts/run-with-uv.sh run --directory mcp-servers/agent-memory agent-memory
```

`run-with-uv.sh` locates or installs `uv`, then delegates to it. `uv` auto-syncs the virtual environment on first run and starts the server over stdio. No separate install step required.

## Storage

Default database path:

```text
~/.myagents/agent-memory/memory.sqlite
```

Override the storage directory with:

```bash
AGENT_MEMORY_DIR=/custom/memory/dir
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

- `project.remember`: Store durable project memory after quality and secret checks. Requires `why_useful_later`. Idempotent by content: a duplicate raises an error rather than creating a second record.
- `project.search`: Vector search project memory with optional kind and tag filters. Supports `offset` for pagination.
- `project.brief`: Return compact conventions, decisions, pitfalls, and recent memory.
- `project.update`: Correct, refine, or archive an existing memory.
- `project.forget`: Archive by default or hard-delete when requested.
- `project.purge`: Hard-delete archived project memories older than N days to prevent unbounded growth. Audit events are always preserved.

### Project Memory Resources

- `memory://project/current/brief`: Conventions, decisions, pitfalls, and recent memory.

### Project Memory Prompts

- `project_bootstrap`: Fetch relevant memory before non-trivial work.
- `project_handoff`: Store only durable learnings after a task.
- `project_cleanup`: Review stale, contradictory, or low-confidence memory.

## User Memory

User memory is global: it is not scoped to any project. It stores stable facts about the person you are working with so agents can apply them across all sessions and repositories.

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
- Project-specific knowledge: use project memory instead.
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

- `user.remember`: Store durable user memory after quality and secret checks. Requires `why_useful_later`. Idempotent by content.
- `user.search`: Vector search user memory with optional kind and tag filters. Supports `offset` for pagination.
- `user.brief`: Return compact preferences, behaviors, context, and recent user memories.
- `user.update`: Correct, refine, or archive an existing user memory.
- `user.forget`: Archive by default or hard-delete when requested.
- `user.purge`: Hard-delete archived user memories older than N days to prevent unbounded growth. Audit events are always preserved.

### User Memory Resources

- `memory://user/brief`: All four categories of user memory.

### User Memory Prompts

- `user_bootstrap`: Read user memory at the start of a session.
- `user_update`: Store durable user-level learnings after a session.

## Search

Memory search uses vector KNN exclusively. The query and all memories are embedded using `BAAI/bge-small-en-v1.5` (a 384-dimension sentence transformer via `fastembed`). Embeddings are stored in `sqlite-vec` virtual tables (`memory_vec`, `user_memory_vec`). At query time the nearest neighbours are retrieved by cosine distance using sqlite-vec's `MATCH` operator.

**Why vector search?**

Vector search finds memories by meaning, not word overlap. A query for "login issue" will surface a memory about "authentication problem with tokens" even though the two share no words, because the embedding model places them near each other in the 384-dimensional vector space.

**Atomicity**

`remember()` is atomic. If embedding fails after the memory row is written, the row is hard-deleted and the error is re-raised. There are no half-written records and no backfill step.

**Model and caching**

The embedding model (~130 MB ONNX) is downloaded once on first use and cached locally by `fastembed` at the default HuggingFace cache path (`~/.cache/huggingface/hub`). Subsequent starts load from cache with no network access required.

## Development

From the repository root:

```bash
make format
make lint
make test
```

From this directory:

```bash
uv sync
uv run ruff format src tests
uv run ruff check src tests
uv run pytest
```

Smoke test the stdio server:

```bash
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"smoke","version":"0.0.0"}}}' \
  | AGENT_MEMORY_DIR=/tmp/agent-memory-smoke uv run --directory . agent-memory
```

## Important Behavior

- Memory is a hint, not authority. Current user instructions, repo files, tests, and official docs override memory.
- Archived memories are excluded from normal search; pass `include_archived=True` to include them.
- Hard delete removes the memory row but always keeps an audit event.
- `remember()` is atomic: if embedding fails the memory row is rolled back immediately.
- The `AGENT_MEMORY_DIR` environment variable overrides the storage directory; the database is placed directly inside it as `memory.sqlite`.
