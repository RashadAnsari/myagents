#!/usr/bin/env bash
# Installs or updates the complete ECC setup (https://github.com/affaan-m/ECC)
# for Claude Code, Cursor, and Codex. Safe to rerun, every step updates in
# place. See README.md.
#
# Usage: install.sh [--no-observer]
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

REPO_URL="https://github.com/affaan-m/ECC.git"
LEARN_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/ecc-homunculus"
MCP_NAME="ecc-memory-vault"
OBSERVER=true

# Claude Code, Cursor, and Codex all install ECC from this one folder, built
# once per run. Cursor imports Claude Code's plugins too, and it drops a plugin
# it has already loaded from the same folder, so Claude Code is pointed at this
# folder itself and ECC loads once in Cursor whether that import is on or off.
# Cursor only loads real folders in its plugins/local, so the folder lives
# there when Cursor is installed. Codex copies it into its own cache.
CURSOR_PLUGIN_DIR="$HOME/.cursor/plugins/local/ecc"
DATA_PLUGIN_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/ecc-plugin"
if has_cursor; then
  PLUGIN_DIR="$CURSOR_PLUGIN_DIR" OTHER_PLUGIN_DIR="$DATA_PLUGIN_DIR"
else
  PLUGIN_DIR="$DATA_PLUGIN_DIR" OTHER_PLUGIN_DIR="$CURSOR_PLUGIN_DIR"
fi

# ECC's hooks in Codex keep their session data in ~/.claude, so that folder
# alone does not mean Claude Code is installed. Every Claude Code (the CLI,
# the VS Code extension, the desktop app) keeps its settings in ~/.claude.json.
claude_code_installed() { command -v claude &>/dev/null || [ -f "$HOME/.claude.json" ]; }

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

# Writes one key of a JSON object file, creating the file when needed. The value is JSON.
json_set() {
  node -e '
    const fs = require("fs"), [file, path, value] = process.argv.slice(1);
    const data = fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, "utf8") || "{}") : {};
    const keys = path.split("."), last = keys.pop();
    let node = data;
    for (const k of keys) node = node[k] = node[k] || {};
    node[last] = JSON.parse(value);
    fs.mkdirSync(require("path").dirname(file), { recursive: true });
    fs.writeFileSync(file, JSON.stringify(data, null, 2) + "\n");
  ' "$@"
}

# Every tool launches node scripts by absolute path, since apps started from
# the Dock do not see the shell's PATH.
NODE_BIN="$(command -v node)"
vault_script() { echo "$(npm root -g)/ecc-universal/scripts/memory-mcp.mjs"; }

# Runs the vault CLI through node, so it works when npm's bin folder is not on PATH.
ecc_cli() { node "$(npm root -g)/ecc-universal/scripts/ecc.js" "$@"; }

# Builds the plugin folder in <work>/ecc: ECC's repository, which is the Claude
# Code plugin as published, plus a Cursor manifest that points Cursor at ECC's
# own Cursor adapter (the .cursor/ files its project installer copies).
build_plugin() {
  local work="$1" dir="$1/ecc"
  git clone --quiet --depth 1 "$REPO_URL" "$dir" && rm -rf "$dir/.git" || return 1
  # The hook scripts need ECC's npm dependencies. They come from its lock file,
  # without dev tools or install scripts.
  (cd "$dir" && NPM_CONFIG_UPDATE_NOTIFIER=false npm ci --omit=dev --ignore-scripts \
    --no-audit --no-fund --loglevel=error) || return 1

  node - "$dir" "$PLUGIN_DIR" "$NODE_BIN" "$MCP_NAME" "$(vault_script)" <<'JS'
const fs = require("fs"), path = require("path");
const [dir, finalDir, nodeBin, mcpName, vaultScript] = process.argv.slice(2);
const read = file => JSON.parse(fs.readFileSync(path.join(dir, file), "utf8"));
const write = (file, data) => {
  fs.mkdirSync(path.dirname(path.join(dir, file)), { recursive: true });
  fs.writeFileSync(path.join(dir, file), typeof data === "string" ? data : JSON.stringify(data, null, 2) + "\n");
};

// Cursor rules, as .mdc files like ECC's project installer writes them.
fs.mkdirSync(path.join(dir, "cursor/rules"), { recursive: true });
for (const file of fs.readdirSync(path.join(dir, ".cursor/rules")).filter(f => f.endsWith(".md")))
  fs.copyFileSync(path.join(dir, ".cursor/rules", file), path.join(dir, "cursor/rules", file.slice(0, -3) + ".mdc"));

// The adapter hooks run "node .cursor/hooks/<event>.js" from a project root.
// Here they run by absolute path, from any project.
const hooks = read(".cursor/hooks.json");
for (const entries of Object.values(hooks.hooks))
  for (const entry of entries)
    entry.command = entry.command.replace(/^node \.cursor\/hooks\/(\S+)/, (_, file) =>
      `${JSON.stringify(nodeBin)} ${JSON.stringify(path.join(finalDir, ".cursor/hooks", file))}`);
write("cursor/hooks.json", hooks);

// ECC's MCP servers plus the Memory Vault. Claude Code's manifest declares no
// MCP servers, so this file is Cursor's alone.
const mcp = read(".mcp.json");
mcp.mcpServers[mcpName] = { command: nodeBin, args: [vaultScript],
  env: { ECC_MEMORY_HARNESS: "cursor", ECC_MEMORY_ALLOW_USER_SCOPE: "1" } };
write("cursor/mcp.json", mcp);

// Cursor reads this manifest before .claude-plugin/plugin.json, also when it
// imports the plugin from Claude Code. Its Cursor-specific skills come first,
// so they win over the shared skills of the same name.
const claude = read(".claude-plugin/plugin.json");
write(".cursor-plugin/plugin.json", {
  name: claude.name, version: claude.version,
  description: "ECC agents, skills, commands, rules, hooks, and Memory Vault for Cursor.",
  author: claude.author, homepage: claude.homepage, repository: claude.repository, license: claude.license,
  skills: ["./.cursor/skills/", "./skills/"], agents: "./agents/", commands: "./commands/",
  rules: "./cursor/rules/", hooks: "./cursor/hooks.json", mcpServers: "./cursor/mcp.json",
});

// Some commands and skills find ECC's scripts through CLAUDE_PLUGIN_ROOT,
// which Cursor does not set in the shell, and fall back to ~/.claude. They
// fall back to this folder instead. Cursor fills in ${CLAUDE_PLUGIN_ROOT} on
// its own, so that form is left as it is.
const markdown = d => fs.readdirSync(path.join(dir, d), { recursive: true })
  .filter(f => f.endsWith(".md")).map(f => path.join(dir, d, f));
for (const file of [...markdown("commands"), ...markdown("agents"), ...markdown("skills"), ...markdown(".cursor/skills")]) {
  const text = fs.readFileSync(file, "utf8");
  const fixed = text
    .replaceAll("var e=process.env.CLAUDE_PLUGIN_ROOT;", `var e=process.env.CLAUDE_PLUGIN_ROOT||'${finalDir}';`)
    .replaceAll("require(process.env.CLAUDE_PLUGIN_ROOT + ", `require((process.env.CLAUDE_PLUGIN_ROOT||"${finalDir}") + `)
    .replaceAll("${CLAUDE_PLUGIN_ROOT:-$HOME/.claude}", `\${CLAUDE_PLUGIN_ROOT:-${finalDir}}`)
    .replaceAll('"$CLAUDE_PLUGIN_ROOT/', `"\${CLAUDE_PLUGIN_ROOT:-${finalDir}}/`);
  if (fixed !== text) fs.writeFileSync(file, fixed);
}
JS
}

# Replaces the plugin folder whole, so a rerun matches upstream exactly.
plugin_install() {
  local work
  work="$(mktemp -d)"
  if quietly build_plugin "$work" \
    && rm -rf "$PLUGIN_DIR" "$OTHER_PLUGIN_DIR" && mkdir -p "$(dirname "$PLUGIN_DIR")" \
    && mv "$work/ecc" "$PLUGIN_DIR"; then
    rm -rf "$work"
    return 0
  fi
  rm -rf "$work"
  fail "Plugin" "Could not build the ECC plugin in ${PLUGIN_DIR/#$HOME/'~'}."
  return 1
}

# The Memory Vault runtime is shared by every tool. It is pinned to the
# plugin's version, so the CLI and the hooks match.
vault_install() {
  NPM_CONFIG_UPDATE_NOTIFIER=false npm install -g "ecc-universal@$(cat "$PLUGIN_DIR/VERSION")" \
    --no-audit --no-fund --loglevel=error \
    && ecc_cli memory init --scope user
}

# Registers the plugin folder with Claude Code directly in ~/.claude/, the way
# Claude Code records a plugin from a folder marketplace. `claude plugin
# install` would copy it into Claude Code's cache, and Cursor would then see
# two folders and load ECC twice.
claude_register() {
  node - "$HOME/.claude" "$PLUGIN_DIR" "$(cat "$PLUGIN_DIR/VERSION")" <<'JS'
const fs = require("fs"), path = require("path");
const [claudeDir, pluginDir, version] = process.argv.slice(2);
const update = (file, change) => {
  file = path.join(claudeDir, file);
  let data = {};
  try { data = JSON.parse(fs.readFileSync(file, "utf8")); } catch {}
  change(data);
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, JSON.stringify(data, null, 2) + "\n");
};
const source = { source: "directory", path: pluginDir };
const now = new Date().toISOString();
update("plugins/known_marketplaces.json", d => {
  d.ecc = { source, installLocation: pluginDir, lastUpdated: now };
});
update("plugins/installed_plugins.json", d => {
  d.version ??= 2;
  d.plugins ??= {};
  const others = (d.plugins["ecc@ecc"] || []).filter(e => e.scope !== "user");
  d.plugins["ecc@ecc"] = [{ scope: "user", installPath: pluginDir, version, installedAt: now, lastUpdated: now }, ...others];
});
update("settings.json", d => {
  (d.enabledPlugins ??= {})["ecc@ecc"] = true;
  (d.extraKnownMarketplaces ??= {}).ecc = { source };
});
JS
}

claude_install() {
  if quietly claude_register; then
    ok "Claude Code" "Installed the ECC plugin. Restart open sessions to load it."
  else
    fail "Claude Code" "Could not register the ECC plugin in ~/.claude/."
  fi

  # Plugins cannot ship rules, so ECC's README says to copy them. Only the
  # language-neutral common pack is used. It is replaced whole, so a rerun
  # matches upstream exactly.
  mkdir -p "$HOME/.claude/rules/ecc"
  rm -rf "$HOME/.claude/rules/ecc/common"
  if cp -R "$PLUGIN_DIR/rules/common" "$HOME/.claude/rules/ecc/common"; then
    ok "Claude Code" "Copied the common rules to ~/.claude/rules/ecc."
  else
    fail "Claude Code" "Could not copy the common rules to ~/.claude/rules/ecc."
  fi

  if ! command -v claude &>/dev/null; then
    note "Claude Code" "The claude command is not on your PATH, so the $MCP_NAME MCP server was skipped. Add claude to PATH and rerun."
    return 0
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

cursor_install() {
  ok "Cursor" "Installed the ECC plugin for every workspace. Run 'Developer: Reload Window' to load it."
}

# Codex reads the plugin from a marketplace in the plugin folder, which ECC's
# repository ships in .agents/plugins/. `codex plugin add` refreshes Codex's
# copy on every run. A marketplace of the same name pointing elsewhere is
# removed first, since Codex refuses to replace it. Its source is read from
# Codex's config, because `codex plugin marketplace list` fails once the
# folder it points at is gone, as it is after the folder moves.
codex_install() {
  local root
  root="$(awk '/^\[/ { in_ecc = ($0 == "[marketplaces.ecc]") }
    in_ecc && /^source *=/ { sub(/^source *= *"/, ""); sub(/"$/, ""); print }' \
    "${CODEX_HOME:-$HOME/.codex}/config.toml" 2>/dev/null || true)"
  if [ -n "$root" ] && [ "$root" != "$PLUGIN_DIR" ]; then
    codex plugin remove ecc@ecc &>/dev/null || true
    quietly codex plugin marketplace remove ecc || { fail "Codex" "Could not replace the ecc marketplace."; return 0; }
  fi
  if quietly codex plugin marketplace add "$PLUGIN_DIR" && quietly codex plugin add ecc@ecc; then
    ok "Codex" "Installed the ECC plugin. Restart Codex, then run /hooks once to trust its hooks."
  else
    fail "Codex" "Could not install the ECC plugin."
  fi

  # Removed first so a rerun replaces the entry instead of failing on it.
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

if ! claude_code_installed && ! has_cursor && ! has_codex; then
  note "Apps" "No supported app found. Install Claude Code, Cursor, or Codex, then rerun."
  finish
fi

# The plugin goes first: every tool installs from it, and the vault is pinned to its version.
plugin_install || finish

if quietly vault_install; then
  ok "Memory Vault" "Installed the ecc CLI. User memories are kept in ~/.ecc/memory."
else
  fail "Memory Vault" "Could not install the ecc-universal npm package."
  finish
fi

claude_code_installed && claude_install
has_cursor && cursor_install
has_codex && codex_install
learning_install

printf '\nRestart your tools. In each project, run "ecc memory init --scope project" once to give it a vault.\n'
printf 'Rerun this script at any time to update.\n\n'

finish
