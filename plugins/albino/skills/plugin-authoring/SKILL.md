---
name: plugin-authoring
description: 'Best practices for writing skills and agents: descriptions, structure, token efficiency, frontmatter, tool scoping, and common authoring mistakes. Activate when creating or editing a SKILL.md, a command file, or an agent file, or when the user asks to "write a skill", "add a command", "create an agent", or "review this skill".'
---

# Plugin Authoring

Rules for writing skills and agents. Apply them when creating or editing any of these files.

## Universal Rules

- Assume the model is already smart. Only write what it does not already know: project facts, exact procedures, output contracts. Cut explanations of general concepts. Challenge every line: "does this justify its token cost?"
- Write descriptions in third person, stating both what the artifact does and when to use it. Include the trigger phrases a user would naturally say. Put the key use case first: listings truncate long descriptions.
- Use one consistent term per concept throughout a file. Do not mix synonyms.
- No time-sensitive content. Nothing that becomes wrong on a date.
- Forward slashes in all paths.
- Platform-neutral wording: the same file must read correctly in every editor that loads it. No editor-specific product names or jargon in prose.
- Never reference another plugin file by repo-relative path. The install location differs from the source repo. Invoke skills by name and locate scripts via the plugin or skill root variable.

## Skills

Frontmatter: `name` (lowercase letters, numbers, hyphens, max 64 chars) and `description` (max 1024 chars, non-empty). Everything else is optional.

- Keep the body under 500 lines. When approaching the limit, split detail into supporting files in the skill directory and link them from SKILL.md, one level deep only. Give reference files longer than 100 lines a table of contents.
- Match specificity to fragility. Judgment tasks get short, high-freedom guidance. Fragile sequences get exact commands with "do not modify" instructions. One default approach with an escape hatch beats a menu of options.
- For multi-step workflows, write numbered steps. For quality-critical output, build a feedback loop: produce, validate, fix, repeat until the validator passes.
- Side-effect or high-cost workflows the user must trigger themselves (commit, deploy, publish) set `disable-model-invocation: true`. The model then cannot see the skill at all, so the user must type its `/` command. Codex ignores that flag, so also add `agents/openai.yaml` beside `SKILL.md` with `policy: allow_implicit_invocation: false`. Cursor has had a bug where plugin skills with the flag vanish from the `/` menu; if they do, that is the cause. Background knowledge that is not a meaningful action: set `user-invocable: false`.
- Bundled scripts: instruct execution, not reading, unless the algorithm itself is the reference. Scripts must handle their own error cases instead of failing back to the model, and every constant needs a justifying comment.
- A loaded skill stays in context for the whole session. Write standing instructions, not one-time steps.

## Workflow Skills

Write every workflow the user runs by name as a skill, never as a command: Claude Code merged commands into skills, Cursor migrates them, and Codex deprecated custom prompts. All skill rules apply, plus:

- Scope `allowed-tools` to exactly what the task needs (e.g. `Bash(git add:*)`, not `Bash`).
- Declare `argument-hint` when the skill takes arguments, and consume them with `$ARGUMENTS` or positional placeholders. Validate missing arguments first and show a usage line. Only Claude Code fills them in, so say right after the first use to take the value from the user's message when the placeholder is left as written.
- Inject live data with `` !`command` `` lines so the prompt arrives with current state (diff, status, branch) instead of instructing the model to fetch it. Only Claude Code runs them, so tell the agent to run the commands itself when they are left as written.
- End with an explicit task framing: what to do, what not to do, what output is allowed.

## Agents

Frontmatter: `name` and `description` are required.

- One job per agent. The description states when to delegate and includes trigger phrases; add "use proactively" only if it should run without being asked.
- Restrict `tools` to the minimum the job needs. Reviewers and researchers get read-only tools.
- Set `model` to the cheapest model that does the job well. Without it the agent inherits the main conversation's model, which silently multiplies cost when many agents spawn in parallel.
- The body is the system prompt. State the role in one paragraph, the process as numbered steps, and the exact output format. Prefer category headers with a one-line scope over exhaustive per-item checklists: the model already knows what each item means, and every bullet is paid for on every spawn.
- Agents start with fresh context. They do not see the conversation. The spawn prompt must carry everything they need: inputs, constraints, working directory, and output contract.

## Checklist Before Shipping

- Description: third person, what + when, trigger phrases present
- Body: nothing the model already knows, under 500 lines, consistent terms
- Supporting files linked one level deep, scripts executed not loaded
- Tools and invocation control scoped to the artifact's job
- No repo-relative paths to other plugin files, no platform-specific terms, no em dashes
- Test by invoking with a real request before sharing
