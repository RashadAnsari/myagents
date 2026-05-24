# myagents

Personal plugin marketplace for Claude Code and Cursor. Brings Rashad's workflows, review agents, and development conventions to any project.

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/RashadAnsari/myagents/master/install.sh | bash
```

Installs for whichever platforms are detected:
- **Claude Code**: registers the marketplace and installs the plugin
- **Cursor**: symlinks the plugin to `~/.cursor/plugins/local/albino`

Rerun to update. Reload your editor after install.

---

## Plugins

### albino

Personal productivity plugin.

#### Commands

Slash commands available in Claude Code / Cursor sessions.

| Command | Description |
|---------|-------------|
| `/reviewcrew` | Full codebase audit: runs all review agents in parallel and writes `REVIEW_REPORT.md` |
| `/reportloop` | Walk through every issue in `REVIEW_REPORT.md` interactively: explain, fix or skip, one by one |
| `/statusline` | Configure the Claude Code statusline: asks global or project install, shows git branch, current directory, model, and time *(Claude Code only)* |
| `/commit` | Stage all changes and create a git commit with an appropriate message |
| `/caveman` | Switch to lite communication mode: drops filler/hedging/pleasantries for the session. Includes commit format, PR review style, file compression, and subagent delegation templates for spawning agents in caveman mode. |

#### Agents

Specialist review agents: spawned in parallel by `/reviewcrew` and available for individual use.

| Agent | Description |
|-------|-------------|
| `security-reviewer` | Audits for security vulnerabilities: injection, XSS, auth, SSRF, JWT, supply chain, and more |
| `code-reviewer` | Reviews correctness, style, anti-patterns, performance, memory, and concurrency |
| `architecture-reviewer` | Reviews structure, coupling, cohesion, SOLID, duplication, and observability |
| `performance-reviewer` | Reviews bottlenecks, complexity, queries, caching, and scalability |
| `test-reviewer` | Reviews coverage, assertion quality, flakiness, mocking, and test data |
| `logging-reviewer` | Reviews logging gaps, audit trail, monitoring, and sensitive data in logs |
| `dependency-reviewer` | Reviews vulnerable, outdated, unused packages and supply chain risk |
| `docs-reviewer` | Reviews documentation accuracy, completeness, and staleness |
| `agents-md-reviewer` | Reviews codebase against `AGENTS.md` rules |
| `accessibility-reviewer` | Reviews WCAG compliance, ARIA usage, keyboard navigation, and screen reader compatibility. Use when: adding interactive components, building forms, or auditing UI for assistive-technology support. |
| `api-design-reviewer` | Reviews REST/GraphQL naming, HTTP semantics, versioning, error shape, and backward compatibility. Use when: designing new endpoints, changing existing API contracts, or reviewing client-facing interfaces. |
| `database-reviewer` | Reviews schema design, migration safety, indexing strategy, constraints, and query patterns. Use when: adding tables, writing migrations, or auditing existing schema for correctness and safety. |
| `i18n-reviewer` | Reviews hardcoded strings, date/number formatting, pluralization, RTL layout, and locale handling. Use when: adding user-visible text, date or number formatting, or preparing the app for a new locale. |

#### Skills

Behavioral guidelines injected into agent prompts. The six mandatory skills are always active; the rest are opt-in.

| Skill | Description |
|-------|-------------|
| `agent-protocol` | Mandatory: enforces `AGENTS.md` rules on every agent spawn |
| `code-reusability` | Spots duplication and applies extraction patterns |
| `dev-conventions` | General conventions: reuse, scope, localization, UI, validation, data |
| `latest-versions` | Always look up and use the latest stable version of any dependency |
| `research-first` | Research docs and source before answering or implementing anything non-trivial |
| `agent-memory` | Retrieves relevant project memory before non-trivial work and stores durable learnings after the task |
| `humanizer` | Removes signs of AI-generated writing from text |
| `frontend-design` | Creates distinctive, production-grade frontend interfaces: avoids generic AI aesthetics |

#### MCP Servers

| Server | Description |
|--------|-------------|
| `agent-memory` | Stores and retrieves durable project knowledge and user preferences across sessions. Supports semantic search so agents can recall relevant decisions, conventions, and gotchas before starting a task. Rejects vague, duplicate, or secret-containing entries. |

Project memory is stored outside git at `~/.myagents/agent-memory/memory.sqlite` by default. User memory is stored in the same database. Set `AGENT_MEMORY_DIR` to override the storage directory. Project memories are scoped to the repository root; user memories are stored globally across all projects.

#### Hooks

| Hook | Event | Description |
|------|-------|-------------|
| `session-start` | `SessionStart` / `sessionStart` | Bootstraps project memory and user preferences before the first prompt |
| `user-prompt-submit` | `UserPromptSubmit` / `beforeSubmitPrompt` | Injects mandatory `AGENTS.md` reminder and active skill list before every prompt |

#### Rules

Cursor rules (`.mdc` files): always applied to every Cursor agent session.

| Rule | Description |
|------|-------------|
| `session-memory` | Bootstraps project memory at conversation start and prompts memory handoff at conversation end *(covers Cursor `stop` gap)* |

---

## Rules

See `AGENTS.md` for agent and convention rules that apply to this repository.
