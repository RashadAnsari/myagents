#!/usr/bin/env bash
set -euo pipefail

INPUT="$(cat)"

CHECK="Before finishing: did you learn anything durable this turn (a decision made, a user preference stated, a gotcha found, a convention established, an architecture fact clarified)? If yes, store it with project_remember or user_remember now, then reply to the user with a short note for each one: what you learned, why it matters, and whether it went to project or user memory. Never save without telling the user. If nothing durable was learned, or you already saved and reported it in your reply this turn, respond with exactly \"Nothing durable learned.\" and finish; do not explain, summarize, or restate anything."

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
  # Claude Code and Codex share this Stop schema. stop_hook_active is true when
  # the agent is already continuing because this hook blocked the previous stop.
  # Let it through to avoid an infinite loop.
  active="$(jq -r '.stop_hook_active // false' <<<"$INPUT")"
  if [ "$active" = "true" ]; then
    exit 0
  fi
  jq -n --arg reason "$CHECK" '{ decision: "block", reason: $reason }'
fi
