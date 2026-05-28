---
description: Create a git commit and open a pull request (creates a new branch first if on main/master)
allowed-tools: Bash(git add:*), Bash(git status:*), Bash(git diff:*), Bash(git branch:*), Bash(git checkout:*), Bash(git log:*), Bash(git push:*), Bash(gh pr create:*), Bash(gh repo view:*)
---

## Context

The `!` prefix on each line below runs the shell command inline and injects its output before the prompt is submitted.

- Current git status: !`git status`
- Current git diff (staged and unstaged changes): !`git diff HEAD`
- Current branch: !`git branch --show-current`
- Recent commits: !`git log --oneline -10`
- Default branch: !`gh repo view --json defaultBranchRef --jq '.defaultBranchRef.name' 2>/dev/null || echo "main"`

## Your task

Based on the above changes, create a single git commit and open a pull request. Follow these steps in order:

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

### Step 4: Create PR

Use `gh pr create` to open the pull request:

```bash
gh pr create \
  --title "<commit message first line>" \
  --base <default-branch> \
  --head <branch> \
  --body "<2-4 sentence description of what the PR does, derived from the diff>"
```

Use the default branch value from the context above for `--base`. The title should be the first line of the commit message.

### Rules

- Do not use any other tools or do anything else beyond these four steps.
- Do not send any text besides the tool calls and, at the very end, a single short confirmation line with the PR URL.
- If `gh` is not available or not authenticated, print the URL shown in the `git push` output and tell the user to open the PR manually.
