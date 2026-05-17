#!/usr/bin/env bash
set -euo pipefail

find_bun() {
  if command -v bun &>/dev/null; then
    command -v bun
  elif [ -x "$HOME/.bun/bin/bun" ]; then
    echo "$HOME/.bun/bin/bun"
  fi
}

BUN_BIN="$(find_bun || true)"

if [ -z "$BUN_BIN" ]; then
  if ! command -v curl &>/dev/null; then
    echo "run-with-bun: bun is required but neither bun nor curl was found." >&2
    exit 1
  fi
  echo "run-with-bun: bun not found, installing..." >&2
  curl -fsSL https://bun.com/install | bash >&2
  export BUN_INSTALL="${BUN_INSTALL:-$HOME/.bun}"
  export PATH="$BUN_INSTALL/bin:$PATH"
  BUN_BIN="$(find_bun || true)"
  if [ -z "$BUN_BIN" ]; then
    echo "run-with-bun: bun installation failed." >&2
    exit 1
  fi
fi

exec "$BUN_BIN" "$@"
