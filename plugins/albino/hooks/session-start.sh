#!/usr/bin/env bash
set -euo pipefail

# Must stay platform-neutral: bare tool and skill names work on both Cursor
# and Claude Code. Keep in sync with rules/session-start.mdc (intentional duplication).
REMINDER="BEFORE YOUR FIRST RESPONSE (required, do it before answering, without commentary):
1. Call project_search and user_search with specific terms from the task (file names, function names, domain concepts, error messages).
2. Read AGENTS.md if it exists and apply its rules.

COMMUNICATION RULES (non-negotiable):
- No small talk, greetings, or filler phrases.
- No \"Great question!\", \"Certainly!\", \"Of course!\", \"Happy to help!\", or similar openers.
- No closing summaries that restate work already shown. The final message must still contain the answer or result.
- No hedging on anything you can verify (\"I think\", \"it seems\", \"you might want to\"). Verify, then state it plainly. State genuine uncertainty as uncertainty, once.
- No jargon unless the task requires it. Use plain words.
- Be precise. One sentence where one sentence is enough.

DURING EVERY TASK, apply these skills:
- code-reusability: Spot and eliminate duplication before writing new code.
- dev-conventions: Follow project conventions for reuse, scope, localization, UI, validation, and data alignment.
- latest-versions: Always look up and use the latest stable version of any library or dependency.
- research-first: Never guess. Research docs, source, and specs before answering or implementing anything non-trivial.
- karpathy-guidelines: Think before coding, simplicity first, surgical changes, define verifiable success criteria.
- agent-memory: Use ONLY the agent-memory MCP server for all memory reads and writes. Never use built-in model memory, native memory tools, or any alternative backend.

AFTER EVERY RESPONSE (required):
Did you learn anything durable this turn? Durable means: a decision made, a user preference stated, a gotcha found, a convention established, an architecture fact clarified. If yes, call project_remember or user_remember before finishing. Skip if nothing non-obvious was learned. Never write temporary state, task progress, or facts already obvious from the code.

WHEN SPAWNING SUBAGENTS:
Pass the BEFORE and COMMUNICATION sections to every subagent. Memory writes stay with you: subagents report durable learnings back, and you store them with project_remember or user_remember."

if [ "${PLATFORM:-}" = "cursor" ]; then
  # NOTE: Cursor sessionStart additional_context injection is currently broken.
  # The hook runs and output is accepted, but context never reaches the agent window.
  # As a workaround, the same context is delivered via rules/session-start.mdc (alwaysApply: true).
  # Keep this hook in place so it activates automatically once Cursor fixes the bug.
  # https://forum.cursor.com/t/sessionstart-hook-additional-context-is-never-injected-into-agents-initial-system-context/158452
  # https://forum.cursor.com/t/sessionstart-hook-output-is-accepted-and-merged-but-the-injected-context-does-not-reach-agent-window/157141
  jq -n --arg ctx "$REMINDER" '{ additional_context: $ctx }'
else
  jq -n --arg ctx "$REMINDER" '{
    hookSpecificOutput: {
      hookEventName: "SessionStart",
      additionalContext: $ctx
    }
  }'
fi
