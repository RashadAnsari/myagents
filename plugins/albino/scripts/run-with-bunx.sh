#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -eq 0 ]; then
  echo "[run-with-bunx] usage: run-with-bunx.sh <args forwarded to bunx>" >&2
  exit 64
fi

log() { printf '[run-with-bunx] %s\n' "$*" >&2; }

# 1. Make sure the standard bun install dir is on PATH.
export PATH="$HOME/.bun/bin:$PATH"

# 2. Install bun if still missing. The official installer is a single
#    curl|bash, drops the binary in ~/.bun/bin, and is idempotent +
#    non-interactive.
if ! command -v bun >/dev/null 2>&1; then
  log "bun not found; installing one-time via https://bun.sh/install"

  installer_cmd=""
  if command -v curl >/dev/null 2>&1; then
    installer_cmd="curl -fsSL https://bun.sh/install"
  elif command -v wget >/dev/null 2>&1; then
    installer_cmd="wget -qO- https://bun.sh/install"
  else
    log "ERROR: neither curl nor wget on PATH; cannot auto-install bun."
    log "Install bun manually, then restart the editor:"
    log "   https://bun.sh/docs/installation"
    exit 1
  fi

  # Pipe installer to bash; redirect ALL output to stderr to keep stdout clean.
  if ! { eval "$installer_cmd" | bash; } >&2; then
    log "ERROR: bun installer failed. See output above."
    exit 1
  fi

  # Re-prime PATH (installer drops the binary into ~/.bun/bin).
  export PATH="$HOME/.bun/bin:$PATH"
fi

if ! command -v bun >/dev/null 2>&1; then
  log "ERROR: bun install reported success but 'bun' is still not on PATH."
  log "Check ~/.bun/bin manually."
  exit 1
fi

# 3. Hand off. exec replaces this shell so signals and exit codes
#    propagate exactly as if the editor had launched bunx directly.
exec bunx "$@"
