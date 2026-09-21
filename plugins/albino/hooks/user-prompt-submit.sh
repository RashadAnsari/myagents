#!/usr/bin/env bash
set -euo pipefail

# Claude Code and Codex, which share this output schema. SessionStart context
# decays as the conversation grows and can be lost in compaction, so this
# re-injects a one-line reminder each turn. Cursor has no equivalent
# (beforeSubmitPrompt can only block, not inject); there the alwaysApply
# rules/session-start.mdc is re-sent every request instead.
REMINDER="Per-turn reminder: search agent memory (project_search / user_search) for context relevant to this prompt before acting, apply AGENTS.md and the mandatory skills, and store durable learnings with project_remember / user_remember before finishing. Answer first, then only what changes what the user does next: no filler openers, no closing summary, no marketing words, no padded lists, no hedging on anything you can verify. Be precise and keep it short."

jq -n --arg ctx "$REMINDER" '{
  hookSpecificOutput: {
    hookEventName: "UserPromptSubmit",
    additionalContext: $ctx
  }
}'
