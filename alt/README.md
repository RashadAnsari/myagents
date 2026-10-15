# ECC (standalone)

Installs [ECC](https://github.com/affaan-m/ECC) for Claude Code, Cursor, and Codex: its plugin (agents, skills, commands, hooks), common rules, memory, and continuous learning.

This folder is not part of the myagents installer. Run it yourself.

## Install

```bash
bash alt/install.sh                 # everything
bash alt/install.sh --no-observer   # everything except the background observer
```

Needs `git`, `node` 18+, `npm`, and `python3`. Rerun to update. Restart your tools afterwards.

`--no-observer` turns off the background observer: a process that reviews your recorded tool use every 5 minutes with a small Claude model and turns repeated patterns into instincts. It costs tokens. Without it, tool use is still recorded but not turned into instincts. Use `/learn` to pull patterns from a session by hand.

## What it sets up

| Part | Claude Code | Cursor | Codex |
|---|---|---|---|
| Plugin `ecc@ecc` | ✓ | ✓ via the Claude Code plugin | ✓ |
| Session hooks (save, reload, pre-compact snapshot) | ✓ | ✓ via the Claude Code plugin | Session start only |
| Common rules in `~/.claude/rules/ecc` | ✓ | | |
| `ecc-memory-vault` MCP server | ✓ | ✓ | ✓ |
| Background observer | ✓ | ✓ via the Claude Code plugin | |

Cursor has no ECC plugin. It loads the Claude Code one through its "Include third-party Plugins, Skills, and other configs" setting (on by default), so it needs Claude Code installed. Codex runs plugin hooks only after you approve them once with `/hooks`.

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
bash alt/uninstall.sh            # keeps memories, instincts, and session summaries
bash alt/uninstall.sh --purge    # deletes them too
```

Removes the plugin, MCP servers, rules, observer setting, and npm package. Your other entries in `~/.cursor/mcp.json` and the Codex config are kept. Project vaults are never touched. Safe to rerun.
