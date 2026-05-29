#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=_shared.sh
source "${BASH_SOURCE[0]%/*}/_shared.sh"

input=$(cat)
hook_event=$(printf '%s' "$input" | jq -r '.hook_event_name // ""' 2>/dev/null || echo "")

CONTEXT="SESSION MEMORY BOOTSTRAP: Before your first response, you MUST call project_search and user_search with specific terms from the current task (file names, function names, domain concepts, error messages). Do this silently without narrating it to the user. These calls are required, not optional. Do not respond to the user before making them."

if printf '%s' "$hook_event" | grep -q '^[a-z]'; then
  # Cursor: beforeSubmitPrompt cannot inject context per prompt, so include the full
  # skills reminder here at session start (only injection point Cursor supports).
  combined="${REMINDER}

${CONTEXT}"
  jq -n --arg ctx "$combined" '{additional_context: $ctx}'
else
  jq -n --arg event "${hook_event:-SessionStart}" --arg ctx "$CONTEXT" '{
    hookSpecificOutput: {
      hookEventName: $event,
      additionalContext: $ctx
    }
  }'
fi
