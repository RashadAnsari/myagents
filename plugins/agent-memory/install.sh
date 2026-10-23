#!/usr/bin/env bash
# Installs or updates the agent-memory plugin
# (https://github.com/RashadAnsari/agent-memory). Run by the root install.sh.
set -euo pipefail
# shellcheck source=../../scripts/install-lib.sh
source "$MYAGENTS_DIR/scripts/install-lib.sh"

# The HTTPS URL keeps Claude Code from cloning over SSH, which needs GitHub keys.
REPO_URL="https://github.com/RashadAnsari/agent-memory.git"
CHECKOUT_DIR="$MYAGENTS_DIR/plugins/agent-memory/checkout"
CURSOR_PLUGIN_DIR="$HOME/.cursor/plugins/local/agent-memory"

has_claude_code && claude_marketplace_plugin "$REPO_URL" agent-memory agent-memory

# The README installs the Cursor plugin by copying its folder into Cursor's
# local plugins folder. Cursor skips symlinks that point outside that folder,
# so it is a copy, refreshed from a checkout on every run.
if has_cursor; then
  if quietly sync_checkout "$REPO_URL" "$CHECKOUT_DIR" \
    && rm -rf "$CURSOR_PLUGIN_DIR" \
    && mkdir -p "$(dirname "$CURSOR_PLUGIN_DIR")" \
    && cp -R "$CHECKOUT_DIR/plugins/agent-memory" "$CURSOR_PLUGIN_DIR"; then
    ok "Cursor" "Installed. Run 'Developer: Reload Window' to load it."
  else
    fail "Cursor" "Could not copy agent-memory into ~/.cursor/plugins/local/."
  fi
fi

has_codex && codex_marketplace_plugin "$REPO_URL" agent-memory agent-memory

finish
