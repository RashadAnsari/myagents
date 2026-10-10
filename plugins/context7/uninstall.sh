#!/usr/bin/env bash
# Removes Context7 with its documented `ctx7 remove` command, which deletes its
# MCP server entry, rule, and skill and leaves the rest of each file alone. Run
# by the root uninstall.sh.
set -euo pipefail
# shellcheck source=../../scripts/install-lib.sh
source "$MYAGENTS_DIR/scripts/install-lib.sh"

ctx7() { CTX7_TELEMETRY_DISABLED=1 npx -y ctx7@latest "$@" </dev/null; }

# ctx7 setup always installs the context7-mcp skill, so its folder shows
# whether there is anything to remove.
ctx7_remove() {
  local label="$1" agent="$2" skills_dir="$3" hint="$4"
  if [ ! -d "$HOME/$skills_dir/context7-mcp" ]; then
    ok "$label" "Already removed."
  elif ! command -v npx &>/dev/null; then
    fail "$label" "node is not installed, so Context7 could not be removed. Install it with: brew install node"
  elif quietly ctx7 remove --all --yes "--$agent"; then
    ok "$label" "Removed. $hint to unload it."
  else
    fail "$label" "Could not remove Context7."
  fi
}

has_claude_code && ctx7_remove "Claude Code" claude .claude/skills "Restart open sessions"
has_cursor && ctx7_remove "Cursor" cursor .cursor/skills "Start a new chat"
has_codex && ctx7_remove "Codex" codex .agents/skills "Restart Codex"

finish
