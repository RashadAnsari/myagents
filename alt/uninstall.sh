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
CURSOR_PLUGIN_DIR="$HOME/.cursor/plugins/local/ecc"
DATA_PLUGIN_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/ecc-plugin"
MCP_NAME="ecc-memory-vault"
PURGE=false

# ECC's hooks in Codex keep their session data in ~/.claude, so that folder
# alone does not mean Claude Code is installed. Every Claude Code keeps its
# settings in ~/.claude.json, and plugins/ holds what install.sh registered.
claude_code_present() {
  command -v claude &>/dev/null || [ -f "$HOME/.claude.json" ] || [ -d "$HOME/.claude/plugins" ]
}

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

# Drops the entries install.sh wrote in ~/.claude/ and prints whether there were any.
claude_unregister() {
  node - "$HOME/.claude" <<'JS'
const fs = require("fs"), path = require("path");
const [claudeDir] = process.argv.slice(2);
let changed = false;
const update = (file, change) => {
  file = path.join(claudeDir, file);
  let data;
  try { data = JSON.parse(fs.readFileSync(file, "utf8")); } catch { return; }
  if (!change(data)) return;
  changed = true;
  // A registry left with nothing in it goes, as Claude Code recreates it when needed.
  const empty = Object.keys(data).filter(k => k !== "version").every(k =>
    data[k] && typeof data[k] === "object" && Object.keys(data[k]).length === 0);
  if (empty && file.includes(`${path.sep}plugins${path.sep}`)) fs.rmSync(file);
  else fs.writeFileSync(file, JSON.stringify(data, null, 2) + "\n");
};
// Removes a key, and its section too when that leaves the section empty.
const drop = (data, section, key) => {
  const parent = section ? data[section] : data;
  if (!parent || typeof parent !== "object" || !(key in parent)) return false;
  delete parent[key];
  if (section && Object.keys(parent).length === 0) delete data[section];
  return true;
};
update("plugins/known_marketplaces.json", d => drop(d, null, "ecc"));
update("plugins/installed_plugins.json", d => drop(d, "plugins", "ecc@ecc"));
update("settings.json", d => [drop(d, "enabledPlugins", "ecc@ecc"), drop(d, "extraKnownMarketplaces", "ecc")].some(Boolean));
console.log(changed ? "removed" : "absent");
JS
}

claude_remove() {
  if ! quietly claude_unregister; then
    fail "Claude Code" "Could not update the settings in ~/.claude/. Check that the JSON files there are valid."
  elif [ "$quiet_output" = "removed" ]; then
    rmdir "$HOME/.claude/plugins" 2>/dev/null || true
    ok "Claude Code" "Removed the ECC plugin. Restart open sessions to unload it."
  else
    ok "Claude Code" "Already removed."
  fi
  if [ -d "$HOME/.claude/rules/ecc" ]; then
    rm -rf "$HOME/.claude/rules/ecc"
    rmdir "$HOME/.claude/rules" 2>/dev/null || true
    ok "Claude Code" "Removed the rule packs in ~/.claude/rules/ecc."
  fi
  if command -v claude &>/dev/null && claude mcp get "$MCP_NAME" &>/dev/null; then
    if quietly claude mcp remove "$MCP_NAME" --scope user; then
      ok "Claude Code" "Removed the $MCP_NAME MCP server."
    else
      fail "Claude Code" "Could not remove the $MCP_NAME MCP server."
    fi
  fi
}

cursor_remove() {
  if [ -d "$CURSOR_PLUGIN_DIR" ]; then
    rm -rf "$CURSOR_PLUGIN_DIR"
    # install.sh may have created the parents; each goes only when nothing else is in it.
    rmdir "$HOME/.cursor/plugins/local" "$HOME/.cursor/plugins" 2>/dev/null || true
    ok "Cursor" "Removed the ECC plugin. Run 'Developer: Reload Window' to unload it."
  else
    ok "Cursor" "Already removed."
  fi
}

# Codex is checked through its config file, not `codex plugin marketplace
# list`, which fails once the plugin folder its marketplace points at is gone.
# The trust Codex recorded for ECC's hooks goes too, along with the empty
# folder `codex plugin remove` leaves in its cache.
codex_remove() {
  local config="${CODEX_HOME:-$HOME/.codex}/config.toml" removed=false
  if codex mcp get "$MCP_NAME" &>/dev/null; then
    if quietly codex mcp remove "$MCP_NAME"; then
      ok "Codex" "Removed the $MCP_NAME MCP server."
    else
      fail "Codex" "Could not remove the $MCP_NAME MCP server."
    fi
  fi
  if grep -qxF '[plugins."ecc@ecc"]' "$config" 2>/dev/null; then
    quietly codex plugin remove ecc@ecc || { fail "Codex" "Could not remove the ECC plugin."; return 0; }
    removed=true
  fi
  if grep -qxF '[marketplaces.ecc]' "$config" 2>/dev/null; then
    quietly codex plugin marketplace remove ecc || { fail "Codex" "Could not remove the ecc marketplace."; return 0; }
    removed=true
  fi
  if grep -qF '[hooks.state."ecc@ecc:' "$config" 2>/dev/null; then
    # Drops each [hooks.state."ecc@ecc:..."] table, up to the next table header,
    # with the blank lines that separated it from the table before.
    awk '
      /^\[/ { skip = index($0, "[hooks.state.\"ecc@ecc:") == 1; if (skip) blank = "" }
      /^[[:space:]]*$/ { blank = blank $0 "\n"; next }
      skip { blank = ""; next }
      { printf "%s", blank; blank = ""; print }
    ' "$config" >"$config.tmp" \
      && mv "$config.tmp" "$config" || { fail "Codex" "Could not update $config."; return 0; }
    removed=true
  fi
  rmdir "${CODEX_HOME:-$HOME/.codex}/plugins/cache/ecc" "${CODEX_HOME:-$HOME/.codex}/plugins/cache" \
    "${CODEX_HOME:-$HOME/.codex}/plugins" 2>/dev/null || true
  if [ "$removed" = true ]; then
    ok "Codex" "Removed the ECC plugin. Restart Codex to unload it."
  else
    ok "Codex" "Already removed."
  fi
}

# The folder every tool installed from. With Cursor it is Cursor's plugin and
# cursor_remove reports it; otherwise it sits in the data folder.
plugin_remove() {
  if [ -d "$DATA_PLUGIN_DIR" ]; then
    rm -rf "$DATA_PLUGIN_DIR"
    ok "Plugin" "Deleted the ECC plugin folder ${DATA_PLUGIN_DIR/#$HOME/'~'}."
  fi
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

# Without --purge only data is kept: the empty folders install.sh and the vault
# set up go, so nothing is left when ECC never stored anything.
data_remove() {
  # ECC's hooks keep their data in ~/.claude for Claude Code and Codex, and in
  # ~/.cursor/ecc for Cursor.
  local dirs=("$HOME/.ecc" "$LEARN_DIR" "$HOME/.claude/session-data" "$HOME/.claude/metrics"
    "$HOME/.claude/skills/learned" "$HOME/.claude/ecc" "$HOME/.claude/plugins/data/ecc-ecc"
    "$HOME/.cursor/ecc") dir kept=false
  if [ "$PURGE" = true ]; then
    # Also the state of the Chrome DevTools MCP server ECC's plugin starts.
    rm -rf "${dirs[@]}" "${XDG_DATA_HOME:-$HOME/.local/share}/chrome-devtools-mcp"
    ok "Data" "Deleted user memories, learned instincts, and session summaries."
  else
    for dir in "${dirs[@]}"; do
      [ -d "$dir" ] || continue
      find "$dir" -depth -type d -empty -delete 2>/dev/null || true
      [ -d "$dir" ] && kept=true
    done
    if [ "$kept" = true ]; then
      note "Data" "Kept your memories, learned instincts, and session summaries. Rerun with --purge to delete them."
    fi
  fi
  # The data folders' parents, when install.sh created them and nothing else uses them.
  rmdir "$HOME/.claude/skills" 2>/dev/null || true
  rmdir "$HOME/.claude/plugins/data" "$HOME/.claude/plugins" 2>/dev/null || true
  rmdir "$HOME/.local/share" "$HOME/.local" 2>/dev/null || true
}

learning_remove
claude_code_present && claude_remove
has_cursor && cursor_remove
has_codex && codex_remove
plugin_remove
vault_remove
data_remove

printf '\nProject vaults (.ecc/memory inside each repository) are never touched. Delete them by hand if you want.\n\n'

finish
