#!/usr/bin/env bash
set -euo pipefail

input=$(cat)
hook_event=$(printf '%s' "$input" | jq -r '.hook_event_name // ""' 2>/dev/null || echo "")

CONTEXT="SESSION MEMORY HANDOFF: If this session produced durable learnings (decisions, conventions, gotchas, architecture facts, or user preferences), call memory_remember or user_remember now. Skip ephemeral task details. Only save what will help future sessions."

# For Cursor stop, followup_message would re-trigger the agent and cause an infinite loop,
# so output nothing and rely on the session-memory.mdc rule for the handoff instruction.
if printf '%s' "$hook_event" | grep -q '^[a-z]'; then
  echo '{}'
else
  jq -n --arg event "${hook_event:-Stop}" --arg ctx "$CONTEXT" '{
    hookSpecificOutput: {
      hookEventName: $event,
      additionalContext: $ctx
    }
  }'
fi
