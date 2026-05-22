#!/usr/bin/env bash
echo "MANDATORY: Read AGENTS.md and follow its rules before doing anything. When spawning agents, include the full AGENTS.md content verbatim in their prompt.

MANDATORY SKILLS: The following skills MUST be active and followed for every task:
- agent-protocol: Read AGENTS.md and enforce it on every agent spawn
- code-reusability: Spot and eliminate duplication before writing new code
- dev-conventions: Follow project conventions for reuse, scope, localization, UI, validation, and data alignment
- latest-versions: Always look up and use the latest stable version of any library or dependency
- research-first: Never guess: research docs, source, and specs before answering or implementing anything non-trivial
- project-memory: Query the project-memory MCP server to retrieve durable facts, decisions, and conventions for the current repo AND global user preferences and knowledge before non-trivial work; write back any new learnings (both project-scoped and user-scoped) when the task is done so future sessions benefit"
