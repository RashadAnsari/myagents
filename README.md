# myagents

Personal plugin marketplace for Claude Code, Cursor, and Claude Desktop. Brings Rashad's workflows, review agents, and development conventions to any project.

---

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/RashadAnsari/myagents/master/install.sh | bash
```

Installs for whichever platforms are detected:

- **Claude Code**: registers the marketplace and installs the plugin
- **Cursor**: symlinks the plugin to `~/.cursor/plugins/local/albino`
- **Claude Desktop**: merges MCP servers into `claude_desktop_config.json`

Rerun to update. Restart your editor after install.

---

## Contents

- [Plugins](#plugins)
  - [Commands](#commands)
  - [Agents](#agents)
  - [Skills](#skills)
  - [MCP Servers](#mcp-servers)
  - [Hooks](#hooks)
- [Claude Desktop](#claude-desktop)
- [Repository Rules](#repository-rules)

---

## Plugins

### albino

Personal productivity plugin for Claude Code and Cursor.

#### Commands

Slash commands available in Claude Code and Cursor sessions.

| Command | Description |
|---------|-------------|
| `/reviewcrew` | Full codebase audit: runs all review agents in parallel and writes `REVIEW_REPORT.md` |
| `/reportloop` | Walk through every issue in `REVIEW_REPORT.md` interactively: explain, fix, or skip one by one |
| `/statusline` | Configure the Claude Code statusline: shows current directory, git branch and dirty state, model, context usage, and time (Claude Code only) |
| `/commit` | Stage all changes and create a git commit with an appropriate message |
| `/commit-pr` | Stage all changes, commit, and open a pull request. Creates a new branch first if currently on main or master |
| `/pr-review <url>` | Review a GitHub pull request: selects relevant reviewers, loads project and user memory, hunts for ripple effects, humanizes findings, then asks which to post before submitting via `gh` |
| `/remember <what>` | Save something to agent memory: classifies the input (or current session learnings if omitted) as project or user memory and stores it via the agent-memory MCP server |
| `/forget <what>` | Remove something from agent memory: searches both project and user memory and immediately soft-deletes all matching entries |
| `/enrich` | Enrich project memory by mining the 100 most recently merged PRs: spawns parallel extractor agents to pull decisions, conventions, gotchas, and architectural facts from PR bodies, review comments, and discussions, then writes durable learnings to project memory |

#### Agents

Specialist review agents spawned in parallel by `/reviewcrew`, also available individually.

| Agent | Covers |
|-------|--------|
| `security-reviewer` | Injection, XSS, auth, SSRF, JWT, and supply chain vulnerabilities |
| `code-reviewer` | Correctness, style, anti-patterns, performance, memory, and concurrency |
| `architecture-reviewer` | Structure, coupling, cohesion, SOLID, duplication, and observability |
| `performance-reviewer` | Bottlenecks, complexity, queries, caching, and scalability |
| `test-reviewer` | Coverage, assertion quality, flakiness, mocking, and test data |
| `logging-reviewer` | Logging gaps, audit trail, monitoring, and sensitive data in logs |
| `dependency-reviewer` | Vulnerable, outdated, and unused packages plus supply chain risk |
| `docs-reviewer` | Documentation accuracy, completeness, and staleness |
| `agents-md-reviewer` | Codebase compliance with `AGENTS.md` rules |
| `accessibility-reviewer` | WCAG compliance, ARIA usage, keyboard navigation, and screen reader support |
| `api-design-reviewer` | REST/GraphQL naming, HTTP semantics, versioning, error shape, and backward compatibility |
| `database-reviewer` | Schema design, migration safety, indexing strategy, constraints, and query patterns |
| `i18n-reviewer` | Hardcoded strings, date/number formatting, pluralization, RTL layout, and locale handling |

#### Skills

Behavioral guidelines injected into agent prompts.

**Mandatory** (always active, injected at session start via the `session-start` hook for both Claude Code and Cursor):

| Skill | Description |
|-------|-------------|
| `dev-conventions` | Development conventions: think before coding, simplicity first, duplication and extraction discipline, surgical changes, localization, UI, validation, data alignment, goal-driven execution |
| `research-first` | Research docs and source before answering or implementing anything non-trivial, including always looking up the latest stable version of any dependency |
| `agent-memory` | Retrieves relevant project and user memory before non-trivial work and stores durable learnings after |

**Opt-in** (activate manually as needed):

| Skill | Description |
|-------|-------------|
| `caveman` | Kills verbosity for the session: drops filler, hedging, and pleasantries. Injects a brevity prefix into all spawned subagent prompts to keep tool results small. Exit with "stop caveman" or "normal mode" |
| `humanizer` | Removes signs of AI-generated writing from text |
| `frontend-design` | Creates distinctive, production-grade frontend interfaces: avoids generic AI aesthetics |
| `markitdown` | Converts files, URLs, and documents to Markdown using the markitdown MCP server |
| `plugin-authoring` | Best practices for writing skills, commands, and agents: descriptions, structure, token efficiency, frontmatter, and tool scoping |

#### MCP Servers

| Server | Description |
|--------|-------------|
| `agent-memory` | Stores and retrieves durable project knowledge and user preferences across sessions using semantic search. Rejects vague, duplicate, or secret-containing entries. |
| `playwright` | Browser automation via `@playwright/mcp`: navigate, click, fill forms, take screenshots, and inspect the DOM. Auto-installs bun if not present. If `PLAYWRIGHT_MCP_EXTENSION_TOKEN` is exported, starts with `--extension` to drive your real browser through the Playwright Chrome extension. |
| `markitdown` | Converts files, URLs, and documents to Markdown. Supports PDF, Word, PowerPoint, Excel, HTML, CSV, JSON, XML, ZIP, images (OCR), audio (transcription), EPubs, and YouTube URLs. Runs via `uv tool run markitdown-mcp`; auto-installs uv on first use. |

Project memory is stored outside git at `~/.myagents/agent-memory/memory.sqlite` by default. User memory is stored in the same database. Set `AGENT_MEMORY_DIR` to override. Project memories are scoped to the repository identity (a fingerprint of the normalized `origin` remote URL, so they follow the repo across clones and machines; the local root path is the fallback for repos without a remote). User memories are global across all projects. `project_search` accepts `all_projects: true` to search every known project's memories at once, with each result carrying `project_name` and `project_root` provenance.

#### Hooks

| Hook | Event | Platforms | Description |
|------|-------|-----------|-------------|
| `session-start` | `SessionStart` / `sessionStart` | Claude Code, Cursor | Injects mandatory skills, memory read/write rules, and session bootstrap at the start of every session |
| `user-prompt-submit` | `UserPromptSubmit` | Claude Code | Re-injects a one-line reminder on every prompt (search memory first, apply `AGENTS.md` and mandatory skills, store durable learnings), since session-start context decays over long conversations. Cursor gets the same effect via the always-applied `session-start` rule instead |
| `stop` | `Stop` / `stop` | Claude Code, Cursor | Checks at the end of every turn whether durable learnings (decisions, preferences, gotchas, conventions) were stored to agent memory before the agent finishes |

---

## Claude Desktop

`install.sh` detects Claude Desktop automatically and merges MCP servers into `claude_desktop_config.json`. Restart Claude Desktop after running it.

### MCP Servers

| Server | Description |
|--------|-------------|
| `agent-memory` | Stores and retrieves durable user preferences and knowledge across sessions. Runs via `run-with-uv.sh`; auto-installs `uv` on first use. |
| `playwright` | Browser automation via `@playwright/mcp`: navigate, click, fill forms, take screenshots, and inspect the DOM. Runs via `run-with-bunx.sh`; auto-installs `bun` on first use. If `PLAYWRIGHT_MCP_EXTENSION_TOKEN` is set in the app's environment, starts with `--extension` to drive your real browser through the Playwright Chrome extension. |
| `markitdown` | Converts files, URLs, and documents to Markdown. Supports PDF, Word, PowerPoint, Excel, HTML, CSV, JSON, XML, ZIP, images (OCR), audio (transcription), EPubs, and YouTube URLs. Runs via `run-with-uv.sh`; auto-installs `uv` on first use. |

### Skills

Skills for Claude Desktop are managed directly inside the app. Go to **Customize > Skills** to add, remove, or reorder skills. The installer does not manage skills for Claude Desktop.

| Skill | Description |
|-------|-------------|
| `agent-memory` | Remembers personal context across everyday conversations: health, food, travel, habits, goals, and communication style |
| `markitdown` | Converts files, URLs, and documents to Markdown using the markitdown MCP server |

---

## Repository Rules

See `AGENTS.md` for agent and convention rules that apply to this repository.
