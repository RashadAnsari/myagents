---
description: Interactively walk through all issues in REVIEW_REPORT.md — explains each issue, asks to fix or skip, handles follow-up questions, and applies fixes one by one in severity order.
allowed-tools: [Agent, Read, Write, Edit, Glob, Grep, Bash, AskUserQuestion]
---

Spawn the ultra-fixer agent to walk through every issue in REVIEW_REPORT.md interactively. Issues are processed in severity order (CRITICAL → HIGH → MEDIUM → LOW). For each issue the agent explains the problem in context, asks whether to fix or skip, answers any follow-up questions, and applies the fix before moving to the next.
