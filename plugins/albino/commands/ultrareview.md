---
description: Run a full codebase audit — spawns all review agents in parallel and writes a consolidated report to REVIEW_REPORT.md
allowed-tools: [Agent, Read, Write, Glob, Grep]
---

Spawn the ultra-reviewer agent to run all specialist reviewers in parallel (security, code quality, architecture, performance, tests, logging, dependencies, documentation, AGENTS.md) and write the consolidated findings to REVIEW_REPORT.md.
