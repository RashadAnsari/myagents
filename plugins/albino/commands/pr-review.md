---
description: 'Review a GitHub pull request: analyzes changed files to select relevant reviewers, loads project and user memory, runs reviewers in parallel, lets the user pick which findings to post, then submits the review on behalf of the user via gh CLI'
allowed-tools: [Agent, Bash, Read, Write, Glob, Grep, AskUserQuestion, mcp__plugin_albino_agent-memory__project_brief, mcp__plugin_albino_agent-memory__user_brief]
---

MANDATORY: Read AGENTS.md and follow its rules before doing anything.

MANDATORY: Read the humanizer skill at `plugins/albino/skills/humanizer/SKILL.md` now and keep all its rules active for the entire session. Every piece of text you write or post, including comment bodies, the review body, and any output to the user, must pass the humanizer check before it leaves your context.

# PR Review

Review the GitHub pull request: $ARGUMENTS

## Step 1: Validate Input

If `$ARGUMENTS` is empty or missing, stop immediately and tell the user:
```
Usage: /pr-review <github-pr-url>
Example: /pr-review https://github.com/owner/repo/pull/123
```

Parse the PR URL to extract `owner`, `repo`, and `number`:
- URL format: `https://github.com/{owner}/{repo}/pull/{number}`

## Step 2: Fetch PR Data

Run all three in parallel:

```bash
gh pr view "$ARGUMENTS" --json number,title,body,author,baseRefName,headRefName,headRefOid,state,additions,deletions,changedFiles
```

```bash
gh pr view "$ARGUMENTS" --json files --jq '[.files[].path]'
```

```bash
gh pr diff "$ARGUMENTS"
```

If any command fails, stop and report the error. If not authenticated, suggest `gh auth login`.

Store:
- `PR_META`: parsed JSON from the first command
- `CHANGED_FILES`: list of changed file paths from the second command
- `PR_DIFF`: full diff text from the third command
- `HEAD_SHA`: value of `headRefOid` from `PR_META`

## Step 3: Load Context

Run both in parallel:

1. Call `mcp__plugin_albino_agent-memory__project_brief` to load conventions, decisions, and pitfalls for this repo.
2. Call `mcp__plugin_albino_agent-memory__user_brief` to load user preferences.

Combine into `PROJECT_CONTEXT`: a compact summary of active conventions, known decisions, and pitfalls that reviewers must apply.

## Step 4: Select Relevant Reviewers

Analyze `CHANGED_FILES` and apply the rules below to build the list of reviewers to spawn. Log which reviewers were selected and why before spawning.

**Always include:**
- `security-reviewer`
- `code-reviewer`
- `architecture-reviewer`
- `performance-reviewer`
- `test-reviewer`
- `logging-reviewer`

**Include `dependency-reviewer`** if any changed file matches: `package.json`, `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `bun.lockb`, `pyproject.toml`, `requirements*.txt`, `setup.py`, `setup.cfg`, `Pipfile`, `go.mod`, `go.sum`, `Cargo.toml`, `Cargo.lock`, `Gemfile`, `Gemfile.lock`, `pom.xml`, `build.gradle`, `build.gradle.kts`, or `*.podspec`.

**Include `docs-reviewer`** if any changed file has extension `.md`, `.mdx`, `.rst`, or `.txt`, or if any path contains `docs/`.

**Include `accessibility-reviewer`** if any changed file has extension `.html`, `.jsx`, `.tsx`, `.vue`, `.svelte`, or `.astro`, or if any path contains `components/`, `ui/`, `pages/`, `views/`, `frontend/`, `client/`, or `web/`.

**Include `i18n-reviewer`** if any changed file has extension `.jsx`, `.tsx`, `.vue`, `.svelte`, or `.astro`, or if any path contains `i18n/`, `locales/`, or `translations/`.

**Include `api-design-reviewer`** if any changed path contains `routes/`, `router/`, `api/`, `handlers/`, `controllers/`, or `endpoints/`, or if any changed file is named `openapi.json`, `openapi.yaml`, `swagger.json`, or `swagger.yaml`, or has extension `.openapi.*` or `.swagger.*`.

**Include `database-reviewer`** if any changed path contains `migrations/`, `migration/`, `db/`, `database/`, or `prisma/`, or if any changed file has extension `.sql`, or is named `schema.prisma`, or matches `*.migration.ts`, `*.migration.js`, or `*.migration.py`.

**Include `agents-md-reviewer`** if `AGENTS.md` is in the changed files, or if any changed path contains `.claude/`, `rules/`, `hooks/`, `commands/`, or `agents/`.

**Spawn additional custom reviewers** if the PR touches areas not covered by any of the above. Look at the diff and ask: is there a meaningful review angle that none of the selected reviewers will cover? If yes, spawn a purpose-built reviewer agent for it. Examples:

- GraphQL schema changes: spawn a "graphql-reviewer" focused on schema design, breaking changes, and resolver correctness
- Terraform or infrastructure-as-code: spawn an "infra-reviewer" focused on resource misconfigurations, IAM over-permissions, and blast radius
- CI/CD pipeline files: spawn a "ci-reviewer" focused on secret exposure, caching correctness, and pipeline reliability
- Cryptography or key management code: spawn a "crypto-reviewer" focused on algorithm choices, key handling, and entropy
- Data serialization or protocol buffer changes: spawn a "serialization-reviewer" focused on backward compatibility and field ordering
- Any other domain where a specialist eye would catch things the core six reviewers would miss

When spawning a custom reviewer, write a focused system prompt for it that describes its area of expertise and what to look for, then apply the same instructions and output format as all other reviewers.

## Step 5: Spawn Selected Reviewers in Parallel

Spawn all selected reviewers simultaneously, including any custom ones decided in Step 4. Do not wait for one before starting the next.

Each agent prompt MUST:
- Begin with: `MANDATORY: Read AGENTS.md and follow its rules before doing anything.`
- Include the full `PR_META` and `PR_DIFF` verbatim
- Include the full `PROJECT_CONTEXT`
- The root cause of every finding must trace back to a `+` or `-` line in the diff. Something this PR added, removed, or modified must be the source of the problem
- The impact of a finding can extend anywhere in the codebase. Actively use Read, Glob, and Grep to look for ripple effects: broken callers, missing imports, consumers of a changed API, queries that rely on a modified schema, components that depend on a changed contract. These cross-file impacts are the most important findings
- Examples of valid findings that originate in the diff but affect unchanged code: changing a function signature that breaks callers elsewhere, removing a utility that other modules still import, changing an API response shape that breaks a frontend consumer, modifying a shared config that affects downstream services, deleting a guard that other code relied on
- A finding is invalid only if it has no connection to anything changed in this PR: a pre-existing bug in unrelated code the PR never touched. Discard those
- Instruct the agent to flag anything in the changed lines that conflicts with the conventions and decisions in `PROJECT_CONTEXT`
- Instruct the agent to only flag real, confirmed issues. No speculation, no "consider whether", no low-confidence nitpicks
- Instruct the agent to write each finding the way a senior engineer writes a PR comment: direct, specific, and short. Max 2 sentences. State what is wrong and why it matters. No padding, no hedging, no "it's worth noting that", no significance inflation
- Instruct the agent to output each finding in this exact format (one finding per line):

For file-specific findings:
```
[SEVERITY] path/to/file:line | <finding text>
```

For general findings with no specific location:
```
[SEVERITY] (general) | <finding text>
```

Where SEVERITY is one of: CRITICAL, HIGH, MEDIUM, LOW. The `[SEVERITY]` tag and location are metadata for the orchestrator only. They must NOT appear in the finding text itself. The finding text is what will be posted as the comment body after humanizing.

## Step 6: Collect, Clean, and Number All Findings

Wait for all agents to complete. Collect every finding from every agent.

Deduplicate: if multiple reviewers flag the same file:line, merge into one entry that covers all concerns raised.

**Discard out-of-scope findings**: filter out any finding whose root cause has no connection to a `+` or `-` line in the diff. Pre-existing bugs in code the PR never touched are out of scope. Keep everything else, including findings where the root cause is in the diff but the impact is in an unchanged file elsewhere in the codebase.

For cross-file impact findings (root cause in the diff, problem manifests in another file): the inline comment goes on the `+` or `-` line that is the source of the breakage, with the comment body describing what it breaks and where. If the impact spans too many locations to pin to one line, make it a general finding.

Separate findings into:
- **Inline**: findings with a specific `file:line`. Include only lines that appear in the diff (lines added or modified). If a finding references a line outside the diff, convert it to a general finding.
- **General**: findings with no specific location, or those moved from inline due to being outside the diff.

**Apply the humanizer skill to every finding body before presenting or posting.** Rewrite each one to remove AI writing patterns. Specifically:
- Cut hedging: "could potentially", "it's worth noting that", "it may be the case that", "consider whether"
- Cut significance inflation: "this is a critical issue that", "it's important to ensure", "this could have serious implications"
- Cut filler openers: "In order to", "Due to the fact that", "It should be noted that"
- Cut padding -ing phrases: "ensuring that", "highlighting the need for", "contributing to"
- Make it direct and specific. If the finding says "this function could potentially cause issues in some cases", rewrite it as "this function panics if X is nil"
- Max 2 sentences per finding. If it's longer, cut it down

Assign a sequential number to every finding across both groups, sorted by severity (CRITICAL first, then HIGH, MEDIUM, LOW). Example:

```
1.  [CRITICAL] src/auth/login.ts:42: SQL injection: unsanitized input passed directly to query builder
2.  [HIGH]     src/api/users.ts:88: No rate limiting on this public endpoint
3.  [HIGH]     (general): The new payment flow has no test coverage
4.  [MEDIUM]   src/utils/config.ts:17: Magic number 86400 should be a named constant
5.  [LOW]      src/models/user.ts:103: Variable name `d` is too vague, use `deletedAt`
```

## Step 7: Present Findings and Ask What to Post

Print the full numbered list to chat.

Then ask the user three questions using AskUserQuestion:

**Question 1**: "Which findings should I post?"
- Options:
  - "Post all" — post every finding
  - "Post none" — submit the verdict only, no inline comments
  - "Describe what to post" — type a natural language instruction in the Other field

  For "Describe what to post", the user types freely in the Other field. Examples of what they might write:
  - "only post 1, 2, and 5"
  - "skip the style comments, post everything else"
  - "only post critical and high severity"
  - "don't post anything about logging"
  - "post all security findings, skip the rest"
  - "post everything except 3 and 7"

  Interpret their instruction against the numbered list and select the matching subset. If their instruction is ambiguous, err on the side of posting less and tell the user which comments you included.

**Question 2**: "Review verdict?"
- Options:
  - "Request Changes"
  - "Approve"
  - "Comment only"

**Question 3**: "Main review body (the top-level comment on the review)?"
- Options:
  - "Leave empty" — no overall review body, only inline comments
  - "Write it for me" — auto-generate a short summary from the findings being posted
  - "I'll write it" — user types their own text in the Other field

  If the user picks "I'll write it", use exactly what they type in the Other field as the review body verbatim, with no modifications.
  If the user picks "Write it for me", write a short 1-3 sentence summary in plain human language covering the main themes of the findings being posted. No bullet points, no severity tags, no AI vocabulary. Apply the humanizer skill.
  If the user picks "Leave empty", set the body to an empty string.

If the user picks "Post none" for Question 1 and "Comment only" for Question 2 and "Leave empty" for Question 3, confirm there will be nothing posted and stop.

## Step 8: Post the Review

Use the review body from Question 3 in Step 7 exactly as determined:
- User wrote it: use their text verbatim
- "Write it for me": a short human-written summary you generated from the findings
- "Leave empty": empty string

GitHub allows an empty review body, so empty string is valid.

Map the verdict to the GitHub event field:
- "Request Changes" -> `REQUEST_CHANGES`
- "Approve" -> `APPROVE`
- "Comment only" -> `COMMENT`

Build the payload and write it to `/tmp/pr_review_payload.json`:

```json
{
  "commit_id": "<HEAD_SHA>",
  "body": "<general findings body or empty string>",
  "event": "<REQUEST_CHANGES|APPROVE|COMMENT>",
  "comments": [
    { "path": "src/auth/login.ts", "line": 42, "body": "Unsanitized input goes straight into the query builder here. Use parameterized queries." },
    { "path": "src/api/users.ts", "line": 88, "body": "This endpoint has no rate limiting and is publicly accessible." }
  ]
}
```

Include in `comments` only the inline findings the user chose to post.

Post via:
```bash
gh api repos/{owner}/{repo}/pulls/{number}/reviews \
  --method POST \
  --input /tmp/pr_review_payload.json
```

After posting:
- Show a confirmation with verdict and number of comments posted
- Print the direct link to the review: `https://github.com/{owner}/{repo}/pull/{number}`
- Clean up: `rm -f /tmp/pr_review_payload.json`

## Rules

- Never post the review without explicit user confirmation in Step 7
- Never include any mention of a review tool, AI, or automated system in the posted body or comment text. Comments must read as if a human engineer wrote them directly
- Every comment body must pass the humanizer skill check: no hedging, no padding, no AI vocabulary ("crucial", "ensure", "leverage", "pivotal", "robust"), no significance inflation
- Each posted comment must be 1-3 sentences. If it cannot be said in 3 sentences it is probably not specific enough
- Only flag real, confirmed issues. Do not post speculative or low-confidence findings
- Do not use em dashes anywhere in comment text or the review body. Use commas or periods instead
- Every finding must trace back to a `+` or `-` line in the diff as its root cause. Pre-existing bugs with no connection to what this PR changed must be discarded
- Cross-file impact findings are valid and encouraged: root cause in the diff, impact anywhere in the codebase
- Inline comments must point to the `+` or `-` line that is the source of the problem. If the impact is spread across many files with no single source line, make it a general finding
- If the GitHub API call fails, print the full error response and the raw payload for diagnosis
- Deduplicate before presenting. Never show the user the same file:line twice
- If a reviewer finds nothing, do not invent findings
- Clean up `/tmp/pr_review_payload.json` whether or not the post succeeded
