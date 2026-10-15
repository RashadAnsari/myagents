#!/usr/bin/env bash
# Installs or updates the complete ECC setup (https://github.com/affaan-m/ECC)
# for Claude Code, Cursor, and Codex. Not part of the myagents installer: run
# it on its own. Safe to rerun, every step updates in place. See README.md.
#
# Usage: install.sh [--no-observer]
set -euo pipefail

ALT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../scripts/install-lib.sh
source "$ALT_DIR/../scripts/install-lib.sh"

REPO_URL="https://github.com/affaan-m/ECC.git"
CLAUDE_MARKETPLACE_DIR="$HOME/.claude/plugins/marketplaces/ecc"
LEARN_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/ecc-homunculus"
CURSOR_MCP="$HOME/.cursor/mcp.json"
MCP_NAME="ecc-memory-vault"
OBSERVER=true

while [ $# -gt 0 ]; do
  case "$1" in
    --no-observer) OBSERVER=false; shift ;;
    *) fail "Usage" "Unknown option $1. The only option is --no-observer."; finish ;;
  esac
done

section "ECC"

for tool in git node npm python3; do need "$tool"; done
if [ "$(node -p 'process.versions.node.split(".")[0]')" -lt 18 ]; then
  fail "Requirements" "ECC needs Node.js 18 or newer. Update it with: brew upgrade node"
  finish
fi

# Writes or removes one key of a JSON object file, creating the file when needed.
# The value is JSON; an empty value removes the key.
json_set() {
  node -e '
    const fs = require("fs"), [file, path, value] = process.argv.slice(1);
    const data = fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, "utf8") || "{}") : {};
    const keys = path.split("."), last = keys.pop();
    let node = data;
    for (const k of keys) node = node[k] = node[k] || {};
    if (value) node[last] = JSON.parse(value); else delete node[last];
    fs.mkdirSync(require("path").dirname(file), { recursive: true });
    fs.writeFileSync(file, JSON.stringify(data, null, 2) + "\n");
  ' "$@"
}

# The Memory Vault runtime is shared by every tool. It is pinned to the Claude
# plugin's version when that is known, so the CLI and the hooks match.
vault_install() {
  local version="latest"
  [ -f "$CLAUDE_MARKETPLACE_DIR/VERSION" ] && version="$(cat "$CLAUDE_MARKETPLACE_DIR/VERSION")"
  NPM_CONFIG_UPDATE_NOTIFIER=false npm install -g "ecc-universal@$version" --no-audit --no-fund --loglevel=error \
    && ecc_cli memory init --scope user
}

# Runs the vault CLI through node, so it works when npm's bin folder is not on PATH.
ecc_cli() { node "$(npm root -g)/ecc-universal/scripts/ecc.js" "$@"; }

# Every tool launches the MCP server with absolute paths, since apps started
# from the Dock do not see the shell's PATH.
NODE_BIN="$(command -v node)"
vault_script() { echo "$(npm root -g)/ecc-universal/scripts/memory-mcp.mjs"; }

# Rules and the MCP server. The plugin itself is installed before the vault.
claude_install() {
  command -v claude &>/dev/null || return 0

  # Plugins cannot ship rules, so ECC's README says to copy them. Only the
  # language-neutral common pack is used. It is replaced whole, so a rerun
  # matches upstream exactly.
  mkdir -p "$HOME/.claude/rules/ecc"
  rm -rf "$HOME/.claude/rules/ecc/common"
  if cp -R "$CLAUDE_MARKETPLACE_DIR/rules/common" "$HOME/.claude/rules/ecc/common"; then
    ok "Claude Code" "Copied the common rules to ~/.claude/rules/ecc."
  else
    fail "Claude Code" "Could not copy the common rules to ~/.claude/rules/ecc."
  fi

  # Removed first so a rerun replaces the entry instead of failing on it.
  claude mcp remove "$MCP_NAME" --scope user &>/dev/null || true
  if quietly claude mcp add "$MCP_NAME" --scope user \
    -e ECC_MEMORY_HARNESS=claude -e ECC_MEMORY_ALLOW_USER_SCOPE=1 \
    -- "$NODE_BIN" "$(vault_script)"; then
    ok "Claude Code" "Added the $MCP_NAME MCP server."
  else
    fail "Claude Code" "Could not add the $MCP_NAME MCP server."
  fi
}

# Cursor loads the Claude Code plugin itself through its "Include third-party
# Plugins, Skills, and other configs" setting, so only the MCP server is added.
cursor_install() {
  local entry
  entry="$(node -e 'console.log(JSON.stringify({ command: process.argv[1], args: [process.argv[2]],
    env: { ECC_MEMORY_HARNESS: "cursor", ECC_MEMORY_ALLOW_USER_SCOPE: "1" } }))' "$NODE_BIN" "$(vault_script)")"
  if quietly json_set "$CURSOR_MCP" "mcpServers.$MCP_NAME" "$entry"; then
    ok "Cursor" "Added the $MCP_NAME MCP server. Start a new chat to load it."
  else
    fail "Cursor" "Could not add the $MCP_NAME MCP server to ~/.cursor/mcp.json."
  fi
  if ! has_claude_code; then
    note "Cursor" "ECC's skills, agents, and hooks reach Cursor through the Claude Code plugin. Install Claude Code and rerun to get them."
  fi
}

codex_install() {
  codex_marketplace_plugin "$REPO_URL" ecc ecc
  codex mcp remove "$MCP_NAME" &>/dev/null || true
  if quietly codex mcp add "$MCP_NAME" \
    --env ECC_MEMORY_HARNESS=codex --env ECC_MEMORY_ALLOW_USER_SCOPE=1 \
    -- "$NODE_BIN" "$(vault_script)"; then
    ok "Codex" "Added the $MCP_NAME MCP server."
  else
    fail "Codex" "Could not add the $MCP_NAME MCP server."
  fi
}

# The observer reads config.json from its data folder before the copy inside
# the plugin, so this setting survives plugin updates. Only the observer key is
# changed; anything else in the file is kept.
learning_install() {
  local entry
  mkdir -p "$LEARN_DIR"/{instincts/{personal,inherited},evolved/{agents,skills,commands},projects}
  [ -f "$LEARN_DIR/config.json" ] || echo '{"version": "2.1"}' >"$LEARN_DIR/config.json"
  entry="{\"enabled\": $OBSERVER, \"run_interval_minutes\": 5, \"min_observations_to_analyze\": 20}"
  if ! quietly json_set "$LEARN_DIR/config.json" observer "$entry"; then
    fail "Learning" "Could not write ${LEARN_DIR/#$HOME/'~'}/config.json."
  elif [ "$OBSERVER" = true ]; then
    ok "Learning" "Turned on the background observer. It uses a small Claude model, so it costs tokens."
  else
    ok "Learning" "Left the background observer off. Tool use is still recorded."
  fi
}

# The Claude Code plugin goes first: its download tells the vault which version to install.
has_claude_code && claude_marketplace_plugin "$REPO_URL" ecc ecc

if quietly vault_install; then
  ok "Memory Vault" "Installed the ecc CLI. User memories are kept in ~/.ecc/memory."
else
  fail "Memory Vault" "Could not install the ecc-universal npm package."
  finish
fi

has_claude_code && claude_install
has_cursor && cursor_install
has_codex && codex_install
learning_install

if ! has_claude_code && ! has_cursor && ! has_codex; then
  note "Apps" "No supported app found. Install Claude Code, Cursor, or Codex, then rerun."
fi

printf '\nRestart your tools. In each project, run "ecc memory init --scope project" once to give it a vault.\n'
printf 'Rerun this script at any time to update.\n\n'

finish
