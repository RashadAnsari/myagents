#!/usr/bin/env bash
set -euo pipefail

REMINDER="MANDATORY: Read AGENTS.md and follow its rules before doing anything. When spawning agents, include the full AGENTS.md content verbatim in their prompt.

MANDATORY SKILLS: The following skills MUST be active and followed for every task:
- agent-protocol: Read AGENTS.md and enforce it on every agent spawn
- code-reusability: Spot and eliminate duplication before writing new code
- dev-conventions: Follow project conventions for reuse, scope, localization, UI, validation, and data alignment
- latest-versions: Always look up and use the latest stable version of any library or dependency
- research-first: Never guess: research docs, source, and specs before answering or implementing anything non-trivial
- project-memory: EXCLUSIVELY use the project-memory MCP server for ALL memory work. This is the ONLY permitted memory system. Never use built-in model memory, native memory tools, or any other memory kind for storage or retrieval. Query it to retrieve durable facts, decisions, and conventions for the current repo AND global user preferences and knowledge before non-trivial work; write back any new learnings (both project-scoped and user-scoped) when the task is done so future sessions benefit.

MEMORY ENFORCEMENT: Any agent that has access to the project-memory plugin MUST route all memory reads and writes through the project-memory MCP server. Using the model's own memory system, any native memory tool, or any alternative memory backend is strictly forbidden. This applies to every form of memory work without exception: storing facts, recalling context, updating beliefs, or retrieving preferences."

input=$(cat)
hook_event=$(printf '%s' "$input" | jq -r '.hook_event_name // ""' 2>/dev/null || echo "")

# Cursor's beforeSubmitPrompt expects JSON with a user_message field.
# Claude Code's UserPromptSubmit accepts plain text output as a system reminder.
if printf '%s' "$hook_event" | grep -q '^[a-z]'; then
  jq -n --arg msg "$REMINDER" '{"user_message": $msg}'
else
  printf '%s\n' "$REMINDER"
fi
