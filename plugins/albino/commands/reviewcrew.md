---
description: 'Run a full codebase audit: spawns all specialist reviewers in parallel and writes a consolidated report to REVIEW_REPORT.md'
allowed-tools: [Agent, Read, Write, Glob, Grep, mcp__plugin_albino_agent-memory__project_search, mcp__plugin_albino_agent-memory__user_search]
---

# Review Crew

Spawn all specialist review agents in parallel, collect their findings, and write a single consolidated report to `REVIEW_REPORT.md` in the project root.

## Step 1: Load Memory

Before spawning any reviewer, call project_search and user_search with relevant terms to load project conventions and user preferences. Use findings to inform how you brief each reviewer and to flag known gotchas or decisions that are relevant to the review.

## Step 2: Spawn All Reviewers in Parallel

Spawn all of the following agents simultaneously. Do not wait for one to finish before starting the next. Each agent prompt MUST begin with:

```
MANDATORY: Read AGENTS.md and follow its rules before doing anything.
```

Agents to spawn in parallel:

1. **security-reviewer**: security vulnerabilities across all categories
2. **code-reviewer**: correctness, style, patterns, anti-patterns
3. **architecture-reviewer**: structure, coupling, separation of concerns, SOLID
4. **performance-reviewer**: bottlenecks, complexity, memory, queries
5. **test-reviewer**: coverage, quality, missing cases, flakiness
6. **logging-reviewer**: logging gaps, monitoring, audit trail
7. **dependency-reviewer**: outdated, vulnerable, unused packages
8. **docs-reviewer**: accuracy, completeness, staleness
9. **agents-md-reviewer**: AGENTS.md rule inconsistencies
10. **accessibility-reviewer**: WCAG compliance, ARIA, keyboard navigation, screen reader compatibility
11. **api-design-reviewer**: REST/GraphQL naming, HTTP semantics, versioning, error shape, backward compatibility
12. **database-reviewer**: schema design, migration safety, indexing, constraints, query patterns
13. **i18n-reviewer**: hardcoded strings, date/number formatting, pluralization, RTL, locale handling

## Step 3: Collect All Results

Wait for all agents to complete. Collect every finding from every agent. Do not discard or summarize findings: preserve the full output of each reviewer.

## Step 4: Write Consolidated Report

Write the full consolidated report to `REVIEW_REPORT.md` in the project root. Use this exact structure:

```markdown
# Codebase Review Report

Generated: <current date and time>

## Summary

Each row reflects the count from that reviewer's own output. Cross-reviewer duplicates are not merged.

| Review Area        | Critical | High | Medium | Low |
|--------------------|----------|------|--------|-----|
| Security           | N        | N    | N      | N   |
| Code Quality       | N        | N    | N      | N   |
| Architecture       | N        | N    | N      | N   |
| Performance        | N        | N    | N      | N   |
| Tests              | N        | N    | N      | N   |
| Logging            | N        | N    | N      | N   |
| Dependencies       | N        | N    | N      | N   |
| Documentation      | N        | N    | N      | N   |
| AGENTS.md          | N        | N    | N      | N   |
| Accessibility      | N        | N    | N      | N   |
| API Design         | N        | N    | N      | N   |
| Database           | N        | N    | N      | N   |
| i18n               | N        | N    | N      | N   |
| **Total**          | **N**    | **N**| **N**  | **N** |

---

## Security Review

<full output from security-reviewer>

---

## Code Quality Review

<full output from code-reviewer>

---

## Architecture Review

<full output from architecture-reviewer>

---

## Performance Review

<full output from performance-reviewer>

---

## Test Review

<full output from test-reviewer>

---

## Logging & Monitoring Review

<full output from logging-reviewer>

---

## Dependency Review

<full output from dependency-reviewer>

---

## Documentation Review

<full output from docs-reviewer>

---

## AGENTS.md Consistency Review

<full output from agents-md-reviewer>

---

## Accessibility Review

<full output from accessibility-reviewer>

---

## API Design Review

<full output from api-design-reviewer>

---

## Database Review

<full output from database-reviewer>

---

## i18n Review

<full output from i18n-reviewer>
```

## Rules

- Do not truncate or summarize any reviewer's output: paste full findings
- Fill in the summary table with actual counts from each reviewer's output. Count each issue once per reviewer that reported it: do not merge cross-reviewer duplicates. Write `0` for severity levels where a reviewer found nothing; do not leave cells blank.
- If a reviewer finds no issues, write `No issues found.` under its section: do not omit the section
- If a reviewer fails or errors, write `Reviewer failed: <error>` under its section
- Report file must be complete and self-contained: no references to external files needed to understand findings
