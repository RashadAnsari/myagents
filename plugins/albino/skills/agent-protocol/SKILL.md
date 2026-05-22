---
name: agent-protocol
description: This skill MUST activate before spawning any agent or subagent. It enforces the mandatory AGENTS.md rules protocol for all agent interactions.
---

# Agent Protocol: Mandatory Rules Enforcement

## THIS IS NON-NEGOTIABLE

Before spawning any agent, you MUST do the following. These are hard requirements, not suggestions.

## Step 1: Read AGENTS.md

Read `AGENTS.md` before every agent spawn. Do not guard on whether it exists: attempt to read it and proceed accordingly.

## Step 2: Instruct every agent to read AGENTS.md

Every agent spawn prompt MUST begin with:

```
MANDATORY: Read AGENTS.md and follow its rules before doing anything.

Your task: ...
```

The agent reads and enforces AGENTS.md itself. Do not paste the content: the agent is responsible for reading it.

## Step 3: Enforce on nested spawns

If an agent spawns further subagents, the same rules apply. Include explicit instructions in the spawn prompt telling the agent it must also prepend AGENTS.md to any agents it spawns.

## Why this cannot be skipped

Agents are isolated: they do not inherit session context or hooks. The only way rules reach them is through their prompt. If you omit AGENTS.md from the spawn prompt, the agent operates without rules. That is a violation of user requirements.
