#!/usr/bin/env bash
# Installs or updates the albino plugin. Run by the root install.sh.
set -euo pipefail
# shellcheck source=../../scripts/install-lib.sh
source "$MYAGENTS_DIR/scripts/install-lib.sh"

PLUGIN_NAME="albino"
PLUGIN_ID="${PLUGIN_NAME}@${MYAGENTS_MARKETPLACE}"
PLUGIN_SRC="$MYAGENTS_DIR/plugins/$PLUGIN_NAME"

CLAUDE_PLUGINS_DIR="$HOME/.claude/plugins"
INSTALLED_PLUGINS_JSON="$CLAUDE_PLUGINS_DIR/installed_plugins.json"
KNOWN_MARKETPLACES_JSON="$CLAUDE_PLUGINS_DIR/known_marketplaces.json"
CLAUDE_SETTINGS_JSON="$HOME/.claude/settings.json"

CLAUDE_DESKTOP_CONFIG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
CLAUDE_DESKTOP_MCP_SRC="$PLUGIN_SRC/.claude-desktop/mcp.json"

CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
CODEX_PROMPTS_DIR="$CODEX_HOME/prompts"
CODEX_AGENTS_DIR="$CODEX_HOME/agents"
CODEX_SKILLS_DIR="$CODEX_HOME/skills"

need jq # used by plugin hooks at runtime, not this script
need python3

# Earlier installers ran plain `ln -sf`, which on a rerun created this link
# inside the plugin folder instead of replacing the Cursor link.
[ -L "$PLUGIN_SRC/$PLUGIN_NAME" ] && rm -f "$PLUGIN_SRC/$PLUGIN_NAME"

# Claude Code: register the marketplace and plugin directly in ~/.claude/, so it
# works without the claude command on PATH. Each value is overwritten, never
# appended, so a rerun leaves the files unchanged.
if has_claude_code; then
  if quietly python3 - \
      "$MYAGENTS_DIR" "$PLUGIN_SRC" "$MYAGENTS_MARKETPLACE" "$PLUGIN_ID" \
      "$KNOWN_MARKETPLACES_JSON" "$INSTALLED_PLUGINS_JSON" "$CLAUDE_SETTINGS_JSON" \
      <<'PY'
import datetime, json, os, sys

(install_dir, plugin_src, mkt_name, plugin_id,
 known_path, installed_path, settings_path) = sys.argv[1:8]

def load(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}

def save(path, data):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    os.replace(tmp, path)

known = load(known_path)
now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
known[mkt_name] = {
    "source": {"source": "directory", "path": install_dir},
    "installLocation": install_dir,
    "lastUpdated": now,
}
save(known_path, known)

installed = load(installed_path)
installed.setdefault("version", 2)
plugins = installed.setdefault("plugins", {})
existing = plugins.get(plugin_id, [])
if not isinstance(existing, list):
    existing = []
kept = [e for e in existing
        if not (isinstance(e, dict) and e.get("scope") == "user")]
kept.insert(0, {"scope": "user", "installPath": plugin_src})
plugins[plugin_id] = kept
save(installed_path, installed)

settings = load(settings_path)
enabled = settings.setdefault("enabledPlugins", {})
if not isinstance(enabled, dict):
    settings["enabledPlugins"] = enabled = {}
enabled[plugin_id] = True

extras = settings.setdefault("extraKnownMarketplaces", {})
if not isinstance(extras, dict):
    settings["extraKnownMarketplaces"] = extras = {}
extras[mkt_name] = {"source": {"source": "directory", "path": install_dir}}
save(settings_path, settings)
PY
  then
    ok "Claude Code" "Installed. Restart open sessions to load it."
  else
    fail "Claude Code" "Could not update the settings in ~/.claude/. Check that you can write to that folder."
  fi
fi

if has_cursor; then
  if quietly link_dir "$PLUGIN_SRC" "$HOME/.cursor/plugins/local/$PLUGIN_NAME"; then
    ok "Cursor" "Installed. Run 'Developer: Reload Window' to load it."
  else
    fail "Cursor" "Could not link the plugin into ~/.cursor/plugins/local/."
  fi
fi

if has_codex; then
  # Codex reads the plugin (skills, MCP servers, hooks) from the marketplace in
  # .agents/plugins/. Rerunning both commands refreshes Codex's cached copy.
  #
  # Codex also converts some plugin commands into skills, but skips any that
  # take arguments, use Claude Code inline shell expansion, or are over roughly
  # 3.8 KB. Custom prompts stopped loading in codex-cli 0.117.0, so the skipped
  # ones are generated as skills. Subagents cannot load from a plugin at all,
  # so they are generated as TOML. Both generators prune their old output.
  migrated_dir=""
  if quietly codex plugin marketplace add "$MYAGENTS_DIR" && quietly codex plugin add "$PLUGIN_ID"; then
    for candidate in "$CODEX_HOME/plugins/cache/$MYAGENTS_MARKETPLACE/$PLUGIN_NAME"/*/.codex-plugin/migrated-command-skills; do
      [ -d "$candidate" ] && migrated_dir="$candidate"
    done

    # Remove the prompts earlier installers created. Codex no longer reads them.
    for link in "$CODEX_PROMPTS_DIR"/*.md; do
      [ -L "$link" ] || continue
      case "$(readlink "$link")" in "$PLUGIN_SRC"/commands/*) rm -f "$link" ;; esac
    done

    if ! quietly "$PLUGIN_SRC/scripts/gen-codex-command-skills.sh" "$CODEX_SKILLS_DIR" "$migrated_dir"; then
      fail "Codex" "Installed, but could not generate the command skills in $CODEX_SKILLS_DIR."
    elif ! quietly "$PLUGIN_SRC/scripts/gen-codex-agents.sh" "$CODEX_AGENTS_DIR"; then
      fail "Codex" "Installed, but could not generate the agents in $CODEX_AGENTS_DIR."
    else
      ok "Codex" "Installed. Restart Codex, then run /hooks once to trust its hooks."
    fi
  else
    fail "Codex" "Could not install $PLUGIN_NAME."
  fi
fi

# Claude Desktop has no plugin support, so only the MCP servers are added. Servers
# with the same name are replaced, so a rerun does not duplicate them.
if has_claude_desktop; then
  if quietly python3 - "$CLAUDE_DESKTOP_MCP_SRC" "$CLAUDE_DESKTOP_CONFIG" <<'PY'
import json, os, sys

src_path, config_path = sys.argv[1], sys.argv[2]

def load(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}

def save(path, data):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    os.replace(tmp, path)

src = load(src_path)
config = load(config_path)
src_servers = src.get("mcpServers", {})
config.setdefault("mcpServers", {}).update(src_servers)
save(config_path, config)
PY
  then
    ok "Claude Desktop" "MCP servers added. Restart Claude Desktop to load them."
  else
    fail "Claude Desktop" "Could not update $CLAUDE_DESKTOP_CONFIG."
  fi
fi

finish
