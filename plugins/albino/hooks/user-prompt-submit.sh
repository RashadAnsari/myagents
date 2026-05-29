#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=_shared.sh
source "${BASH_SOURCE[0]%/*}/_shared.sh"

input=$(cat)
hook_event=$(printf '%s' "$input" | jq -r '.hook_event_name // ""' 2>/dev/null || echo "")

if printf '%s' "$hook_event" | grep -q '^[a-z]'; then
  # Cursor: beforeSubmitPrompt cannot inject additional context (Cursor limitation).
  # The skills reminder is injected via sessionStart instead.
  exit 0
else
  printf '%s\n' "$REMINDER"
fi
