# myagents

[![Build](https://github.com/RashadAnsari/myagents/actions/workflows/build.yml/badge.svg)](https://github.com/RashadAnsari/myagents/actions/workflows/build.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Platforms](https://img.shields.io/badge/works%20with-Claude%20Code%20%7C%20Cursor%20%7C%20Codex%20%7C%20Claude%20Desktop-555)

**One command to give every AI coding agent you use the same memory, reviewers, and working rules.**

Coding agents start every session from zero. They forget what your team decided last week, skip the conventions in `AGENTS.md`, guess at library versions, and review code in one generic pass. myagents fixes that across Claude Code, Cursor, Codex, and Claude Desktop at once:

- **Memory that persists.** Agents look up project decisions and your preferences before they start, and save new ones when they finish. Memory follows the repository across clones and machines.
- **14 specialist reviewers.** Security, performance, architecture, tests, accessibility, database, dead code, and more. Run all of them in parallel, pick one, or point them at a GitHub pull request.
- **Rules that stay on.** Research before guessing, the simplest change that works, no filler in answers. Hooks load them at the start of every session and repeat them on every prompt, so they hold up in long conversations.
- **One install, four tools.** The installer finds the tools you have and sets up each one the way that tool expects. Rerun it to update.

---

## Quick start

On macOS, run this. It installs any missing tools it needs with Homebrew, and installs Homebrew first if you don't have it:

```bash
curl -fsSL https://raw.githubusercontent.com/RashadAnsari/myagents/master/install.sh | bash
```

```
myagents
  ✓ Download        Saved to ~/.myagents (version 65f708b).
  ✓ Requirements    All installed.
  ✓ Apps            Found Claude Code, Cursor, Codex, Claude Desktop.

albino
  ✓ Claude Code     Installed. Restart open sessions to load it.
  ✓ Cursor          Installed. Run 'Developer: Reload Window' to load it.
  ✓ Codex           Installed. Restart Codex, then run /hooks once to trust its hooks.
  ✓ Claude Desktop  MCP servers added. Restart Claude Desktop to load them.

context7
  ✓ Claude Code     Installed. Restart open sessions, then run /mcp once to sign in to Context7.
  ✓ Cursor          Installed. Sign in to Context7 when Cursor asks, or from Cursor Settings > MCP.
  ✓ Codex           Installed. Run 'codex mcp login context7' once to sign in.

ponytail
  ✓ Claude Code     Installed. Restart open sessions to load it.
  ✓ Codex           Installed. Restart Codex, then run /hooks once to trust its hooks.
  ✓ Cursor          Installed. Start a new chat to load it.

security-audit
  ✓ Claude Code     Installed. Restart open sessions to load it.
  ✓ Cursor          Installed. Start a new chat to load it.
  ✓ Codex           Installed. Restart Codex to load it.

ui-ux-pro-max
  ✓ Claude Code     Installed. Restart open sessions to load it.
  ✓ Cursor          Installed. Start a new chat to load it.
  ✓ Codex           Installed. Restart Codex to load it.

Summary
  ✓ albino          Ready.
  ✓ context7        Ready.
  ✓ ponytail        Ready.
  ✓ security-audit  Ready.
  ✓ ui-ux-pro-max   Ready.
```

Then try it in any project:

```
/reviewcrew                       # every reviewer in parallel, report in REVIEW_REPORT.md
/audit security src/api           # one reviewer, one folder
/pr-review https://github.com/org/repo/pull/42
/remember we deploy from the release branch, never from master
```

To update, run the same install command again.

---

## Contents

- [Plugins](#plugins): [albino](#albino), [ponytail](#ponytail), [security-audit](#security-audit), [context7](#context7), [ui-ux-pro-max](#ui-ux-pro-max)
- [Platform support](#platform-support)
- [Agent memory](#agent-memory)
- [Installing, updating, and uninstalling](#installing-updating-and-uninstalling)
- [Adding a plugin](#adding-a-plugin)
- [License](#license)

---

## Plugins

### albino

The main plugin: commands, review agents, skills, MCP servers, and hooks.

#### Commands

| Command | What it does |
|---------|--------------|
| `/reviewcrew` | Runs every review agent in parallel and writes a consolidated `REVIEW_REPORT.md` |
| `/reportloop` | Walks through `REVIEW_REPORT.md` one issue at a time, by severity: explains it, then fixes or skips it |
| `/audit [reviewer] [path]` | Runs one reviewer of your choice, optionally on one path, and prints its findings |
| `/pr-review <url>` | Reviews a GitHub pull request: picks the reviewers that fit the changed files, loads memory, checks ripple effects, lets you choose which findings to post, and submits the review with `gh` |
| `/commit` | Stages all changes and writes a commit message in the project's existing style |
| `/commit-pr` | Commits and opens a pull request, creating a branch first when you are on `main` or `master` |
| `/remember <what>` | Saves something to project or user memory, or this session's learnings when given nothing |
| `/forget <what>` | Finds and removes matching entries from project and user memory |
| `/enrich` | Mines the 100 most recently merged pull requests for decisions, conventions, and gotchas, and saves them to project memory |
| `/statusline` | Sets the Claude Code status line: folder, git branch and dirty state, model, context usage, and time |

On Codex, commands become skills (`albino:source-command-<name>` or `albino-command-<name>`). Ask for them by name instead of with a slash.

#### Review agents

Used by `/reviewcrew`, `/audit`, and `/pr-review`, or on their own.

| Agent | Looks for |
|-------|-----------|
| `security-reviewer` | Injection, XSS, auth flaws, SSRF, JWT misuse, and supply chain risk |
| `code-reviewer` | Correctness, anti-patterns, concurrency, and memory bugs |
| `architecture-reviewer` | Structure, coupling, cohesion, SOLID, and duplication |
| `performance-reviewer` | Bottlenecks, complexity, slow queries, caching, and scalability |
| `test-reviewer` | Coverage gaps, weak assertions, flaky tests, and over-mocking |
| `logging-reviewer` | Logging and monitoring gaps, audit trails, and sensitive data in logs |
| `dependency-reviewer` | Vulnerable, outdated, and unused packages |
| `docs-reviewer` | Documentation that is wrong, missing, or stale |
| `agents-md-reviewer` | Code that breaks the rules in `AGENTS.md` |
| `accessibility-reviewer` | WCAG, ARIA, keyboard navigation, and screen reader support |
| `api-design-reviewer` | REST and GraphQL naming, HTTP semantics, versioning, error shape, and compatibility |
| `database-reviewer` | Schema design, migration safety, indexes, constraints, and query patterns |
| `i18n-reviewer` | Hardcoded strings, date and number formatting, plurals, RTL, and locale handling |
| `unused-code-reviewer` | Dead code, tests, CI jobs, infrastructure, config, docs, and assets across the whole repository |

#### Skills

Three skills are always on. The session-start hook tells the agent to load each one in full before its first answer.

| Skill | What it enforces |
|-------|------------------|
| `dev-conventions` | Think before coding, the simplest change that works, no duplication, surgical edits, and checkable success criteria |
| `research-first` | Read the docs and source before answering, and use the latest stable version of every dependency |
| `agent-memory` | Search memory before non-trivial work, and save durable learnings after it |

The rest load when a task calls for them:

| Skill | Use it for |
|-------|------------|
| `frontend-design` | Distinctive, production-grade interfaces that avoid the generic AI look |
| `humanizer` | Removing the signs of AI-generated writing from text |
| `markitdown` | Converting PDFs, Office files, images, audio, and URLs to Markdown |
| `plugin-authoring` | Writing skills, commands, and agents that trigger reliably and use few tokens |
| `eu-ai-act` | EU AI Act risk tiers, obligations, deadlines, and penalties |

#### MCP servers

| Server | What it adds |
|--------|--------------|
| `agent-memory` | Project and user memory with semantic search. Rejects vague, duplicate, and secret-containing entries. See [Agent memory](#agent-memory) |
| `playwright` | Browser automation: navigate, click, fill forms, take screenshots, and inspect the page. Set `PLAYWRIGHT_MCP_EXTENSION_TOKEN` to drive your real browser through the Playwright Chrome extension |
| `markitdown` | Converts PDF, Word, PowerPoint, Excel, HTML, images (OCR), audio (transcription), EPUB, and YouTube URLs to Markdown |

Claude Desktop gets `playwright` plus `linkedin`, which reads LinkedIn profiles, companies, and job posts through your own browser session via [`mcp-server-linkedin`](https://github.com/stickerdaniel/linkedin-mcp-server). It needs no API key: a login window opens the first time a tool needs it.

Each server installs its own runtime (`bun` or `uv`) on first use.

#### Hooks

| Hook | Runs | What it does |
|------|------|--------------|
| `session-start` | Start of every session | Loads the mandatory skills, the memory rules, and the communication rules: answer first, be precise, no filler |
| `user-prompt-submit` | Every prompt | Repeats a one-line reminder of those rules, since session-start context fades in long conversations |
| `stop` | End of every turn | Asks the agent whether it learned anything durable and, if so, to save it before finishing |

### ponytail

[ponytail](https://github.com/DietrichGebert/ponytail) by Dietrich Gebert is a third-party plugin that pushes agents toward the shortest solution that works: YAGNI, standard library first, no abstractions nobody asked for. The installer sets it up with each tool's own method and keeps it up to date. Its hooks need `node`.

### security-audit

[security-audit](https://github.com/cloudflare/security-audit-skill) by Cloudflare is the skill that seeded Cloudflare's vulnerability discovery harness. Ask for a security audit and it runs isolated agents through reconnaissance, coverage-led hunting, and validation, where a fresh agent tries to disprove every finding, then writes a report with confirmed findings and open leads. Reports default to `~/security-audit-skill/<repo-name>/`. It complements albino's `security-reviewer`, which gives a quicker single-pass review.

The installer adds it with the [Skills CLI](https://skills.sh), with install telemetry turned off. It needs `node`, and building or running the audited code needs an OS-level sandbox; without one, the skill reports those leads as unconfirmed instead of executing the target.

### context7

[Context7](https://github.com/upstash/context7) by Upstash gives agents current, version-specific documentation for libraries and frameworks, pulled from their source repositories, so they stop guessing at APIs that changed after their training data. It pairs with albino's `research-first` skill, which tells agents to check the docs before answering; Context7 is where they read them. Ask a library question and it resolves the library, then fetches the relevant docs.

The installer runs Context7's own `ctx7 setup --mcp --oauth` for each tool, which adds its MCP server, a rule that tells the agent when to use it, and a `context7-mcp` skill. Sign-in happens in the app the first time, so no API key is stored on disk: run `/mcp` in Claude Code, sign in when Cursor asks, or run `codex mcp login context7`. For Codex, the rule is added as a marked block in `~/.codex/AGENTS.md`, and uninstalling removes only that block. Telemetry is turned off.

### ui-ux-pro-max

[UI UX Pro Max](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) by nextlevelbuilder gives agents a searchable local design database: 79 styles, 192 product palettes, 74 font pairings, 119 UX guidelines, 25 chart types, and guidance for 22 stacks, from React and SwiftUI to Flutter and Tailwind. It activates on its own when you build, review, or fix an interface, and can generate a design system for your product. It overlaps with albino's `frontend-design` skill, which sets a visual direction; this one supplies the concrete styles, palettes, and stack rules.

It ships seven skills: `ui-ux-pro-max`, `design`, `design-system`, `ui-styling` (shadcn/ui and Tailwind), `brand`, `banner-design`, and `slides`. The installer follows the project's own instructions: the upstream marketplace for Claude Code, and its `uipro` CLI for Cursor (`~/.cursor/skills`) and Codex (`~/.agents/skills`). Its search scripts need `python3`.

---

## Platform support

| | Claude Code | Cursor | Codex | Claude Desktop |
|---|:---:|:---:|:---:|:---:|
| albino commands | ✓ | ✓ | ✓ as skills | |
| albino review agents | ✓ | ✓ | ✓ | |
| albino skills | ✓ | ✓ | ✓ | |
| albino hooks | ✓ | ✓ | ✓ after `/hooks` | |
| albino MCP servers | ✓ | ✓ | ✓ | ✓ `playwright`, `linkedin` |
| ponytail | ✓ | ✓ hooks | ✓ after `/hooks` | |
| security-audit | ✓ | ✓ | ✓ | |
| context7 | ✓ | ✓ | ✓ | |
| ui-ux-pro-max | ✓ | ✓ | ✓ | |

<details>
<summary>How albino is packaged for each tool</summary>

Every tool reads the same source files. Only the packaging differs.

| Component | Claude Code | Cursor | Codex |
|-----------|-------------|--------|-------|
| Manifest | `.claude-plugin/plugin.json` | `.cursor-plugin/plugin.json` | `.codex-plugin/plugin.json` |
| Marketplace | `.claude-plugin/marketplace.json` | `.cursor-plugin/marketplace.json` | `.agents/plugins/marketplace.json` |
| Skills | plugin `skills/` | plugin `skills/` | plugin `skills/` |
| MCP servers | `.mcp.json` | `.mcp.json` | `.mcp.json` |
| Hooks | manifest `hooks` block | manifest `hooks` block | manifest `hooks` block |
| Commands | plugin `commands/` | plugin `commands/` | plugin `commands/`, or generated into `$CODEX_HOME/skills/` where Codex skips one |
| Agents | plugin `agents/` | plugin `agents/` | generated into `$CODEX_HOME/agents/` as TOML |

Two things differ on Codex:

- **Commands become skills.** Codex converts a plugin's commands itself but skips any that use `$ARGUMENTS`, use inline shell expansion, or exceed roughly 3.8 KB. The installer generates those into `$CODEX_HOME/skills/` as `albino-command-<name>`, with `$ARGUMENTS` replaced by an instruction to take the subject from the request. `allowed-tools` is ignored.
- **Agents are generated as TOML** by `plugins/albino/scripts/gen-codex-agents.sh`. The Markdown files stay the source of truth, and `readonly: true` becomes `sandbox_mode = "read-only"`.

Cursor drops the context a `sessionStart` hook returns, so the same text reaches Cursor through the always-applied rule `plugins/albino/rules/session-start.mdc`.

</details>

---

## Agent memory

Memory lives in one SQLite database at `~/.myagents/agent-memory/memory.sqlite`, outside every repository. Set `AGENT_MEMORY_DIR` to move it.

- **Project memory** is tied to the repository's `origin` remote, so it follows the repo across clones and machines. Repositories without a remote fall back to their local path.
- **User memory** holds your preferences and applies to every project.
- `project_search` with `all_projects: true` searches every project at once, and each result says which repository it came from.

Uninstalling keeps your memory unless you pass `--purge`.

---

## Installing, updating, and uninstalling

The installer downloads this repository to `~/.myagents` and makes sure the tools listed in [`requirements.list`](requirements.list) are available: `jq`, `node`, `uv`, and `bun`. It installs only the ones not already on your PATH, with Homebrew, so tools you installed another way are left alone. If something is missing and Homebrew is not installed, it installs Homebrew first, which may ask for your password, and adds Homebrew to your PATH in `~/.zprofile`. `git` and `python3` come with the Xcode Command Line Tools (`xcode-select --install`).

Then it runs `plugins/<name>/install.sh` for each plugin. Each plugin installs into whichever tools it finds:

| Tool | What albino's installer does |
|------|------------------------------|
| Claude Code | Registers the `myagents` marketplace and enables the plugin |
| Cursor | Links the plugin into `~/.cursor/plugins/local/albino` |
| Codex | Adds the marketplace, installs the plugin, and generates command skills and agents. Run `/hooks` once in Codex to trust the hooks |
| Claude Desktop | Adds the MCP servers to `claude_desktop_config.json` |

**Updating.** Run the install command again. Every step is safe to repeat: a rerun updates what is there and never duplicates settings, hooks, or links. `~/.myagents` belongs to the installer, so a rerun resets it to the latest version and discards local edits to tracked files. Untracked files, such as the memory database, are kept.

**Uninstalling.** This undoes every install step on every tool, including settings, hooks, MCP servers, and the generated Codex skills and agents, then deletes `~/.myagents`. Your own settings, hooks, skills, and agents are left alone, and so is your agent memory. Homebrew and the tools from `requirements.list` stay installed, since other software may use them; remove them with `brew uninstall` if you no longer need them.

```bash
curl -fsSL https://raw.githubusercontent.com/RashadAnsari/myagents/master/uninstall.sh | bash
```

Add `--purge` to delete your agent memory too:

```bash
curl -fsSL https://raw.githubusercontent.com/RashadAnsari/myagents/master/uninstall.sh | bash -s -- --purge
```

Rerunning the uninstaller is safe: steps with nothing left to undo report "Already removed." If a step fails, `~/.myagents` is kept so you can fix the problem and rerun.

---

## Adding a plugin

Each folder in `plugins/` holds either a full plugin or just the scripts that install a third-party one. Add `plugins/<name>/install.sh` and `plugins/<name>/uninstall.sh`, and the root scripts pick them up. They run with `bash`, with `MYAGENTS_DIR` (the checkout path) and `MYAGENTS_MARKETPLACE` (`myagents`) exported.

Source `scripts/install-lib.sh` so both scripts are safe to rerun and print the same messages as the other plugins. A third-party plugin published as Claude Code and Codex marketplaces needs only this:

```bash
# plugins/<name>/install.sh
#!/usr/bin/env bash
set -euo pipefail
source "$MYAGENTS_DIR/scripts/install-lib.sh"

REPO_URL="https://github.com/owner/repo.git"

has_claude_code && claude_marketplace_plugin "$REPO_URL" <marketplace> <plugin>
has_codex && codex_marketplace_plugin "$REPO_URL" <marketplace> <plugin>

finish
```

```bash
# plugins/<name>/uninstall.sh
#!/usr/bin/env bash
set -euo pipefail
source "$MYAGENTS_DIR/scripts/install-lib.sh"

has_claude_code && claude_marketplace_plugin_remove <marketplace> <plugin>
has_codex && codex_marketplace_plugin_remove <marketplace> <plugin>

finish
```

<details>
<summary>Helpers in <code>scripts/install-lib.sh</code></summary>

| Helper | Purpose |
|--------|---------|
| `has_claude_code`, `has_cursor`, `has_codex`, `has_claude_desktop` | Detect a tool |
| `section`, `ok`, `note`, `fail` | Print a heading or one status line; `fail` also shows the failed command's last output lines |
| `quietly <cmd>` | Run a command with its output hidden unless it fails; on success the output is in `$quiet_output` |
| `need <tool> [brew formula]` | Stop the plugin with an install hint when a tool is missing |
| `claude_marketplace_plugin`, `codex_marketplace_plugin` | Install or update a plugin from a git-hosted marketplace |
| `claude_marketplace_plugin_remove`, `codex_marketplace_plugin_remove` | Remove that plugin and its marketplace, or report "Already removed." |
| `codex_has_marketplace <name>` | Check whether Codex has a marketplace configured |
| `skills_cli_skill <repo-url> <skill>`, `skills_cli_skill_remove <skill>` | Install or update a standalone skill with the Skills CLI for Claude Code, Cursor, and Codex, or remove it |
| `sync_checkout <url> <dir>` | Clone a repository, or reset it to the latest commit |
| `link_dir <src> <link>` | Create or replace a symlink to a directory |
| `finish` | Exit non-zero if any step failed |

</details>

Repository rules for contributors and agents are in [`AGENTS.md`](AGENTS.md). Run `make local` before opening a pull request.

---

## License

[MIT](LICENSE) © Rashad Ansari
