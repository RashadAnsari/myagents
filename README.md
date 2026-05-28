# myagents

Personal plugin marketplace for Claude Code and Cursor. Brings Rashad's workflows, review agents, and development conventions to any project.

---

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/RashadAnsari/myagents/master/install.sh | bash
```

Installs for whichever platforms are detected:

- **Claude Code**: registers the marketplace and installs the plugin
- **Cursor**: symlinks the plugin to `~/.cursor/plugins/local/albino`

Rerun to update. Reload your editor after install.

---

## Contents

- [Plugins](#plugins)
  - [Commands](#commands)
  - [Agents](#agents)
  - [Skills](#skills)
  - [MCP Servers](#mcp-servers)
  - [Hooks](#hooks)
  - [Cursor Rules](#cursor-rules)
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
| `/statusline` | Configure the Claude Code statusline: shows git branch, current directory, model, and time (Claude Code only) |
| `/commit` | Stage all changes and create a git commit with an appropriate message |
| `/caveman` | Kill verbosity for the session: drops filler, hedging, and pleasantries. Injects a brevity prefix into all spawned subagent prompts to keep tool results small |
| `/pr-review <url>` | Review a GitHub pull request: selects relevant reviewers, loads project and user memory, hunts for ripple effects, humanizes findings, then asks which to post before submitting via `gh` |
| `/remember [what]` | Save something to agent memory: classifies the input (or current session learnings if omitted) as project or user memory and stores it via the agent-memory MCP server |
| `/forget <what>` | Remove something from agent memory: searches both project and user memory and immediately soft-deletes all matching entries |

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

**Mandatory** (always active, injected before every prompt via the `user-prompt-submit` hook):

| Skill | Description |
|-------|-------------|
| `agent-protocol` | Enforces `AGENTS.md` rules on every agent spawn |
| `code-reusability` | Spots duplication and applies extraction patterns |
| `dev-conventions` | General conventions: reuse, scope, localization, UI, validation, and data |
| `latest-versions` | Always look up and use the latest stable version of any dependency |
| `research-first` | Research docs and source before answering or implementing anything non-trivial |
| `agent-memory` | Retrieves relevant project and user memory before non-trivial work and stores durable learnings after |

**Opt-in** (activate manually as needed):

| Skill | Description |
|-------|-------------|
| `humanizer` | Removes signs of AI-generated writing from text |
| `frontend-design` | Creates distinctive, production-grade frontend interfaces: avoids generic AI aesthetics |

#### MCP Servers

| Server | Description |
|--------|-------------|
| `agent-memory` | Stores and retrieves durable project knowledge and user preferences across sessions using semantic search. Rejects vague, duplicate, or secret-containing entries. |
| `playwright` | Browser automation via `@playwright/mcp`: navigate, click, fill forms, take screenshots, and inspect the DOM. Auto-installs bun if not present. |

Project memory is stored outside git at `~/.myagents/agent-memory/memory.sqlite` by default. User memory is stored in the same database. Set `AGENT_MEMORY_DIR` to override. Project memories are scoped to the repository root; user memories are global across all projects.

#### Hooks

| Hook | Event | Description |
|------|-------|-------------|
| `session-start` | `SessionStart` / `sessionStart` | Bootstraps project memory and user preferences before the first prompt |
| `user-prompt-submit` | `UserPromptSubmit` / `beforeSubmitPrompt` | Injects the mandatory `AGENTS.md` reminder and active skill list before every prompt |

#### Cursor Rules

`.mdc` files applied to every Cursor agent session.

| Rule | Description |
|------|-------------|
| `session-memory` | Bootstraps project memory at conversation start and prompts memory handoff at the end (covers the Cursor `stop` gap) |

---

## Repository Rules

See `AGENTS.md` for agent and convention rules that apply to this repository.
