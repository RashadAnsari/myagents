#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/RashadAnsari/myagents"
INSTALL_DIR="$HOME/.myagents"
PLUGIN_NAME="albino"
PLUGIN_SRC="$INSTALL_DIR/plugins/$PLUGIN_NAME"
CURSOR_PLUGINS_DIR="$HOME/.cursor/plugins/local"

installed_claude=false
installed_cursor=false
failed_claude=false
failed_cursor=false

# ── Helpers ────────────────────────────────────────────────────────────────────

need() {
  if ! command -v "$1" &>/dev/null; then
    echo "✗ Required tool not found: $1"
    exit 1
  fi
}

# ── Fetch repo ─────────────────────────────────────────────────────────────────

need git

if [ -d "$INSTALL_DIR/.git" ]; then
  echo "→ Updating $INSTALL_DIR..."
  git -C "$INSTALL_DIR" pull --ff-only
else
  echo "→ Cloning $REPO_URL → $INSTALL_DIR..."
  git clone "$REPO_URL" "$INSTALL_DIR"
fi

# ── Claude Code ────────────────────────────────────────────────────────────────

if command -v claude &>/dev/null; then
  echo "→ Installing for Claude Code..."
  if claude plugin marketplace add "$INSTALL_DIR" && \
     claude plugin install "$PLUGIN_NAME@myagents"; then
    echo "  ✓ Claude Code: installed"
    installed_claude=true
  else
    echo "  ✗ Claude Code: installation failed"
    failed_claude=true
  fi
else
  echo "  – Claude Code: claude CLI not found, skipping"
fi

# ── Cursor ─────────────────────────────────────────────────────────────────────

if [ -d "$HOME/.cursor" ]; then
  echo "→ Installing for Cursor..."
  mkdir -p "$CURSOR_PLUGINS_DIR"
  LINK="$CURSOR_PLUGINS_DIR/$PLUGIN_NAME"

  if [ -L "$LINK" ]; then
    rm "$LINK"
  elif [ -e "$LINK" ]; then
    echo "  ✗ Cursor: $LINK exists and is not a symlink — remove it manually and rerun"
    failed_cursor=true
  fi

  if [ "$failed_cursor" = false ]; then
    ln -s "$PLUGIN_SRC" "$LINK"
    echo "  ✓ Cursor: installed ($LINK → $PLUGIN_SRC)"
    echo "  ! Reload Cursor to activate (Developer: Reload Window)"
    installed_cursor=true
  fi
else
  echo "  – Cursor: ~/.cursor not found, skipping"
fi

# ── Summary ────────────────────────────────────────────────────────────────────

echo ""
echo "────────────────────────────────"
echo " myagents — albino plugin"
echo "────────────────────────────────"
printf " Claude Code : %s\n" "$( [ "$installed_claude" = true ] && echo "✓ installed" || ( [ "$failed_claude" = true ] && echo "✗ FAILED" || echo "– skipped" ) )"
printf " Cursor      : %s\n" "$( [ "$installed_cursor" = true ] && echo "✓ installed" || ( [ "$failed_cursor" = true ] && echo "✗ FAILED" || echo "– skipped" ) )"
echo "────────────────────────────────"

if [ "$installed_claude" = false ] && [ "$installed_cursor" = false ] && [ "$failed_claude" = false ] && [ "$failed_cursor" = false ]; then
  echo ""
  echo "Nothing installed — neither Claude Code nor Cursor detected."
  echo "Install Claude Code: https://claude.ai/download"
  echo "Install Cursor:      https://cursor.com/download"
fi

if [ "$failed_claude" = true ] || [ "$failed_cursor" = true ]; then
  exit 1
fi
