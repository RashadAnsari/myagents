#!/usr/bin/env bash
# Installs or updates every plugin in myagents. Safe to rerun at any time.
set -euo pipefail

REPO_URL="${MYAGENTS_REPO_URL:-https://github.com/RashadAnsari/myagents}"
export MYAGENTS_DIR="$HOME/.myagents"
export MYAGENTS_MARKETPLACE="myagents"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "✗ myagents supports macOS only for now."
  exit 1
fi

# git and python3 come with the Xcode Command Line Tools.
if ! command -v git &>/dev/null; then
  echo "✗ git is not installed. Install it with: xcode-select --install"
  exit 1
fi

# The folder is owned by the installer, so it is reset to the latest commit
# rather than pulled: local edits (such as uv rewriting uv.lock) never block an
# update. Untracked files, including the agent-memory database, are kept. This
# also works when the folder exists but is not a clone yet.
mkdir -p "$MYAGENTS_DIR"
before="$(git -C "$MYAGENTS_DIR" rev-parse --short HEAD 2>/dev/null || true)"
if ! { git -C "$MYAGENTS_DIR" init --quiet \
  && { git -C "$MYAGENTS_DIR" remote set-url origin "$REPO_URL" 2>/dev/null \
    || git -C "$MYAGENTS_DIR" remote add origin "$REPO_URL"; } \
  && git -C "$MYAGENTS_DIR" fetch --quiet origin HEAD \
  && git -C "$MYAGENTS_DIR" reset --quiet --hard FETCH_HEAD; }; then
  echo "✗ Could not download myagents from $REPO_URL. Check your connection and try again."
  exit 1
fi
after="$(git -C "$MYAGENTS_DIR" rev-parse --short HEAD)"

# shellcheck source=scripts/install-lib.sh
source "$MYAGENTS_DIR/scripts/install-lib.sh"

section "myagents"
if [ -z "$before" ]; then
  ok "Download" "Saved to ~/.myagents (version $after)."
elif [ "$before" = "$after" ]; then
  ok "Update" "Already on the latest version ($after)."
else
  ok "Update" "Updated from $before to $after."
fi

# Installs, with Homebrew, each command in requirements.list that is not already
# on PATH. Homebrew itself is installed only when something is missing.
find_missing() {
  missing=()
  while read -r command formula _; do
    case "$command" in "" | \#*) continue ;; esac
    command -v "$command" &>/dev/null || missing+=("$formula")
  done <"$MYAGENTS_DIR/requirements.list"
}

find_missing
# Putting Homebrew on PATH can reveal tools it already installed.
[ ${#missing[@]} -gt 0 ] && { ensure_homebrew || true; find_missing; }

if [ ${#missing[@]} -eq 0 ]; then
  ok "Requirements" "All installed."
else
  formulas="$(printf '%s, ' "${missing[@]}")"
  if ! command -v brew &>/dev/null; then
    fail "Requirements" "Could not install ${formulas%, }, because Homebrew is not available."
  elif quietly brew install "${missing[@]}"; then
    ok "Requirements" "Installed ${formulas%, } with Homebrew."
  else
    fail "Requirements" "Could not install ${formulas%, }. Plugins that need them may fail below."
  fi
fi

found=()
has_claude_code && found+=("Claude Code")
has_cursor && found+=("Cursor")
has_codex && found+=("Codex")
if [ ${#found[@]} -eq 0 ]; then
  note "Apps" "No supported app found. Install Claude Code, Cursor, or Codex, then rerun."
else
  joined="$(printf '%s, ' "${found[@]}")"
  ok "Apps" "Found ${joined%, }."
fi

installed=()
failed=()
for script in "$MYAGENTS_DIR"/plugins/*/install.sh; do
  [ -f "$script" ] || continue
  name="$(basename "$(dirname "$script")")"
  section "$name"
  if bash "$script"; then
    installed+=("$name")
  else
    failed+=("$name")
  fi
done

section "Summary"
for name in ${installed[@]+"${installed[@]}"}; do
  ok "$name" "Ready."
done
for name in ${failed[@]+"${failed[@]}"}; do
  fail "$name" "Some steps failed. See the details above, fix them, and rerun."
done
printf '\nRerun this command at any time to update.\n\n'

finish
