---
description: Configure the Claude Code statusline to show git branch, current directory, and time. Writes the statusline script and updates ~/.claude/settings.json.
allowed-tools: [Read, Write, Edit, Bash]
---

Configure the Claude Code statusline by doing the following steps in order:

1. Find the albino plugin install directory. Check these locations in order and use the first that exists:
   - `~/.myagents/plugins/albino`
   - The directory of the current `CLAUDE_PLUGIN_ROOT` environment variable

2. Read `~/.claude/settings.json`. If the file does not exist, treat it as an empty JSON object `{}`.

3. Add or update the `statusLine` field with:
   ```json
   {
     "statusLine": {
       "type": "command",
       "command": "<absolute-path-to-configure-statusline.sh>",
       "refreshInterval": 30
     }
   }
   ```
   Preserve all other existing fields. Write the result back to `~/.claude/settings.json`.

4. Confirm to the user: statusline is configured. It shows git branch, current directory, and time. It refreshes every 30 seconds. Changes take effect on the next Claude Code interaction.
