#!/usr/bin/env bash
set -euo pipefail

INPUT="$(cat)"

CHECK="Before finishing: did you learn anything durable this turn (a decision made, a user preference stated, a gotcha found, a convention established, an architecture fact clarified)? If yes, store it with project_remember or user_remember now. If nothing durable was learned, finish your response."

if [ "${PLATFORM:-}" = "cursor" ]; then
  # Only nudge completed turns, and only if this hook has not already submitted
  # a follow-up (loop_count > 0). Cursor additionally caps follow-ups via
  # loop_limit, so this can never loop even if the guard is wrong.
  status="$(jq -r '.status // empty' <<<"$INPUT")"
  loop_count="$(jq -r '.loop_count // 0' <<<"$INPUT")"
  if [ "$status" = "completed" ] && [ "$loop_count" -eq 0 ]; then
    jq -n --arg msg "$CHECK" '{ followup_message: $msg }'
  else
    echo '{}'
  fi
else
  # stop_hook_active is true when the agent is already continuing because this
  # hook blocked the previous stop. Let it through to avoid an infinite loop.
  active="$(jq -r '.stop_hook_active // false' <<<"$INPUT")"
  if [ "$active" = "true" ]; then
    exit 0
  fi
  jq -n --arg reason "$CHECK" '{ decision: "block", reason: $reason }'
fi
