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

# ── Helpers ────────────────────────────────────────────────────────────────────

need() {
  if ! command -v "$1" &>/dev/null; then
    echo "✗ Required tool not found: $1"
    exit 1
  fi
}

# ── Fetch repo ─────────────────────────────────────────────────────────────────

need git
need python3   # used to safely merge JSON config files

if [ -d "$INSTALL_DIR/.git" ]; then
  echo "→ Updating $INSTALL_DIR..."
  git -C "$INSTALL_DIR" pull --ff-only
else
  echo "→ Cloning $REPO_URL → $INSTALL_DIR..."
  git clone "$REPO_URL" "$INSTALL_DIR"
fi

[ -d "$PLUGIN_SRC" ] || { echo "✗ Plugin source not found at $PLUGIN_SRC"; exit 1; }

# ── Register plugin in ~/.claude/ ──────────────────────────────────────────────
#
# Both Cursor and Claude Code read plugin registration from these JSON files.
# Writing them directly (instead of running `claude plugin install` + creating
# a Cursor symlink) means the script works on Cursor-only setups too, and
# points both editors at the live source so edits propagate on the next reload.

echo "→ Registering plugin..."
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
  echo "  ✓ Registered $PLUGIN_ID → $PLUGIN_SRC"
else
  echo "  ✗ Registration failed"
  failed_registry=true
fi

# ── Editor detection (informational only) ──────────────────────────────────────

if command -v claude &>/dev/null; then
  claude_detected=true
  echo "  • Claude Code detected — restart open sessions to pick up the plugin"
fi

if [ -d "$HOME/.cursor" ]; then
  cursor_detected=true
  mkdir -p "$CURSOR_PLUGINS_DIR"
  ln -sf "$PLUGIN_SRC" "$CURSOR_PLUGIN_LINK"
  echo "  ✓ Cursor symlink → $CURSOR_PLUGIN_LINK"
  echo "  • Cursor detected — reload Cursor window (Developer: Reload Window)"
fi

# ── Summary ────────────────────────────────────────────────────────────────────

echo ""
echo "────────────────────────────────"
echo " myagents — $PLUGIN_NAME plugin"
echo "────────────────────────────────"
printf " Registry    : %s\n" "$( [ "$registered" = true ] && echo "✓ written" || echo "✗ FAILED" )"
printf " Claude Code : %s\n" "$( [ "$claude_detected" = true ] && echo "✓ detected" || echo "– not detected" )"
printf " Cursor      : %s\n" "$( [ "$cursor_detected" = true ] && echo "✓ symlinked" || echo "– not detected" )"
echo "────────────────────────────────"

if [ "$claude_detected" = false ] && [ "$cursor_detected" = false ]; then
  echo ""
  echo "Registration written but neither Claude Code nor Cursor was detected."
  echo "Install Claude Code: https://claude.ai/download"
  echo "Install Cursor:      https://cursor.com/download"
fi

if [ "$failed_registry" = true ]; then
  exit 1
fi
