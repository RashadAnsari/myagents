---
description: 'Enrich project memory by mining 100 recently merged PRs: extracts decisions, conventions, gotchas, and architectural facts from PR discussions, review comments, and PR bodies'
allowed-tools: [Agent, Bash, mcp__plugin_albino_agent-memory__project_search, mcp__plugin_albino_agent-memory__project_remember, mcp__plugin_albino_agent-memory__user_search]
---

# Memory Enrichment

Mine the 100 most recently merged PRs in the current repository. Extract durable learnings from PR bodies, review discussions, and comments. Write what is genuinely non-obvious and useful to project memory.

## Step 1: Validate Environment

Run all three in parallel:

```bash
gh auth status
```

```bash
git rev-parse --show-toplevel
```

```bash
gh repo view --json nameWithOwner --jq '.nameWithOwner'
```

Store `PROJECT_ROOT` (from `git rev-parse`) and `REPO` (e.g. `owner/repo`). If `gh` is not authenticated, tell the user to run `gh auth login` and stop.

## Step 2: Load Existing Memory

Call `project_search` with these two queries in parallel to understand what is already captured:

- `"architecture decision convention pattern"`
- `"gotcha bug workflow dependency"`

Combine results into `EXISTING_MEMORY_SUMMARY`: a compact list of summaries already stored. Extractor agents will use this to avoid rediscovering what is already known.

## Step 3: Fetch Merged PR List

```bash
gh pr list --repo {REPO} --state merged --limit 100 \
  --json number,title,mergedAt,comments,reviews \
  --jq 'sort_by((.comments | length) + (.reviews | length)) | reverse | [.[] | {number: .number, title: .title}]'
```

Store as `PR_LIST`. Sort puts high-discussion PRs first to maximize signal in the analysis. If the repo has fewer than 100 merged PRs, proceed with however many exist. If there are no merged PRs, tell the user and stop.

Extract just the `number` field from each element so you have a flat array `PR_NUMBERS` like `[101, 99, 88, ...]`.

## Step 4: Split Into Batches and Spawn Extractor Agents

Divide `PR_NUMBERS` into batches of 10 (up to 10 batches total). Spawn all batches simultaneously. Do not wait for one to finish before starting the next.

Each extractor agent receives:
- `REPO`: the owner/repo string
- `BATCH`: a list of 10 PR numbers
- `EXISTING_MEMORY_SUMMARY`: the summary from Step 2

Use this prompt for every extractor agent (substituting values):

---

**Extractor Agent Prompt:**

```
You are a memory extractor agent. Mine GitHub PR data and return structured memory candidates as JSON.

REPO: {REPO}
BATCH: {list of PR numbers}
EXISTING_MEMORY_SUMMARY: {EXISTING_MEMORY_SUMMARY}

## Fetch PR Data

For each PR number in BATCH, run these two commands. You may run all fetch commands in parallel across all PRs in your batch.

Command A (PR body, issue comments, and review bodies):
  gh pr view {number} --repo {REPO} \
    --json number,title,body,comments,reviews \
    --jq '{
      number: .number,
      title: .title,
      body: (.body // ""),
      comments: [.comments[].body],
      review_bodies: [.reviews[] | select(.body != "") | .body]
    }'

Command B (inline review thread comments):
  gh api repos/{REPO}/pulls/{number}/comments \
    --jq '[.[] | select(.body != null and .body != "") | .body]'

If a PR fetch fails (e.g. rate limit), skip that PR and continue.

Skip any PR where the author login ends in "[bot]" or is one of:
dependabot, renovate, snyk-bot, github-actions

## What to Extract

For each PR, read the title, body, issue comments, review bodies, and inline review comments together. Extract durable learnings that meet ALL of these criteria:

INCLUDE:
- Architectural or design decisions with stated rationale ("we decided to use X because Y")
- Conventions established in review ("going forward, all X must Y", "never do Z")
- Gotchas or surprising behavior ("note that X silently fails when Y")
- Non-obvious workflow requirements ("always run X before Y")
- Bug root causes identified in discussion, not just the fix itself
- Dependency constraints or quirks surfaced during review
- Patterns explicitly adopted or rejected in this PR

EXCLUDE:
- Facts already covered in EXISTING_MEMORY_SUMMARY
- Implementation details obvious from reading the code
- Temporary state or WIP markers ("TODO: fix this later", "needs follow-up")
- Opinion without a stated reason or outcome
- Review nitpicks that did not establish a general rule
- Vague praise or encouragement ("great PR!", "looks good")
- Anything that only describes what the PR does, not why or what to do going forward

## Output Format

Return ONLY a JSON array. No prose, no explanation, no markdown fences.

Each element:
{
  "content": "Specific, concrete statement at least 40 characters long. No vague language.",
  "source_ref": "PR #<number>"
}

If a PR has no durable learnings, skip it. If the entire batch has nothing worth storing, return [].
```

---

## Step 5: Collect All Candidates

Wait for all extractor agents to complete. Parse and merge all returned JSON arrays into a single flat list `ALL_CANDIDATES`.

If parsing an agent's output fails (not valid JSON), log a warning and continue with the others. If all agents returned empty arrays or failed, tell the user "No durable learnings found in the analyzed PRs." and stop.

## Step 6: Deduplicate Within Candidates

Within `ALL_CANDIDATES`, merge candidates that describe the same fact. When two candidates overlap:

- Prefer the `content` that is more specific.
- Set `source_ref` to the earliest PR number that established the rule (e.g. `"PR #42"` if the fact first appeared there).

Also remove any candidate whose content closely matches something already in `EXISTING_MEMORY_SUMMARY`. Use semantic judgment, not exact string matching.

Store the deduplicated result as `FINAL_CANDIDATES`.

## Step 7: Write to Project Memory

For each candidate in `FINAL_CANDIDATES`, call `project_remember` with:

- `project_root`: `PROJECT_ROOT`
- `content`: candidate's `content`
- `source`: `"agent"`
- `source_ref`: candidate's `source_ref`

Call all writes in parallel. If a call returns `MemoryQualityError` with reason `duplicates`, skip that candidate silently. Do not retry.

Count how many writes succeeded (`WRITTEN_COUNT`) and how many were skipped as duplicates (`SKIPPED_COUNT`).

## Step 8: Report Results

Print a summary:

- PRs analyzed: how many from `PR_LIST`
- Memory candidates extracted: length of `ALL_CANDIDATES` before deduplication
- After deduplication: length of `FINAL_CANDIDATES`
- Written to memory: `WRITTEN_COUNT`
- Skipped (already existed): `SKIPPED_COUNT`

Then list every written memory: `content (source_ref)`.

If nothing was written, say so and explain why (all duplicates, no signal in PRs, etc.).

## Rules

- Never use em dashes in any output or written memory content. Use commas or periods instead.
- Never write temporary state, WIP markers, or facts obvious from reading the code.
- Inline review comments often carry more signal than PR bodies: extractors should weight them accordingly.
- Prefer specificity: 5 high-quality memories beat 50 vague ones.
- If `project_remember` returns any error other than `duplicates`, log it and continue.
- Never write user memories from PR analysis. PR discussions are project-scoped.
