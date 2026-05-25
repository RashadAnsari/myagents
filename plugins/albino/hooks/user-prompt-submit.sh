#!/usr/bin/env bash
set -euo pipefail

REMINDER="MANDATORY: Read AGENTS.md and follow its rules before doing anything. When spawning agents, include the full AGENTS.md content verbatim in their prompt.

MANDATORY SKILLS: The following skills MUST be active and followed for every task:
- agent-protocol: Read AGENTS.md and enforce it on every agent spawn
- code-reusability: Spot and eliminate duplication before writing new code
- dev-conventions: Follow project conventions for reuse, scope, localization, UI, validation, and data alignment
- latest-versions: Always look up and use the latest stable version of any library or dependency
- research-first: Never guess: research docs, source, and specs before answering or implementing anything non-trivial
- agent-memory: EXCLUSIVELY use the agent-memory MCP server for ALL memory work. This is the ONLY permitted memory system. Never use built-in model memory, native memory tools, or any other memory kind for storage or retrieval. Query it to retrieve durable facts, decisions, and conventions for the current repo AND global user preferences and knowledge before non-trivial work.

MEMORY WRITE-BACK REQUIREMENT: Before producing your final response each turn, ask yourself: did I learn anything durable this turn? Durable means: a decision made, a user preference stated, a gotcha discovered, a convention established, an architecture fact clarified. If yes, you MUST call project.remember or user.remember before finishing. This is not optional. Do not skip it. Do not defer it to later. If nothing durable was learned this turn, skip the write. Only write what is genuinely non-obvious and useful to a future agent. Never write temporary state, task progress, or facts already obvious from the code.

MEMORY ENFORCEMENT: Any agent that has access to the agent-memory plugin MUST route all memory reads and writes through the agent-memory MCP server. Using the model's own memory system, any native memory tool, or any alternative memory backend is strictly forbidden."

input=$(cat)
hook_event=$(printf '%s' "$input" | jq -r '.hook_event_name // ""' 2>/dev/null || echo "")

if printf '%s' "$hook_event" | grep -q '^[a-z]'; then
  jq -n --arg msg "$REMINDER" '{"user_message": $msg}'
else
  printf '%s\n' "$REMINDER"
fi
