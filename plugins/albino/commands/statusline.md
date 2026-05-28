---
description: Configure the Claude Code statusline to show git branch, current directory, and time. Writes the statusline script and updates ~/.claude/settings.json.
allowed-tools: [Read, Write, Edit, Bash, AskUserQuestion]
---

Configure the Claude Code statusline by doing the following steps in order:

1. Ask the user where to install using AskUserQuestion with these options:
   - **Global**: writes to `~/.claude/settings.json`, applies to all projects
   - **Project**: writes to `.claude/settings.local.json` in the current working directory, applies only to this project (gitignored, personal)

2. Find the albino plugin install directory. Check these locations in order and use the first that exists:
   - `~/.myagents/plugins/albino`
   - The directory of the current `CLAUDE_PLUGIN_ROOT` environment variable

3. Based on the user's choice, determine the target settings file:
   - **Global**: `~/.claude/settings.json`
   - **Project**: `.claude/settings.local.json` (relative to current working directory: create `.claude/` if it does not exist)

4. Read the target settings file. If it does not exist, treat it as an empty JSON object `{}`.

5. Add or update the `statusLine` field with:
   ```json
   {
     "statusLine": {
       "type": "command",
       "command": "<absolute-path-to-configure-statusline.sh>",
       "refreshInterval": 30
     }
   }
   ```
   Preserve all other existing fields. Write the result back to the target settings file.

6. Confirm to the user: statusline is configured (global or project, as chosen). It shows git branch, current directory, and time. It refreshes every 30 seconds. Changes take effect on the next Claude Code interaction.
