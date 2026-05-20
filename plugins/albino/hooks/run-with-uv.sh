#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -eq 0 ]; then
  echo "[run-uv] usage: run-uv.sh <args forwarded to uv>" >&2
  exit 64
fi

log() { printf '[run-uv] %s\n' "$*" >&2; }

# 1. Make sure the standard uv install dirs are on PATH.
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

# 2. Install uv if still missing. The official installer is a single
#    curl|sh, drops the binary in ~/.local/bin, and is idempotent +
#    non-interactive.
if ! command -v uv >/dev/null 2>&1; then
  log "uv not found; installing one-time via https://astral.sh/uv/install.sh"

  installer_cmd=""
  if command -v curl >/dev/null 2>&1; then
    installer_cmd="curl -LsSf https://astral.sh/uv/install.sh"
  elif command -v wget >/dev/null 2>&1; then
    installer_cmd="wget -qO- https://astral.sh/uv/install.sh"
  else
    log "ERROR: neither curl nor wget on PATH; cannot auto-install uv."
    log "Install uv manually, then restart the editor:"
    log "   https://docs.astral.sh/uv/getting-started/installation/"
    exit 1
  fi

  # Pipe installer to sh; redirect ALL output to stderr to keep stdout clean.
  if ! { eval "$installer_cmd" | sh; } >&2; then
    log "ERROR: uv installer failed. See output above."
    exit 1
  fi

  # Re-prime PATH (installer drops the binary into ~/.local/bin).
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi

if ! command -v uv >/dev/null 2>&1; then
  log "ERROR: uv install reported success but 'uv' is still not on PATH."
  log "Check ~/.local/bin and ~/.cargo/bin manually."
  exit 1
fi

# 3. Hand off. exec replaces this shell so signals and exit codes
#    propagate exactly as if the editor had launched uv directly.
exec uv "$@"
