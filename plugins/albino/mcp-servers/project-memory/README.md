# Project Memory MCP Server

Local MCP server for durable project memory. It lets agents retrieve useful project knowledge before work and store reusable learnings after work.

The server is intentionally local-first:

- Runs over MCP stdio.
- Stores memory in SQLite.
- Uses SQLite FTS for search.
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
~/.myagents/memory.sqlite
```

Override the storage directory with:

```bash
MYAGENTS_MEMORY_DIR=/custom/memory/dir
```

When set, the database path becomes:

```text
/custom/memory/dir/memory.sqlite
```

The database is ignored by git.

## What Gets Stored

Good memory:

- Stable project conventions.
- Decisions that affect future implementation.
- Non-obvious architecture facts.
- Repeated gotchas.
- Recurring bug root causes.
- Important user preferences.
- Setup or workflow details that are hard to rediscover.

Bad memory:

- Secrets, tokens, credentials, cookies, private keys, or `.env` values.
- Raw command output.
- Temporary task state.
- Vague summaries like "fixed the issue".
- Facts already obvious from current files unless the memory adds durable interpretation.

Every stored memory must include `whyUsefulLater`.

## Tools

The server exposes these MCP tools:

- `memory.remember`: Store durable memory after quality and secret checks.
- `memory.search`: Search project memory with optional kind and tag filters.
- `memory.get`: Fetch one memory by id.
- `memory.project_brief`: Return compact conventions, decisions, pitfalls, and recent memory.
- `memory.update`: Correct, refine, or archive an existing memory.
- `memory.forget`: Archive by default or hard-delete when requested.
- `memory.capture_task_summary`: Store reusable end-of-task learnings.
- `memory.export_project`: Export project memory for backup or migration.
- `memory.import_project`: Import a project memory export.
- `memory.link_project_paths`: Explicitly link another checkout path to the same project memory.
- `memory.possible_project_matches`: Find same-git-remote paths without automatically linking them.

## Resources

The server exposes these MCP resources:

- `memory://project/current/brief`
- `memory://project/current/conventions`
- `memory://project/current/decisions`
- `memory://project/current/pitfalls`
- `memory://project/current/recent`

These resources are compact JSON context for agents.

## Prompts

The server exposes these MCP prompts:

- `memory_bootstrap`: Fetch relevant memory before non-trivial work.
- `memory_handoff`: Store only durable learnings after a task.
- `memory_cleanup`: Review stale, contradictory, or low-confidence memory.

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
- Archived memories are excluded from normal search.
- `includeArchived` can include archived memories in search.
- Hard delete removes the memory row but keeps a project-scoped audit event.
- Same git remote paths are only linked when `memory.link_project_paths` is called explicitly.
