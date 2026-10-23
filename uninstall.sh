#!/usr/bin/env bash
# Removes every plugin myagents installed, then ~/.myagents itself. Safe to rerun.
set -euo pipefail

export MYAGENTS_DIR="$HOME/.myagents"
export MYAGENTS_MARKETPLACE="myagents"

if [ ! -f "$MYAGENTS_DIR/scripts/install-lib.sh" ] && [ ! -d "$MYAGENTS_DIR/.git" ]; then
  echo "✓ myagents is already uninstalled."
  exit 0
fi

# Older installs predate the uninstall scripts, so update to the latest version
# first. If that fails, uninstall with the files already on disk.
updated=true
git -C "$MYAGENTS_DIR" fetch --quiet origin HEAD 2>/dev/null \
  && git -C "$MYAGENTS_DIR" reset --quiet --hard FETCH_HEAD 2>/dev/null \
  || updated=false

if [ ! -f "$MYAGENTS_DIR/scripts/install-lib.sh" ]; then
  echo "✗ Could not download the uninstall scripts. Check your connection and try again."
  exit 1
fi

# shellcheck source=scripts/install-lib.sh
source "$MYAGENTS_DIR/scripts/install-lib.sh"

if [ "$updated" = false ]; then
  section "myagents"
  note "Update" "Could not check for a newer version. Uninstalling with the files already on disk."
fi

removed=()
failed=()
for dir in "$MYAGENTS_DIR"/plugins/*/; do
  name="$(basename "$dir")"
  [ -f "$dir/install.sh" ] || continue
  section "$name"
  if [ ! -f "$dir/uninstall.sh" ]; then
    fail "Uninstall" "This plugin has no uninstall script, so it was left installed."
    failed+=("$name")
  elif bash "$dir/uninstall.sh"; then
    removed+=("$name")
  else
    failed+=("$name")
  fi
done

section "Summary"
for name in ${removed[@]+"${removed[@]}"}; do
  ok "$name" "Removed."
done
for name in ${failed[@]+"${failed[@]}"}; do
  fail "$name" "Some steps failed. See the details above, fix them, and rerun."
done

# The files stay while anything failed, since a rerun needs the plugin scripts.
if [ ${#failed[@]} -gt 0 ]; then
  note "Files" "Kept ~/.myagents so you can rerun the uninstaller."
else
  rm -rf "$MYAGENTS_DIR"
  ok "Files" "Removed ~/.myagents."
fi
printf '\n'

finish
