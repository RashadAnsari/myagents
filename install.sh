#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/RashadAnsari/myagents"
INSTALL_DIR="$HOME/.myagents"
PLUGIN_NAME="albino"
MARKETPLACE_NAME="myagents"
PLUGIN_ID="${PLUGIN_NAME}@${MARKETPLACE_NAME}"
PLUGIN_SRC="$INSTALL_DIR/plugins/$PLUGIN_NAME"

CLAUDE_PLUGINS_DIR="$HOME/.claude/plugins"
INSTALLED_PLUGINS_JSON="$CLAUDE_PLUGINS_DIR/installed_plugins.json"
KNOWN_MARKETPLACES_JSON="$CLAUDE_PLUGINS_DIR/known_marketplaces.json"
CLAUDE_SETTINGS_JSON="$HOME/.claude/settings.json"

CURSOR_PLUGINS_DIR="$HOME/.cursor/plugins/local"
CURSOR_PLUGIN_LINK="$CURSOR_PLUGINS_DIR/$PLUGIN_NAME"

registered=false
claude_detected=false
cursor_detected=false
failed_registry=false

# Helpers

need() {
  if ! command -v "$1" &>/dev/null; then
    echo "✗ '$1' is not installed. Please install it and try again."
    exit 1
  fi
}

# Fetch repo

need git
need python3

if [ -d "$INSTALL_DIR/.git" ]; then
  echo "Updating to the latest version..."
  git -C "$INSTALL_DIR" pull --ff-only
else
  echo "Downloading myagents for the first time..."
  git clone "$REPO_URL" "$INSTALL_DIR"
fi

[ -d "$PLUGIN_SRC" ] || { echo "✗ Something went wrong: plugin files are missing after download."; exit 1; }

# Register plugin in ~/.claude/

echo "Setting up the plugin..."
mkdir -p "$CLAUDE_PLUGINS_DIR"

if python3 - \
    "$INSTALL_DIR" "$PLUGIN_SRC" "$MARKETPLACE_NAME" "$PLUGIN_ID" \
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
  registered=true
  echo "  ✓ Plugin installed successfully"
else
  echo "  ✗ Setup failed — could not save plugin settings"
  failed_registry=true
fi

# Editor detection

if command -v claude &>/dev/null; then
  claude_detected=true
  echo "  • Claude Code found! Restart any open Claude Code sessions to activate the plugin."
fi

if [ -d "$HOME/.cursor" ]; then
  cursor_detected=true
  mkdir -p "$CURSOR_PLUGINS_DIR"
  ln -sf "$PLUGIN_SRC" "$CURSOR_PLUGIN_LINK"
  echo "  • Cursor found! Reload your Cursor window to activate the plugin (Ctrl+Shift+P → 'Reload Window')."
fi

# Summary

echo ""
echo "────────────────────────────────"
echo " myagents installation summary"
echo "────────────────────────────────"
printf " Plugin saved  : %s\n" "$( [ "$registered" = true ] && echo "✓ yes" || echo "✗ failed" )"
printf " Claude Code   : %s\n" "$( [ "$claude_detected" = true ] && echo "✓ found" || echo "not found" )"
printf " Cursor        : %s\n" "$( [ "$cursor_detected" = true ] && echo "✓ found" || echo "not found" )"
echo "────────────────────────────────"

if [ "$claude_detected" = false ] && [ "$cursor_detected" = false ]; then
  echo ""
  echo "The plugin was installed, but we could not find Claude Code or Cursor on your computer."
  echo "Get Claude Code: https://claude.ai/download"
  echo "Get Cursor:      https://cursor.com/download"
fi

if [ "$failed_registry" = true ]; then
  exit 1
fi
