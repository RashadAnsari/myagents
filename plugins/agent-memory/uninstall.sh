#!/usr/bin/env bash
# Removes the agent-memory plugin. Run by the root uninstall.sh. The memory
# database in ~/.agent-memory belongs to the user and is kept.
set -euo pipefail
# shellcheck source=../../scripts/install-lib.sh
source "$MYAGENTS_DIR/scripts/install-lib.sh"

CHECKOUT_DIR="$MYAGENTS_DIR/plugins/agent-memory/checkout"
CURSOR_PLUGIN_DIR="$HOME/.cursor/plugins/local/agent-memory"

has_claude_code && claude_marketplace_plugin_remove agent-memory agent-memory

if has_cursor; then
  if [ -d "$CURSOR_PLUGIN_DIR" ]; then
    rm -rf "$CURSOR_PLUGIN_DIR"
    ok "Cursor" "Removed. Run 'Developer: Reload Window' to unload it."
  else
    ok "Cursor" "Already removed."
  fi
fi

has_codex && codex_marketplace_plugin_remove agent-memory agent-memory

rm -rf "$CHECKOUT_DIR"

finish
