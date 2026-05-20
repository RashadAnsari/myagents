---
description: Interactively walk through all issues in REVIEW_REPORT.md — explains each issue, asks to fix or skip, handles follow-up questions, and applies fixes one by one in severity order.
allowed-tools: [Read, Write, Edit, Glob, Grep, Bash, AskUserQuestion]
---

MANDATORY: Read AGENTS.md and follow its rules before doing anything.

# Report Loop

Read `REVIEW_REPORT.md`, walk through every issue one by one, explain it, ask the user to fix or skip, handle follow-up questions, and apply fixes.

## Step 1 — Load the Report

Read `REVIEW_REPORT.md` from the project root. If it does not exist, stop and tell the user to run `/reviewcrew` first.

Parse all issues across all sections. Collect them into an ordered list:
1. CRITICAL issues first (all sections)
2. HIGH issues second
3. MEDIUM issues third
4. LOW issues last

Within each severity, preserve the order they appear in the report.

## Step 2 — Show Progress Header

Before starting, tell the user:
- Total issue count
- Breakdown by severity (CRITICAL: N, HIGH: N, MEDIUM: N, LOW: N)
- That they can say "fix", "skip", "skip all [severity]", or ask any question about the issue

## Step 3 — Process Each Issue

For each issue, repeat this loop:

### 3a — Read the Code

Before presenting the issue to the user, read the file and line referenced in the issue. Understand the actual code in context.

### 3b — Present the Issue

Show clearly:
```
─────────────────────────────────────────────
Issue N of TOTAL  [SEVERITY]
─────────────────────────────────────────────
File:     path/to/file:line
Category: <review category>
Issue:    <description from report>

Explanation:
<2-4 sentences explaining: what the problem is, why it matters,
and what the fix would look like — written for the specific code
you just read, not the generic description from the report>
```

### 3c — Ask the User

Ask: **Fix this issue?**
Options:
- **Fix** — apply the fix now
- **Skip** — leave it, move to next issue
- **Skip remaining [severity]** — skip all remaining issues at this severity level
- **Question** — user wants to discuss before deciding

### 3d — Handle Response

- **Fix**: read the file, apply a minimal targeted fix, confirm what was changed, move to next issue
- **Skip**: note it as skipped, move to next issue
- **Skip remaining [severity]**: mark all remaining issues at that level as skipped, move to next severity
- **Question / follow-up**: answer the question thoroughly using the actual code as context, then re-ask step 3c — stay on the same issue until the user decides fix or skip

### 3e — Never Assume

Do not fix an issue without explicit user confirmation. Do not move to the next issue until the user has said fix or skip for the current one.

## Step 4 — Final Summary

After all issues are processed, write a summary:

```
─────────────────────────────────────────────
Report Loop Complete
─────────────────────────────────────────────
Fixed:   N issues
Skipped: N issues
Total:   N issues

Fixed:
- path/to/file:line — <brief description>
...

Skipped:
- path/to/file:line — <brief description>
...
```

## Rules

- Process issues in severity order: CRITICAL → HIGH → MEDIUM → LOW
- Never apply a fix without user confirmation
- Never skip an issue without user confirmation
- Stay on the current issue until user decides — do not advance unilaterally
- When fixing: make the minimal change that resolves the issue — do not refactor surrounding code
- When explaining: reference the actual code, not just the generic report description
- If a fix requires changes across multiple files, explain all files that will change before applying
- If an issue is no longer present in the code (already fixed), say so and auto-advance
