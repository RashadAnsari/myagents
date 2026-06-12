---
name: research-first
description: Enforce thorough research before answering or implementing anything non-trivial, including always looking up the latest stable version of any library or dependency. Activate when working on unfamiliar APIs, systems, protocols, security topics, dependency versions, or any concept where guessing would be harmful.
---

# Research First: No Guessing

Do not rely on training knowledge alone for anything that matters. Research first, then answer or implement.

## When This Applies

- Unfamiliar API, SDK, or library behavior
- Security concepts, vulnerability types, cryptographic primitives
- Platform-specific behavior (OS, browser, runtime)
- Protocol specifications (HTTP, OAuth, JWT, WebSocket, etc.)
- Any version number written into a manifest, install command, Dockerfile, or CI config
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

## Dependency Versions: No Stale Dependencies

Versions from training knowledge are stale by definition. Always use the latest stable version unless the user explicitly requests otherwise.

- Never hardcode or suggest an old version number from training knowledge
- Before writing any version into a manifest or command, look up the current latest stable release
- Never use `latest` tag as a substitute: resolve the actual version number and pin it explicitly
- If the project already pins a version, check whether it is still current before accepting it as correct

This applies when adding a dependency to any manifest (`package.json`, `requirements.txt`, `pyproject.toml`, `go.mod`, `Cargo.toml`, `pom.xml`, etc.), writing an install command, recommending a tool with a version number, writing a `FROM` line in a Dockerfile, or referencing a GitHub Action by tag or SHA.

Where to look up the latest version:

1. **npm**: `https://registry.npmjs.org/<package>/latest` or `npm show <package> version`
2. **PyPI**: `https://pypi.org/pypi/<package>/json` -> `.info.version`
3. **Go**: `https://pkg.go.dev/<module>` or `go list -m -versions`
4. **Crates.io**: `https://crates.io/api/v1/crates/<name>` -> `.crate.newest_version`
5. **GitHub Actions**: check the action's releases page for latest tag or pinned SHA
6. **Docker base images**: check the official image page on Docker Hub for latest stable tag
7. **Everything else**: official GitHub releases page or package registry

Only use an older version when the user explicitly requests it and states a reason. In that case, flag the version as pinned below latest and note the security risk if applicable.

## What "Research" Means

Research means using available tools to find authoritative, current information:
- `WebSearch` and `WebFetch` for external docs, specs, CVEs, changelogs
- `Read`, `Grep`, `Glob` for current codebase behavior
- Official source over any secondary source
- Primary spec over blog post or Stack Overflow answer

A guess dressed up in confident language is still a guess. Research means finding the actual answer.
