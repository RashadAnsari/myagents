---
description: Create a git commit and open a pull request (creates a new branch first if on main/master)
allowed-tools: Bash(git add:*), Bash(git status:*), Bash(git diff:*), Bash(git branch:*), Bash(git checkout:*), Bash(git log:*), Bash(git push:*), Bash(gh pr create:*), Bash(gh pr view:*), Bash(gh pr edit:*), Bash(gh repo view:*)
---

## Context

The `!` prefix on each line below runs the shell command inline and injects its output before the prompt is submitted.

- Current git status: !`git status`
- Current git diff (staged and unstaged changes): !`git diff HEAD`
- Current branch: !`git branch --show-current`
- Recent commits: !`git log --oneline -10`
- Default branch: !`gh repo view --json defaultBranchRef --jq '.defaultBranchRef.name' 2>/dev/null || echo "main"`

## Your task

Based on the above changes, create a single git commit and create or update the pull request. Follow these steps in order:

### Step 1: Branch check

Read the current branch from the context above.

If the current branch is `main` or `master`:
1. Generate a short, kebab-case branch name that describes the staged changes (e.g. `fix-login-validation`, `add-user-settings`). Keep it under 40 characters.
2. Run: `git checkout -b <branch-name>`

Otherwise, stay on the current branch. Do not switch branches.

### Step 2: Commit

Infer the commit message format from the recent commits shown above: match the exact style, prefix convention, casing, and structure used in this project. Do not impose an external convention if the project already has one.

Stage all changed files and create a single commit with the inferred message style.

### Step 3: Push

Push the branch to origin:
```
git push -u origin <current-branch>
```

### Step 4: Build PR title and body from branch diff

Run both in parallel:

```bash
git log <default-branch>..<branch> --oneline
```

```bash
git diff <default-branch>..<branch>
```

Using all commits and the full diff between the branch and the default branch:
- Derive a concise PR title that summarises the overall change (not just the latest commit).
- Derive a 2-4 sentence PR body that describes what the branch does as a whole.

### Step 5: Create or update the PR

Check whether a PR already exists for this branch:

```bash
gh pr view --json number,url 2>/dev/null
```

If a PR exists, update it:
```bash
gh pr edit --title "<title>" --body "<body>"
```

If no PR exists, create one:
```bash
gh pr create \
  --title "<title>" \
  --base <default-branch> \
  --head <branch> \
  --body "<body>"
```

### Rules

- Do not use any other tools or do anything else beyond these five steps.
- Do not send any text besides the tool calls and, at the very end, a single short confirmation line with the PR URL.
- If `gh` is not available or not authenticated, print the URL shown in the `git push` output and tell the user to open the PR manually.
