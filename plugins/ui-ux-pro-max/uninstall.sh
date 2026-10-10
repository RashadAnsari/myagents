#!/usr/bin/env bash
# Removes the UI UX Pro Max skills with the same tools install.sh used. Run by
# the root uninstall.sh.
set -euo pipefail
# shellcheck source=../../scripts/install-lib.sh
source "$MYAGENTS_DIR/scripts/install-lib.sh"

uipro() { npx -y ui-ux-pro-max-cli@latest "$@"; }

# uipro uninstall asks for confirmation and has no flag to skip it. Without an
# answer it removes nothing and still exits 0, so the answer is piped in.
uipro_confirmed_uninstall() { printf 'y\n' | uipro uninstall --ai "$1" --global; }

# The CLI removes only its own seven skills, so other skills in the same
# folder are left alone.
uipro_remove() {
  local label="$1" ai="$2" dir="$3" hint="$4"
  if [ ! -d "$HOME/$dir/ui-ux-pro-max" ]; then
    ok "$label" "Already removed."
  elif ! command -v npx &>/dev/null; then
    fail "$label" "node is not installed, so ui-ux-pro-max could not be removed. Install it with: brew install node"
  elif quietly uipro_confirmed_uninstall "$ai" && [ ! -d "$HOME/$dir/ui-ux-pro-max" ]; then
    ok "$label" "Removed. $hint to unload it."
  else
    fail "$label" "Could not remove ui-ux-pro-max from ~/$dir."
  fi
}

has_claude_code && claude_marketplace_plugin_remove ui-ux-pro-max-skill ui-ux-pro-max
has_cursor && uipro_remove "Cursor" cursor .cursor/skills "Start a new chat"
has_codex && uipro_remove "Codex" codex .agents/skills "Restart Codex"

finish
