---
description: Create a git commit
allowed-tools: Bash(git add:*), Bash(git status:*), Bash(git commit:*)
---

MANDATORY: Read AGENTS.md and follow its rules before doing anything.

## Context

The `!` prefix on each line below runs the shell command inline and injects its output before the prompt is submitted.

- Current git status: !`git status`
- Current git diff (staged and unstaged changes): !`git diff HEAD`
- Current branch: !`git branch --show-current`
- Recent commits: !`git log --oneline -10`

## Your task

Based on the above changes, create a single git commit.

Infer the commit message format from the recent commits shown above — match the exact style, prefix convention, casing, and structure used in this project. Do not impose an external convention if the project already has one.

You have the capability to call multiple tools in a single response. Stage and create the commit using a single message. Do not use any other tools or do anything else. Do not send any other text or messages besides these tool calls.
