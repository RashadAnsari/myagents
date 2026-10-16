#!/usr/bin/env bash
# Removes everything install.sh set up for ECC, on every tool. Safe to rerun.
# Memories, session summaries, and learned instincts are kept unless --purge
# is passed. See README.md.
#
# Usage: uninstall.sh [--purge]
set -euo pipefail

# Run from a clone, the library sits next to this folder. Piped from curl there
# is no folder, so the library is downloaded from GitHub instead.
LIB="$(cd "$(dirname "${BASH_SOURCE[0]:-.}")" && pwd)/../scripts/install-lib.sh"
if [ ! -f "$LIB" ]; then
  LIB="$(mktemp)"
  trap 'rm -f "$LIB"' EXIT
  if ! curl -fsSL "https://raw.githubusercontent.com/RashadAnsari/myagents/master/scripts/install-lib.sh" -o "$LIB"; then
    echo "✗ Could not download the myagents install library. Check your connection and try again."
    exit 1
  fi
fi
# shellcheck source=../scripts/install-lib.sh
source "$LIB"

LEARN_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/ecc-homunculus"
CURSOR_MCP="$HOME/.cursor/mcp.json"
MCP_NAME="ecc-memory-vault"
PURGE=false

case "${1:-}" in
  "") ;;
  --purge) PURGE=true ;;
  *) fail "Usage" "Unknown option $1. Use --purge to also delete ECC's data."; finish ;;
esac

section "ECC"

# Stops every running observer before its scripts go away with the plugin.
learning_remove() {
  local pid_file stopped=0
  for pid_file in "$LEARN_DIR"/projects/*/.observer.pid; do
    [ -f "$pid_file" ] || continue
    kill "$(cat "$pid_file")" 2>/dev/null && stopped=$((stopped + 1))
    rm -f "$pid_file"
  done
  if [ -f "$LEARN_DIR/config.json" ]; then
    rm -f "$LEARN_DIR/config.json"
    ok "Learning" "Turned off the background observer ($stopped running stopped)."
  else
    ok "Learning" "Already removed."
  fi
}

claude_remove() {
  if ! command -v claude &>/dev/null; then
    claude_marketplace_plugin_remove ecc ecc
    return 0
  fi
  if claude mcp get "$MCP_NAME" &>/dev/null; then
    if quietly claude mcp remove "$MCP_NAME" --scope user; then
      ok "Claude Code" "Removed the $MCP_NAME MCP server."
    else
      fail "Claude Code" "Could not remove the $MCP_NAME MCP server."
    fi
  fi
  if [ -d "$HOME/.claude/rules/ecc" ]; then
    rm -rf "$HOME/.claude/rules/ecc"
    # install.sh may have created the parent; it goes only when nothing else is in it.
    rmdir "$HOME/.claude/rules" 2>/dev/null || true
    ok "Claude Code" "Removed the rule packs in ~/.claude/rules/ecc."
  fi
  claude_marketplace_plugin_remove ecc ecc
}

# Only ECC's entry is removed; the rest of ~/.cursor/mcp.json is left alone.
cursor_remove() {
  if [ ! -f "$CURSOR_MCP" ] || ! node -e '
    const [file, name] = process.argv.slice(1);
    process.exit((JSON.parse(require("fs").readFileSync(file, "utf8")).mcpServers || {})[name] ? 0 : 1);
  ' "$CURSOR_MCP" "$MCP_NAME" 2>/dev/null; then
    ok "Cursor" "Already removed."
  elif quietly node -e '
    const fs = require("fs"), [file, name] = process.argv.slice(1);
    const data = JSON.parse(fs.readFileSync(file, "utf8"));
    delete data.mcpServers[name];
    fs.writeFileSync(file, JSON.stringify(data, null, 2) + "\n");
  ' "$CURSOR_MCP" "$MCP_NAME"; then
    ok "Cursor" "Removed the $MCP_NAME MCP server. Start a new chat to unload it."
  else
    fail "Cursor" "Could not remove the $MCP_NAME MCP server from ~/.cursor/mcp.json."
  fi
}

codex_remove() {
  if codex mcp get "$MCP_NAME" &>/dev/null; then
    if quietly codex mcp remove "$MCP_NAME"; then
      ok "Codex" "Removed the $MCP_NAME MCP server."
    else
      fail "Codex" "Could not remove the $MCP_NAME MCP server."
    fi
  fi
  codex_marketplace_plugin_remove ecc ecc
}

vault_remove() {
  if ! command -v npm &>/dev/null || ! npm ls -g ecc-universal &>/dev/null; then
    ok "Memory Vault" "Already removed."
  elif quietly npm uninstall -g ecc-universal --loglevel=error; then
    ok "Memory Vault" "Removed the ecc CLI."
  else
    fail "Memory Vault" "Could not remove the ecc-universal npm package."
  fi
}

data_remove() {
  if [ "$PURGE" = true ]; then
    rm -rf "$HOME/.ecc" "$LEARN_DIR" "$HOME/.claude/session-data" "$HOME/.cursor/ecc"
    ok "Data" "Deleted user memories, learned instincts, and session summaries."
  else
    note "Data" "Kept ~/.ecc/memory, ${LEARN_DIR/#$HOME/'~'}, and the session summaries. Rerun with --purge to delete them."
  fi
}

learning_remove
has_claude_code && claude_remove
has_cursor && cursor_remove
has_codex && codex_remove
vault_remove
data_remove

printf '\nProject vaults (.ecc/memory inside each repository) are never touched. Delete them by hand if you want.\n\n'

finish
