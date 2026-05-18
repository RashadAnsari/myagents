# myagents

Personal plugin marketplace for Claude Code and Cursor. Brings Rashad's workflows, review agents, and development conventions to any project.

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/RashadAnsari/myagents/master/install.sh | bash
```

Installs for whichever platforms are detected:
- **Claude Code** — registers the marketplace and installs the plugin
- **Cursor** — symlinks the plugin to `~/.cursor/plugins/local/albino`

Rerun to update. Reload your editor after install.

---

## Plugins

### albino

Personal productivity plugin.

#### Commands

| Command | Description |
|---------|-------------|
| `/ultrareview` | Full codebase audit — runs all review agents in parallel and writes `REVIEW_REPORT.md` |
| `/ultrafix` | Walk through every issue in `REVIEW_REPORT.md` interactively — explain, fix or skip, one by one |
| `/agents-md-review` | Review codebase for inconsistencies with `AGENTS.md` rules |
| `/configure-statusline` | Configure the Claude Code statusline — asks global or project install, shows git branch, current directory, model, and time *(Claude Code only)* |
| `/commit` | Stage all changes and create a git commit with an appropriate message |
| `/caveman` | Switch to lite communication mode — drops filler/hedging/pleasantries for the session. Includes commit format, PR review style, file compression, and subagent delegation guide. |
| `/goal` | Goal-oriented orchestration — state a goal with success criteria, execute toward it, verify, and loop until every criterion passes |

#### Agents

| Agent | Description |
|-------|-------------|
| `security-reviewer` | Audits for security vulnerabilities — injection, XSS, auth, SSRF, JWT, supply chain, and more |
| `code-reviewer` | Reviews correctness, style, anti-patterns, performance, memory, and concurrency |
| `architecture-reviewer` | Reviews structure, coupling, cohesion, SOLID, duplication, and observability |
| `performance-reviewer` | Reviews bottlenecks, complexity, queries, caching, and scalability |
| `test-reviewer` | Reviews coverage, assertion quality, flakiness, mocking, and test data |
| `logging-reviewer` | Reviews logging gaps, audit trail, monitoring, and sensitive data in logs |
| `dependency-reviewer` | Reviews vulnerable, outdated, unused packages and supply chain risk |
| `docs-reviewer` | Reviews documentation accuracy, completeness, and staleness |
| `agents-md-reviewer` | Reviews codebase against `AGENTS.md` rules |
| `accessibility-reviewer` | Reviews WCAG compliance, ARIA usage, keyboard navigation, and screen reader compatibility |
| `api-design-reviewer` | Reviews REST/GraphQL naming, HTTP semantics, versioning, error shape, and backward compatibility |
| `database-reviewer` | Reviews schema design, migration safety, indexing strategy, constraints, and query patterns |
| `i18n-reviewer` | Reviews hardcoded strings, date/number formatting, pluralization, RTL layout, and locale handling |
| `humanizer` | Removes AI writing patterns from text |

#### Skills

| Skill | Description |
|-------|-------------|
| `agent-protocol` | Mandatory — enforces `AGENTS.md` rules on every agent spawn |
| `code-reusability` | Spots duplication and applies extraction patterns |
| `dev-conventions` | General conventions — reuse, scope, localization, UI, validation, data |
| `latest-versions` | Always look up and use the latest stable version of any dependency |
| `research-first` | Research docs and source before answering or implementing anything non-trivial |
| `project-memory` | Retrieves relevant project memory before non-trivial work and stores durable learnings after the task |
| `humanizer` | Removes signs of AI-generated writing from text |
| `frontend-design` | Creates distinctive, production-grade frontend interfaces — avoids generic AI aesthetics |

#### MCP Servers

| Server | Description |
|--------|-------------|
| `project-memory` | Bun-powered local stdio MCP server for durable project and user memory with SQLite FTS search, quality gates, secret rejection, export/import, and explicit checkout path linking |

Project memory is stored outside git at `~/.myagents/project-memory/memory.sqlite` by default. User memory is stored in the same database. Set `MYAGENTS_MEMORY_DIR` to override the storage directory. Memories are keyed by project root (project memory) or stored globally (user memory) and can be exported or imported through the MCP tools.

#### Hooks

| Event | Hook | Description |
|-------|------|-------------|
| `UserPromptSubmit` / `beforeSubmitPrompt` | `agents-reminder` | Injects mandatory `AGENTS.md` reminder and active skill list before every prompt |

---

## Rules

See `AGENTS.md` for agent and convention rules that apply to this repository.
