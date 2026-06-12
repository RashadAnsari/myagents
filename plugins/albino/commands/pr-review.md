---
description: 'Review a GitHub pull request: analyzes changed files to select relevant reviewers, loads project and user memory, runs reviewers in parallel, lets the user pick which findings to post, then submits the review on behalf of the user via gh CLI'
argument-hint: [github-pr-url]
allowed-tools: [Agent, Bash, Read, Write, Glob, Grep, AskUserQuestion, mcp__plugin_albino_agent-memory__project_search, mcp__plugin_albino_agent-memory__user_search]
---

MANDATORY: Load the humanizer skill (`albino:humanizer`) now and keep all its rules active for the entire session. Every piece of text you write or post, including comment bodies, the review body, and any output to the user, must pass the humanizer check before it leaves your context.

# PR Review

Review the GitHub pull request: $ARGUMENTS

## Step 1: Validate Input

If `$ARGUMENTS` is empty or missing, stop immediately and tell the user:
```
Usage: /pr-review <github-pr-url>
Example: /pr-review https://github.com/owner/repo/pull/123
```

Parse `owner`, `repo`, and `number` from `$ARGUMENTS` now (URL format: `https://github.com/{owner}/{repo}/pull/{number}`). If the URL does not match this format, stop and show the usage message above.

## Step 2: Pre-Review Gate

Run both in parallel:

```bash
gh pr view "$ARGUMENTS" --json state,isDraft,author --jq '{state: .state, isDraft: .isDraft, author: .author.login}'
```

```bash
gh api repos/{owner}/{repo}/pulls/{number}/reviews --jq '[.[].user.login]'
```

Stop immediately with a clear message if any condition is true:
- `state` is not `"OPEN"` (PR is closed or merged)
- `isDraft` is `true`
- `author.login` ends in `[bot]` or is one of: `dependabot`, `renovate`, `snyk-bot`, `github-actions`
- The authenticated user's login already appears in the reviews list (run `gh api user --jq '.login'` to get it if needed)

## Step 3: Fetch PR Data

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

## Step 4: Create Isolated Review Environment

Clone the repository to a temporary directory at the PR head commit. All file reads, grep operations, and git commands in subsequent steps must target this directory, not the current working directory.

```bash
REVIEW_DIR=$(mktemp -d /tmp/pr-review-XXXXXX)
gh repo clone {owner}/{repo} "$REVIEW_DIR" -- --depth=100
git -C "$REVIEW_DIR" fetch origin pull/{number}/head:pr-review-head
git -C "$REVIEW_DIR" checkout pr-review-head
```

If any command fails, clean up with `rm -rf "$REVIEW_DIR"` and report the error.

Store `REVIEW_DIR` for use in all subsequent steps. This is the only path reviewers may use for file access and git operations.

## Step 5: Load Context

Run both in parallel:

1. Call `project_search` (agent-memory MCP server) with terms relevant to the changed files (e.g. file paths, module names, domain concepts) to load conventions, decisions, and pitfalls for this repo.
2. Call `user_search` (agent-memory MCP server) with similar terms to load user preferences relevant to this PR.

Combine into `PROJECT_CONTEXT`: a compact summary of active conventions, known decisions, and pitfalls that reviewers must apply.

## Step 6: Select Relevant Reviewers

Analyze `CHANGED_FILES` and apply the rules below to build the list of reviewers to spawn. Log which reviewers were selected and why before spawning.

**Always include:**
- `security-reviewer`
- `code-reviewer`
- `architecture-reviewer`
- `performance-reviewer`
- `test-reviewer`
- `logging-reviewer`

**Always spawn the inline `history-reviewer`** as well. It has no agent file: its task is defined in Step 7.

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
- Any other domain where a specialist eye would catch things the core reviewers would miss

When spawning a custom reviewer, write a focused system prompt for it that describes its area of expertise and what to look for, then apply the same instructions and output format as all other reviewers.

## Step 7: Spawn Selected Reviewers in Parallel

Spawn all selected reviewers simultaneously, including any custom ones decided in Step 6. Do not wait for one before starting the next.

**Model assignment per reviewer:**
- `security-reviewer`, `architecture-reviewer`, `code-reviewer`: use **Opus**
- All other reviewers (including `history-reviewer`, conditional, and custom): use **Sonnet**

Each agent prompt MUST:
- Begin with: `MANDATORY: Read AGENTS.md and follow its rules before doing anything.`
- Include the full `PR_META` and `PR_DIFF` verbatim
- Include the full `PROJECT_CONTEXT`
- Include `REVIEW_DIR` and this instruction verbatim: "All file reads (Read, Glob, Grep) and git commands must use REVIEW_DIR as the repository root. Do not read files from any other path."
- Include this instruction verbatim: "Before reviewing, call `project_search` and `user_search` (agent-memory MCP server) with terms specific to your reviewer domain and the files in the diff (e.g. file paths, module names, patterns you are about to analyze). Use the results to supplement PROJECT_CONTEXT with any additional conventions, decisions, or gotchas relevant to what you are reviewing."
- The root cause of every finding must trace back to a `+` or `-` line in the diff. Something this PR added, removed, or modified must be the source of the problem
- The impact of a finding can extend anywhere in the codebase. Actively use Read, Glob, and Grep (all against REVIEW_DIR) to look for ripple effects: broken callers, missing imports, consumers of a changed API, queries that rely on a modified schema, components that depend on a changed contract. These cross-file impacts are the most important findings
- Examples of valid findings that originate in the diff but affect unchanged code: changing a function signature that breaks callers elsewhere, removing a utility that other modules still import, changing an API response shape that breaks a frontend consumer, modifying a shared config that affects downstream services, deleting a guard that other code relied on
- A finding is invalid only if it has no connection to anything changed in this PR: a pre-existing bug in unrelated code the PR never touched. Discard those
- Instruct the agent to flag anything in the changed lines that conflicts with the conventions and decisions in `PROJECT_CONTEXT`
- Instruct the agent to only flag real, confirmed issues. No speculation, no "consider whether", no low-confidence nitpicks
- Instruct the agent to write each finding the way a senior engineer writes a PR comment: direct, specific, and short. Max 2 sentences. State what is wrong and why it matters. No padding, no hedging, no "it's worth noting that", no significance inflation
- **DO NOT FLAG** - instruct every agent to skip without exception:
  - Pre-existing issues in code this PR never touched
  - Code that looks wrong but is correct given context or surrounding comments
  - Issues a linter (eslint, tsc, ruff, mypy, etc.) will catch automatically
  - Issues already silenced with a lint-ignore, `eslint-disable`, or `# type: ignore` comment
  - Pedantic style concerns a senior engineer would not raise in a real review
  - General code quality suggestions not backed by a specific rule in `PROJECT_CONTEXT`
- For any finding that is a small, self-contained fix (6 lines or fewer, no structural changes, no edits required in multiple locations), include a GitHub committable suggestion block immediately after the finding text:

  ````
  ```suggestion
  <corrected line(s)>
  ```
  ````

  If the fix cannot be expressed completely and correctly in a single contiguous suggestion block, omit it and use prose only. Never include a partial suggestion that only fixes part of the problem.

- Instruct the agent to output each finding in this exact format (one finding per line):

For file-specific findings:
```
[SEVERITY] path/to/file:line | <finding text, including suggestion block if applicable>
```

For general findings with no specific location:
```
[SEVERITY] (general) | <finding text>
```

Where SEVERITY is one of: CRITICAL, HIGH, MEDIUM, LOW. The `[SEVERITY]` tag and location are metadata for the orchestrator only. They must NOT appear in the finding text itself.

**History reviewer instructions:**

The `history-reviewer` has a different task from the other reviewers. Its job is not to find new bugs but to provide context that reveals real problems hidden in history. Spawn it as a general-purpose agent with the mandatory prompt requirements above plus this task. For each changed hunk in `PR_DIFF`:

1. Run `git -C "$REVIEW_DIR" log --follow -p -- <file>` to understand the commit history of changed files
2. Run `git -C "$REVIEW_DIR" blame -L <start>,<end> -- <file>` on the changed lines to see who introduced them and when

Output a finding only when history reveals a real problem: e.g., a line being reverted to a version that was previously removed for a known reason, or a pattern being re-introduced that was explicitly cleaned up before. Use the same output format as all other reviewers.

## Step 8: Collect, Clean, and Number All Findings

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
- Max 2 sentences per finding body (suggestion blocks do not count toward this limit)

Assign a sequential number to every finding across both groups, sorted by severity (CRITICAL first, then HIGH, MEDIUM, LOW). Example:

```
1.  [CRITICAL] src/auth/login.ts:42: SQL injection: unsanitized input passed directly to query builder
2.  [HIGH]     src/api/users.ts:88: No rate limiting on this public endpoint
3.  [HIGH]     (general): The new payment flow has no test coverage
4.  [MEDIUM]   src/utils/config.ts:17: Magic number 86400 should be a named constant
5.  [LOW]      src/models/user.ts:103: Variable name `d` is too vague, use `deletedAt`
```

## Step 9: Confidence Scoring

For every finding collected in Step 8, spawn one **Haiku** subagent in parallel to score it. Each scorer receives:
- The finding text
- The relevant diff hunk(s) where the root cause appears
- The `PROJECT_CONTEXT`

The scorer must output a single integer 0-100 using this scale:
- 0-25: likely false positive. Code is probably correct, issue is speculative or pre-existing.
- 26-50: possible issue but uncertain. Depends on runtime context or unstated assumptions.
- 51-79: real issue but low confidence. Something is off but not conclusive.
- 80-94: high confidence. Confirmed problem with clear evidence in the diff.
- 95-100: certain. Will break in production, unambiguous bug, or clear rule violation.

**Discard any finding that scores below 80.** Do not present it to the user and do not post it.

## Step 10: Present PR Brief, Findings, and Ask What to Post

Before listing any findings, print a **PR Brief**: 2 to 4 sentences of plain-English summary of what this PR does, derived from the PR body and diff. Cover the problem or goal, the approach taken, and any notable side effects or risks. Do not copy the PR body verbatim; synthesise it. If the PR body is empty, derive the summary from the diff alone.

Apply the humanizer skill to the summary sentences before printing.

If findings remain after scoring, print the full numbered list below the PR Brief. If none remain, tell the user "No issues found." and proceed directly to the verdict questions below - do not ask Question 1.

**Question 1** (skip if no findings): "Which findings should I post? Pick an option, or type a description in Other (e.g. 'only 1 and 3', 'only critical and high', 'skip logging findings')."
- Options:
  - "Post all" - post every finding
  - "Post none" - submit the verdict only, no inline comments

  If the user types in Other, interpret it as a natural language instruction against the numbered list. If ambiguous, err on the side of posting less and tell the user which comments you included.

**Question 2**: "Review verdict?"
- Options:
  - "Request Changes"
  - "Approve"
  - "Comment only"

**Question 3**: "Review body? Type your own text in Other, or leave empty."
- Options:
  - "Leave empty" - no top-level comment, only inline comments

  If the user types in Other, use their text verbatim as the review body with no modifications.
  If the user picks "Leave empty", set the body to an empty string.

If the user picks "Comment only" for Question 2 and "Leave empty" for Question 3 (and there are no findings or they chose "Post none"), confirm there will be nothing posted and stop.

## Step 11: Post the Review

Use the review body from Question 3 in Step 10 exactly as determined:
- User typed in Other: use their text verbatim
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
    { "path": "src/api/users.ts", "line": 88, "body": "This endpoint has no rate limiting and is publicly accessible.\n\n```suggestion\nrouter.get('/users', rateLimiter({ max: 100 }), usersHandler);\n```" }
  ]
}
```

Include in `comments` only the inline findings the user chose to post. If a finding includes a committable suggestion block, include it verbatim in the `body` field after the finding text, separated by a blank line.

Post via:
```bash
gh api repos/{owner}/{repo}/pulls/{number}/reviews \
  --method POST \
  --input /tmp/pr_review_payload.json
```

After posting:
- Show a confirmation with verdict and number of comments posted
- Print the direct link to the review: `https://github.com/{owner}/{repo}/pull/{number}`
- Clean up: `rm -f /tmp/pr_review_payload.json && rm -rf "$REVIEW_DIR"`

## Rules

- Never post the review without explicit user confirmation in Step 10
- Never include any mention of a review tool, AI, or automated system in the posted body or comment text. Comments must read as if a human engineer wrote them directly
- Every comment body must pass the humanizer skill check: no hedging, no padding, no AI vocabulary ("crucial", "ensure", "leverage", "pivotal", "robust"), no significance inflation
- Each posted comment must be 1-3 sentences (suggestion blocks do not count). If it cannot be said in 3 sentences it is probably not specific enough
- Only flag real, confirmed issues. Do not post speculative or low-confidence findings
- Do not use em dashes anywhere in comment text or the review body. Use commas or periods instead
- Every finding must trace back to a `+` or `-` line in the diff as its root cause. Pre-existing bugs with no connection to what this PR changed must be discarded
- Cross-file impact findings are valid and encouraged: root cause in the diff, impact anywhere in the codebase
- Inline comments must point to the `+` or `-` line that is the source of the problem. If the impact is spread across many files with no single source line, make it a general finding
- If the GitHub API call fails, print the full error response and the raw payload for diagnosis
- Deduplicate before presenting. Never show the user the same file:line twice
- If a reviewer finds nothing, do not invent findings
- Clean up `/tmp/pr_review_payload.json` whether or not the post succeeded
- Never present or post any finding that scored below 80 in Step 9
- Never include a partial committable suggestion. If the fix cannot be expressed completely in one contiguous block, use prose only
