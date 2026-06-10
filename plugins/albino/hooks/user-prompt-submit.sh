#!/usr/bin/env bash
set -euo pipefail

# Claude Code only. SessionStart context decays as the conversation grows and
# can be lost in compaction, so this re-injects a one-line reminder each turn.
# Cursor has no equivalent (beforeSubmitPrompt can only block, not inject);
# there the alwaysApply rules/session-start.mdc is re-sent every request instead.
REMINDER="Per-turn reminder: search agent memory (project_search / user_search) for context relevant to this prompt before acting, apply AGENTS.md and the mandatory skills, and store durable learnings with project_remember / user_remember before finishing."

jq -n --arg ctx "$REMINDER" '{
  hookSpecificOutput: {
    hookEventName: "UserPromptSubmit",
    additionalContext: $ctx
  }
}'
