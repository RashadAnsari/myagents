---
description: 'Run a single specialist reviewer of your choice against the codebase: pick one review agent (security, performance, unused code, and so on), optionally scope it to a path, and get its findings in the terminal'
argument-hint: [reviewer-name] [path]
allowed-tools: [Agent, Read, Glob, Grep, mcp__plugin_albino_agent-memory__project_search, mcp__plugin_albino_agent-memory__user_search]
---

# Audit

Run one specialist reviewer against this codebase: $ARGUMENTS

Use this instead of `/reviewcrew` when only one review angle matters. `/reviewcrew` runs all reviewers and writes a report file: this command runs exactly one and answers in the terminal.

## Step 1: Resolve the Reviewer

The first word of `$ARGUMENTS` names the reviewer. Everything after it is an optional path to scope the review to: a directory or file. When no path is given, review the whole project.

Available reviewers:

| Name | Covers |
|------|--------|
| `security` | Injection, XSS, auth, SSRF, JWT, secrets, supply chain |
| `code` | Correctness, style, anti-patterns, performance, memory, concurrency |
| `architecture` | Structure, coupling, cohesion, SOLID, duplication, observability |
| `performance` | Bottlenecks, complexity, queries, caching, scalability |
| `test` | Coverage, assertion quality, flakiness, mocking, test data |
| `logging` | Logging gaps, audit trail, monitoring, sensitive data in logs |
| `dependency` | Vulnerable, outdated, and unused packages, supply chain risk |
| `docs` | Documentation accuracy, completeness, staleness |
| `agents-md` | Codebase compliance with `AGENTS.md` rules |
| `accessibility` | WCAG compliance, ARIA, keyboard navigation, screen readers |
| `api-design` | REST and GraphQL naming, HTTP semantics, versioning, error shape |
| `database` | Schema design, migration safety, indexing, constraints, queries |
| `i18n` | Hardcoded strings, date and number formatting, pluralization, RTL |
| `unused-code` | Unused code, tests, CI, infrastructure, containers, scripts, schema, docs, assets |

Match the name loosely: accept the bare name, the full agent name with the `-reviewer` suffix, and obvious synonyms (`a11y` for accessibility, `perf` for performance, `deps` for dependency, `dead-code` for unused code, `sec` for security).

If `$ARGUMENTS` is empty, or the first word matches no reviewer, print the table above and ask which reviewer to run. Wait for the answer. Do not guess, and do not fall back to running every reviewer.

If the request names a review angle no reviewer covers (for example Terraform blast radius or GraphQL schema compatibility), say so, then offer to spawn a purpose-built reviewer for it with the same output contract.

## Step 2: Load Memory

Call project_search and user_search with terms specific to the chosen reviewer's domain and the path being reviewed. Use the results to brief the reviewer on active conventions, past decisions, and known gotchas.

## Step 3: Spawn the Reviewer

Spawn the matching agent once. Its prompt MUST begin with:

```
MANDATORY: Read AGENTS.md and follow its rules before doing anything.
```

Then give it:
- The review scope: the resolved path, or the project root when none was given
- The memory context from Step 2, as a compact list of conventions, decisions, and gotchas to apply
- The instruction to call project_search and user_search itself with terms specific to the files it is about to read
- The instruction to use its own output format, grouped by severity

Reviewers start with fresh context and cannot see this conversation, so everything above must be in the prompt.

## Step 4: Report

Print the reviewer's findings in the terminal, in full and grouped by severity. Do not summarize, truncate, or reorder them, and do not add findings the reviewer did not report.

Then state the scope that was reviewed on one line, and offer two follow-ups: writing the findings to `REVIEW_REPORT.md` so `/reportloop` can walk through them, or fixing a specific finding now.

## Rules

- Run exactly one reviewer. Suggest `/reviewcrew` if the user wants full coverage.
- Never write `REVIEW_REPORT.md` unless the user asks for it: this command answers in the terminal.
- Never apply a fix as part of the audit. Report first, fix only when the user picks a finding.
- If the reviewer fails, report the error as-is. Do not retry silently and do not substitute your own review.
