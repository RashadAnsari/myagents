# Agent Rules & Conventions

Rules for all agents and subagents working in this repository.

---

## Review Crew Sync Rule

**When a new review agent is added to `plugins/albino/agents/`, the following MUST be updated in the same change:**

**`plugins/albino/commands/reviewcrew.md`**: add the new agent to the "Spawn All Reviewers in Parallel" list (Step 1) and add its corresponding section to the report structure (Step 3).

**`plugins/albino/commands/pr-review.md`**: add the new agent to the predefined reviewer list in Step 4 ("Select Relevant Reviewers"), including the detection rule that determines when it should be included based on changed file types or paths. If the agent is always relevant regardless of file type, add it to the "Always include" list.

**Failure to update both files when adding a review agent is a violation of this rule.**

Review agents are any agent file whose name ends in `-reviewer.md` inside `plugins/albino/agents/`.

---

## Skill Reminder Rule

The mandatory skill list is injected once at session start via:

- `plugins/albino/hooks/session-start.sh`: runs on both Claude Code (`SessionStart` hook) and Cursor (`sessionStart` hook)

The skills currently injected:

- `code-reusability`
- `dev-conventions`
- `latest-versions`
- `research-first`
- `karpathy-guidelines`
- `agent-memory`

These skills are mandatory and always active. Additional skills are available in `plugins/albino/skills/` but are opt-in and not injected automatically.

**When a new skill is added to `plugins/albino/skills/`, ask the user:**

> "A new skill `<name>` was added. Do you want it included in the agent reminder so it is enforced on every task?"

If yes: add it to the skills list in `plugins/albino/hooks/session-start.sh`. If no: leave it unchanged.

Do not silently add or skip skills. Always ask.

---

## README Sync Rule

After any change that affects the public surface of this project, update `README.md` (at `README.md` in the repository root) accordingly. This includes:

- Adding, removing, or renaming an agent, skill, command, or hook
- Changing what a command or agent does
- Changing the install process or script
- Adding or removing a plugin

Do not update README for internal implementation changes that are not visible to users (e.g. rewriting how an agent prompt is worded internally, fixing a bug inside a hook script).

---

## Verify After Changes Rule

After completing any change in this repository, run the following from the repository root:

```
make local
```

This runs plugin validation, formatting, linting, and tests in sequence. If any step fails, fix the issue and re-run until `make local` passes with no errors. Do not report a task as done until `make local` exits cleanly.

---

## General Rules

- Read this file before doing anything in this repository.
- When spawning subagents, instruct each one to read `AGENTS.md` itself before acting.
- Never write decorative section separator comments such as `# ── function_name ──`. Use plain comments or no comment at all.
- Never use the em dash character in any output, file, or generated content. Use a colon, comma, or period instead. This applies to all text: prose, comments, docstrings, strings in code, documentation, and agent prompts.
