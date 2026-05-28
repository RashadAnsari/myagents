---
name: latest-versions
description: Always use the latest stable version of any library or dependency. Activate when adding, updating, or recommending any package, SDK, framework, or tool version.
---

# Latest Versions: No Stale Dependencies

Always use the latest stable version. Never suggest, pin, or write an old version without explicit user instruction.

## Hard Rules

- Never hardcode or suggest an old version number from training knowledge: versions go stale
- Before writing any version into a manifest or command, look up the current latest stable release
- Use `WebSearch` or `WebFetch` to find the current latest version from the official source (npm, PyPI, pkg.go.dev, crates.io, Maven Central, GitHub releases, etc.)
- Never use `latest` tag as a substitute: resolve the actual version number and pin it explicitly
- If the project already pins a version, check whether it is still current before accepting it as correct

## When to Apply

- Adding a new dependency to any manifest (`package.json`, `requirements.txt`, `pyproject.toml`, `go.mod`, `Cargo.toml`, `pom.xml`, etc.)
- Writing an install command (`npm install`, `pip install`, `go get`, etc.)
- Recommending a library or tool with a version number
- Writing a `FROM` line in a Dockerfile
- Referencing a GitHub Action with a version tag or SHA

## How to Find the Latest Version

1. **npm**: `https://registry.npmjs.org/<package>/latest` or `npm show <package> version`
2. **PyPI**: `https://pypi.org/pypi/<package>/json` → `.info.version`
3. **Go**: `https://pkg.go.dev/<module>` or `go list -m -versions`
4. **Crates.io**: `https://crates.io/api/v1/crates/<name>` → `.crate.newest_version`
5. **GitHub Actions**: check the action's releases page for latest tag or pinned SHA
6. **Docker base images**: check the official image page on Docker Hub for latest stable tag
7. **Everything else**: official GitHub releases page or package registry

## Exceptions

Only use an older version when the user explicitly requests it and states a reason. In that case, flag the version as pinned below latest and note the security risk if applicable.
