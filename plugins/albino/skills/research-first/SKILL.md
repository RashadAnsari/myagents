---
name: research-first
description: Enforce thorough research before answering or implementing anything non-trivial. Activate when working on unfamiliar APIs, systems, protocols, security topics, or any concept where guessing would be harmful.
---

# Research First: No Guessing

Do not rely on training knowledge alone for anything that matters. Research first, then answer or implement.

## When This Applies

- Unfamiliar API, SDK, or library behavior
- Security concepts, vulnerability types, cryptographic primitives
- Platform-specific behavior (OS, browser, runtime)
- Protocol specifications (HTTP, OAuth, JWT, WebSocket, etc.)
- Any topic where being wrong causes a bug, vulnerability, or data loss
- Any topic where the correct answer may have changed since training cutoff

## Research Order

1. **Read the code**: grep, glob, and read relevant files in the current codebase before assuming anything about how it works
2. **Read official docs**: fetch the official documentation or spec for the concept, not a tutorial or blog post
3. **Read the source**: if behavior is ambiguous, read the library or runtime source
4. **Search broadly**: if one source is insufficient, search multiple angles: official docs, spec, changelog, known issues, CVEs
5. **Only then answer or implement**

## Hard Rules

- Never guess an API signature, parameter name, or behavior: read the docs or source
- Never guess how a security mechanism works: look it up
- Never assume a behavior is the same across versions: check the version in use
- Never implement based on vague recollection: verify before writing code
- If research is inconclusive, say so explicitly: do not fill the gap with a guess presented as fact
- If something cannot be verified with available tools, say it cannot be verified: do not fabricate confidence

## What "Research" Means

Research means using available tools to find authoritative, current information:
- `WebSearch` and `WebFetch` for external docs, specs, CVEs, changelogs
- `Read`, `Grep`, `Glob` for current codebase behavior
- Official source over any secondary source
- Primary spec over blog post or Stack Overflow answer

A guess dressed up in confident language is still a guess. Research means finding the actual answer.
