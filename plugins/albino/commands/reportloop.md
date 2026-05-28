---
description: 'Interactively walk through all issues in REVIEW_REPORT.md: explains each issue, asks to fix or skip, handles follow-up questions, and applies fixes one by one in severity order.'
allowed-tools: [Read, Write, Edit, Glob, Grep, Bash, AskUserQuestion]
---

# Report Loop

Read `REVIEW_REPORT.md`, walk through every issue one by one, explain it, ask the user to fix or skip, handle follow-up questions, apply fixes, and write the outcome of every decision back into the report.

## Step 1: Load the Report

Read `REVIEW_REPORT.md` from the project root. If it does not exist, stop and tell the user to run `/reviewcrew` first.

Parse all issues across all sections. For each issue, check whether it already carries a status marker (see Step 3d for the format). Issues that already have a status were handled in a previous session.

Collect all issues into two lists:
- **Pending**: issues with no status marker, sorted: CRITICAL -> HIGH -> MEDIUM -> LOW. Within each severity, preserve report order.
- **Already processed**: issues that already have a status marker (FIXED, SKIPPED, AUTO-ADVANCED).

## Step 2: Show Progress Header

Before starting, tell the user:
- Total issue count (pending + already processed)
- Breakdown of pending issues by severity (CRITICAL: N, HIGH: N, MEDIUM: N, LOW: N)
- Count of already-processed issues (if any), with a note that they will be skipped unless the user asks to revisit
- That they can say "fix", "skip", "skip all [severity]", or ask any question about the issue

## Step 3: Process Each Issue

For each **pending** issue, repeat this loop:

### 3a: Read the Code

Before presenting the issue to the user, read the file and line referenced in the issue. Understand the actual code in context.

### 3b: Present the Issue

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
and what the fix would look like: written for the specific code
you just read, not the generic description from the report>
```

### 3c: Ask the User

Ask: **Fix this issue?**
Options:
- **Fix**: apply the fix now
- **Skip**: leave it, move to next issue
- **Skip remaining [severity]**: skip all remaining issues at this severity level
- **Question**: user wants to discuss before deciding

### 3d: Handle Response and Write Status to Report

After the user decides, immediately update `REVIEW_REPORT.md` to record the outcome directly on the issue. Append one of the following status lines on a new line immediately after the issue text:

- Fixed: `> **Status: FIXED**: <one-line description of what was changed>`
- Skipped: `> **Status: SKIPPED**`
- Skipped as part of "skip remaining [severity]": `> **Status: SKIPPED**: bulk skip`
- Auto-advanced (issue no longer in code): `> **Status: AUTO-ADVANCED**: already resolved`

Use the `Edit` tool to make this update in-place. Do not rewrite unrelated parts of the report.

Then continue:
- **Fix**: read the file, apply a minimal targeted fix, confirm what was changed, write the FIXED status, move to next issue
- **Skip**: note it as skipped, write the SKIPPED status, move to next issue
- **Skip remaining [severity]**: write SKIPPED status to each remaining issue at that level, move to next severity
- **Question / follow-up**: answer the question thoroughly using the actual code as context, then re-ask step 3c: stay on the same issue until the user decides fix or skip

### 3e: Never Assume

Do not fix an issue without explicit user confirmation. Do not move to the next issue until the user has said fix or skip for the current one.

## Rules

- Process issues in severity order: CRITICAL -> HIGH -> MEDIUM -> LOW
- Never apply a fix without user confirmation
- Never skip an issue without user confirmation
- Stay on the current issue until user decides: do not advance unilaterally
- Write the status marker to the report immediately after the user's decision: do not batch status updates to the end
- When fixing: make the minimal change that resolves the issue: do not refactor surrounding code
- When explaining: reference the actual code, not just the generic report description
- If a fix requires changes across multiple files, explain all files that will change before applying
- If an issue is no longer present in the code (already fixed), say so, write AUTO-ADVANCED status, and advance
- Do not re-process issues that already carry a status marker unless the user explicitly asks to revisit them
