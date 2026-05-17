# Agent Rules & Conventions

Rules for all agents and subagents working in this repository.

---

## Ultra-Reviewer Sync Rule

**When a new review agent is added to `plugins/albino/agents/`, the following MUST be updated in the same change:**

**`plugins/albino/commands/ultrareview.md`** — add the new agent to the "Spawn All Reviewers in Parallel" list (Step 1) and add its corresponding section to the report structure (Step 3).

**Failure to update this file when adding a review agent is a violation of this rule.**

Review agents are any agent file whose name ends in `-reviewer.md` inside `plugins/albino/agents/`.

---

## Skill Reminder Sync Rule

The following skills are injected into every agent prompt via the reminder hook (`hooks/agents-reminder.sh`):

- `agent-protocol`
- `code-reusability`
- `dev-conventions`
- `latest-versions`
- `research-first`

**When a new skill is added to `plugins/albino/skills/`, ask the user:**

> "A new skill `<name>` was added. Do you want it included in the agent reminder so it is enforced on every task?"

If the user says yes — add it to the list in `hooks/agents-reminder.sh`. If no — leave the hook unchanged.

Do not silently add or skip skills. Always ask.

---

## README Sync Rule

After any change that affects the public surface of this project, update `README.md` accordingly. This includes:

- Adding, removing, or renaming an agent, skill, command, or hook
- Changing what a command or agent does
- Changing the install process or script
- Adding or removing a plugin

Do not update README for internal implementation changes that are not visible to users (e.g. rewriting how an agent prompt is worded internally, fixing a bug inside a hook script).

---

## General Rules

- Read this file before doing anything in this repository.
- When spawning subagents, instruct each one to read `AGENTS.md` itself before acting.
- Do not create `README.md` or `CLAUDE.md` unless explicitly instructed.
