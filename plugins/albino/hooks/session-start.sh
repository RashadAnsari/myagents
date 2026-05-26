#!/usr/bin/env bash
set -euo pipefail

input=$(cat)
hook_event=$(printf '%s' "$input" | jq -r '.hook_event_name // ""' 2>/dev/null || echo "")

CONTEXT="SESSION MEMORY BOOTSTRAP: Before your first response, you MUST call project.brief to load project conventions and decisions, and call user.brief to load user preferences. Then call project.search and user.search with specific terms from the current task (file names, function names, domain concepts, error messages). Do this silently without narrating it to the user. These calls are required, not optional. Do not respond to the user before making them."

if printf '%s' "$hook_event" | grep -q '^[a-z]'; then
  jq -n --arg ctx "$CONTEXT" '{additional_context: $ctx}'
else
  jq -n --arg event "${hook_event:-SessionStart}" --arg ctx "$CONTEXT" '{
    hookSpecificOutput: {
      hookEventName: $event,
      additionalContext: $ctx
    }
  }'
fi
