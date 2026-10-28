# albino

The main plugin of [myagents](../../README.md): review agents, skills, hooks, and rules for Claude Code, Cursor, and Codex. The [myagents installer](../../README.md#quick-start) installs it with the rest.

## Workflow skills

Skills you run by name. They replaced the old slash commands, which all three tools are moving away from.

| Skill | What it does |
|---------|--------------|
| `/reviewcrew` | Runs every review agent in parallel and writes a consolidated `REVIEW_REPORT.md` |
| `/reportloop` | Walks through `REVIEW_REPORT.md` one issue at a time, by severity: explains it, then fixes or skips it |
| `/audit [reviewer] [path]` | Runs one reviewer of your choice, optionally on one path, and prints its findings |
| `/pr-review <url>` | Reviews a GitHub pull request: picks the reviewers that fit the changed files, loads memory, checks ripple effects, lets you choose which findings to post, and submits the review with `gh` |
| `/commit` | Stages all changes and writes a commit message in the project's existing style |
| `/commit-pr` | Squashes the branch into one commit and opens or updates its pull request, creating a branch first when you are on `main` or `master` |
| `/statusline` | Sets the Claude Code status line: folder, git branch and dirty state, model, context usage, and time |

Run one with `/<name>` in Claude Code (or `/albino:<name>` when another plugin uses the same name) and Cursor, and with `$<name>` or `/skills` in Codex. Claude Code fills in the arguments after the name; Cursor and Codex do not pass arguments to skills, so give the subject in the same message instead. `commit`, `commit-pr`, `pr-review`, `reviewcrew`, and `statusline` run only when you type them, never on the agent's own initiative.

## Review agents

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

## Knowledge skills

Two skills are always on. The session-start hook tells the agent to load each one in full before its first answer.

| Skill | What it enforces |
|-------|------------------|
| `dev-conventions` | Think before coding, the simplest change that works, no duplication, surgical edits, and checkable success criteria |
| `research-first` | Read the docs and source before answering, and use the latest stable version of every dependency |

The rest load when a task calls for them:

| Skill | Use it for |
|-------|------------|
| `frontend-design` | Distinctive, production-grade interfaces that avoid the generic AI look |
| `humanizer` | Removing the signs of AI-generated writing from text |
| `plugin-authoring` | Writing skills and agents that trigger reliably and use few tokens |
| `eu-ai-act` | EU AI Act risk tiers, obligations, deadlines, and penalties |

## MCP servers

albino ships no MCP servers. To add one, declare it in [`.mcp.json`](.mcp.json), which Claude Code, Cursor, and Codex all read:

```json
{
  "mcpServers": {
    "example": {
      "command": "bash",
      "args": [
        "-c",
        "PLUGIN=\"${CLAUDE_PLUGIN_ROOT}\"; [ -z \"$PLUGIN\" ] && PLUGIN=\"$(pwd)\"; exec \"$PLUGIN/scripts/example-server.sh\""
      ],
      "cwd": "."
    }
  }
}
```

Claude Code and Cursor set `CLAUDE_PLUGIN_ROOT` to the plugin folder. Codex does not, so the command falls back to `$(pwd)`, and `"cwd": "."` makes that the plugin folder. Then list the server and what it adds in a table here.

## Hooks

| Hook | Runs | What it does |
|------|------|--------------|
| `session-start` | Start of every session | Loads the mandatory skills and the communication rules: answer first, be precise, no filler |
| `user-prompt-submit` | Every prompt | Repeats a one-line reminder of those rules, since session-start context fades in long conversations |

## Rules

Instructions every agent follows on every task. Each rule is one `plugins/albino/rules/<name>.mdc` file.

| Rule | What it says |
|------|--------------|
| `single-commit-pr` | A pull request the agent opens has exactly one commit: it squashes the branch before opening it, then amends and force-pushes with `--force-with-lease` for every later change. It never rewrites a branch someone else pushed to |
| `working-preferences` | Drafts for other people stay short and plain. Docs, comments, commit messages, and PR descriptions describe only what the code in hand does now, with no plans, ticket keys, or timing words, and no text guesses at other services or how the output will be used. A "why X?" question gets an answer and no edits |

Cursor loads the rules from the plugin and lists them under it. Claude Code and Codex cannot, so the installer copies them into `~/.claude/rules/albino-<name>.md`, whose prefix marks them as albino's, and into a block between `<!-- albino:rules:begin -->` and `<!-- albino:rules:end -->` markers in `~/.codex/AGENTS.md`. Edit a rule and it takes effect after the next install: restart Claude Code and Codex, and reload the Cursor window. Reinstalling rewrites only those files and that block, and uninstalling removes them; your own rules and the rest of `AGENTS.md` are left alone.

## Platform support

| | Claude Code | Cursor | Codex |
|---|:---:|:---:|:---:|
| Review agents | ✓ | ✓ | ✓ |
| Skills | ✓ | ✓ | ✓ |
| Hooks | ✓ | ✓ | ✓ after `/hooks` |
| Rules | ✓ | ✓ | ✓ |

Codex cannot load agents or rules from a plugin, so the installer generates the agents into `~/.codex/agents/` and copies the rules as described above. Codex ships plugin hooks as untrusted: review them once with `/hooks` in the Codex TUI before they run.
