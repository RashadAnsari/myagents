# ECC

Installs [ECC](https://github.com/affaan-m/ECC) for Claude Code, Cursor, and Codex: its plugin (agents, skills, commands, hooks), common rules, memory, and continuous learning.

## Install

```bash
# everything
curl -fsSL https://raw.githubusercontent.com/RashadAnsari/myagents/master/alt/install.sh | bash

# everything except the background observer
curl -fsSL https://raw.githubusercontent.com/RashadAnsari/myagents/master/alt/install.sh | bash -s -- --no-observer
```

Needs `git`, `node` 18+, `npm`, and `python3`. Rerun to update. Restart your tools afterwards.

`--no-observer` turns off the background observer: a process that reviews your recorded tool use every 5 minutes with a small Claude model and turns repeated patterns into instincts. It costs tokens. Without it, tool use is still recorded but not turned into instincts. Use `/learn` to pull patterns from a session by hand.

## What it sets up

| Part | Claude Code | Cursor | Codex |
|---|---|---|---|
| Plugin `ecc@ecc` | ✓ | ✓ | ✓ |
| Session hooks (save, reload, pre-compact snapshot) | ✓ | ✓ | Session start only |
| Rules | Common rules in `~/.claude/rules/ecc` | ECC's Cursor rules | |
| `ecc-memory-vault` MCP server | ✓ | ✓ | ✓ |
| Background observer | ✓ | | |

Cursor has no ECC plugin, so the script builds one plugin folder from ECC's repository that every tool uses: `~/.cursor/plugins/local/ecc` with Cursor, `~/.local/share/ecc-plugin` without. Cursor loads it in every workspace, and loads it once even when its "Include third-party Plugins, Skills, and other configs" setting also imports Claude Code's plugins. Cursor's hooks do not record tool calls, so the observer learns from Claude Code only.

Codex runs plugin hooks only after you approve them once with `/hooks`. Commands are skills there, such as `ecc:source-command-learn`.

## Using memory

ECC has three kinds of memory.

**Session memory** is automatic. The hooks save a summary when a session stops and load the latest one when the next starts. Commands: `/save-session`, `/resume-session`, `/sessions`. Summaries are in `~/.claude/session-data` (Cursor: `~/.cursor/ecc`).

**Instincts** are patterns learned from your tool use, per project, with a confidence score.

- `/instinct-status`: list them.
- `/evolve`: group related instincts into skills or commands.
- `/promote`: make a project instinct global.
- `/learn`: pull patterns from the current session on demand.

**Memory Vault** holds durable notes you or the agent save on purpose: decisions, facts, lessons, handoffs. Every tool reads the same vault.

- In a session, ask the agent to save or look something up. It uses the `memory_save`, `memory_search`, and `memory_read` tools.
- From the shell:

```bash
ecc memory init --scope project                       # once per repository
echo "We use UUIDv7 for ids." | ecc memory save --title "ID format" --stdin
ecc memory search "id format"
ecc memory search "id format" --scope user            # personal memories
```

Project memories are in `.ecc/memory/project` in the repository, git-ignored by default. User memories are in `~/.ecc/memory`. Vault entries are notes, not rules: check important ones before relying on them.

## Uninstall

```bash
# keeps memories, instincts, and session summaries
curl -fsSL https://raw.githubusercontent.com/RashadAnsari/myagents/master/alt/uninstall.sh | bash

# deletes them too
curl -fsSL https://raw.githubusercontent.com/RashadAnsari/myagents/master/alt/uninstall.sh | bash -s -- --purge
```

Removes everything the installer added, from every tool: the plugin folder and its registrations, MCP servers, rules, observer setting, and npm package. Your other settings in each tool are kept. Project vaults are never touched. Safe to rerun.
