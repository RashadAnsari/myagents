# Agent Rules & Conventions

Rules for all agents and subagents working in this repository.

---

## Review Crew Sync Rule

**When a new review agent is added to `plugins/albino/agents/`, the following MUST be updated in the same change:**

**`plugins/albino/commands/reviewcrew.md`**: add the new agent to the "Spawn All Reviewers in Parallel" list (Step 1) and add its corresponding section to the report structure (Step 3).

**`plugins/albino/commands/pr-review.md`**: add the new agent to the predefined reviewer list in Step 6 ("Select Relevant Reviewers"), including the detection rule that determines when it should be included based on changed file types or paths. If the agent is always relevant regardless of file type, add it to the "Always include" list.

**`plugins/albino/commands/audit.md`**: add the new agent as a row in the reviewer table in Step 1, with its short name, what it covers, and any aliases the user might type for it.

**Failure to update all three files when adding a review agent is a violation of this rule.**

Review agents are any agent file whose name ends in `-reviewer.md` inside `plugins/albino/agents/`.

Codex needs no manual update here. `plugins/albino/scripts/gen-codex-agents.sh` generates the Codex TOML definitions from the Markdown agent files at install time, so the Markdown stays the single source of truth.

---

## Skill Reminder Rule

The mandatory skill list is injected once at session start via two mechanisms that must always stay in sync:

- `plugins/albino/hooks/session-start.sh`: runs on Claude Code (`SessionStart` hook), Cursor (`sessionStart` hook), and Codex (`SessionStart` hook). Claude Code and Codex share one output schema, so both use the same branch. The Cursor branch is currently a no-op due to a platform bug where `additional_context` is silently dropped. Keep the hook in place for when Cursor fixes it.
- `plugins/albino/rules/session-start.mdc`: active workaround for Cursor. Injected as an `alwaysApply` rule via `plugins/albino/.cursor-plugin/plugin.json`. This is the mechanism that actually delivers context to Cursor agents today.

The skills currently injected:

- `dev-conventions`
- `research-first`
- `agent-memory`

These skills are mandatory and always active. Additional skills are available in `plugins/albino/skills/` but are opt-in and not injected automatically.

**When a new skill is added to `plugins/albino/skills/`, ask the user:**

> "A new skill `<name>` was added. Do you want it included in the agent reminder so it is enforced on every task?"

If yes: add it to the skills list in BOTH `plugins/albino/hooks/session-start.sh` AND `plugins/albino/rules/session-start.mdc`. If no: leave both unchanged.

Do not silently add or skip skills. Always ask. Never update one file without updating the other.

---

## Codex Parity Rule

Codex is supported through `plugins/albino/.codex-plugin/`, beside the existing `.claude-plugin/` and `.cursor-plugin/` manifests. This mirrors how OpenAI ships its own plugins: none of the 62 plugins in `openai/plugins` uses a root `plugin.json`.

Do not add a root `plugin.json` or a root `mcp.json`. A root `plugin.json` makes Codex load the plugin through the Agent Plugins loader, which has no hook support and silently drops every hook the plugin declares (openai/codex#39895). It also stops Codex reading `.mcp.json`, forcing a duplicate MCP file.

One pair of files must stay in sync:

- `plugins/albino/.claude-plugin/plugin.json` and `plugins/albino/.codex-plugin/plugin.json`: same name, version, description, and author, and the same hook events wired to the same scripts. Both declare their hooks inline, as the Cursor manifest does.

`plugins/albino/.mcp.json` is shared by all three platforms. Each server sets `"cwd": "."`, which Codex resolves to the plugin root so the `$(pwd)` fallback in the command finds the plugin; Claude Code and Cursor use `${CLAUDE_PLUGIN_ROOT}` and ignore `cwd`. Declaring the file explicitly as `"mcpServers": "./.mcp.json"` in the Codex manifest is what makes Codex read it.

Codex has no equivalent of `claude plugin validate`. CI instead installs the plugin with the real CLI (`codex plugin marketplace add .` then `codex plugin add albino@myagents`), which catches a broken manifest or a wrong marketplace source path. It does not check hooks or MCP config, so those stay a review concern.

Codex takes commands from a plugin, but only some of them. On install it converts a plugin's `commands/` into skills named `<plugin>:source-command-<name>`, skipping any command that uses `$ARGUMENTS` or `$1`, uses Claude Code inline shell expansion (`` !`cmd` ``), or is larger than roughly 3.8 KB. Those three limits are not announced anywhere: a command that crosses one is dropped silently. Custom prompts in `$CODEX_HOME/prompts`, the other way a command could reach Codex, stopped loading in codex-cli 0.117.0 (openai/codex#15941), so a skipped command would otherwise not reach Codex at all.

`plugins/albino/scripts/gen-codex-command-skills.sh` covers the gap by generating the skipped commands into `$CODEX_HOME/skills/` as `albino-command-<name>`. It reads the `migrated-command-skills` directory Codex writes to decide which to skip, rather than reimplementing the rules above, so no command is published twice and a command that later crosses the size limit moves between the two paths on its own. Do not hardcode that skip list.

Skills take no arguments, so `$ARGUMENTS` is replaced with a phrase telling the agent to take the subject from the user's message. Keep using `description` and `argument-hint` in command frontmatter, and keep a fallback instruction wherever inline shell expansion is used.

Codex cannot load subagents from a plugin. `plugins/albino/scripts/gen-codex-agents.sh` generates them into `$CODEX_HOME/agents/` as TOML.

Both generators prune what they previously wrote when its source file is gone, and both mark their output so they never touch anything hand-written in `$CODEX_HOME`.

Codex ships plugin hooks as untrusted. They are registered and enabled but do not run until the user reviews them once with `/hooks` in the Codex TUI. That is a per-machine step the installer cannot do.

---

## Plugin Installer Rule

The root `install.sh` and `uninstall.sh` only fetch the repo, run `plugins/<name>/install.sh` or `plugins/<name>/uninstall.sh` for every plugin folder that has an `install.sh`, and print a summary. `uninstall.sh` then deletes `~/.myagents`, keeping `agent-memory/` unless `--purge` is passed. Everything specific to a plugin (registration, platform setup, generated files) lives in that plugin's own scripts, never in the root scripts.

Every plugin folder must ship both `install.sh` and `uninstall.sh`. Each one reads `MYAGENTS_DIR` and `MYAGENTS_MARKETPLACE` from the environment, sources `scripts/install-lib.sh`, checks its own prerequisites with `need`, and ends with `finish`. `uninstall.sh` must undo every step `install.sh` takes on every platform, including files the plugin writes at runtime outside its own folder, and must leave anything the user created untouched. When you add an install step, add its removal in the same change.

A plugin from this repo must also be listed in `.claude-plugin/marketplace.json` and `.agents/plugins/marketplace.json`. A third-party plugin is a folder holding only the two scripts, which call the platform CLIs, and is not listed in either marketplace file.

Every step must be idempotent. Running the installer any number of times must leave the same result as running it once, and an install rerun must update rather than fail: overwrite settings by key instead of appending, use `link_dir` for symlinks (plain `ln -sf` nests a second link inside an existing directory link), use `sync_checkout` for clones, and pair every install command with its update command. An uninstall rerun must report "Already removed." rather than fail: check that an item exists before removing it, since `claude plugin uninstall`, `claude plugin marketplace remove`, and `codex plugin marketplace remove` fail on a missing item.

Test a change by running the root installer twice and then the uninstaller twice under a throwaway `HOME`, with `MYAGENTS_REPO_URL` pointing at a local commit. Diff the config files against their state before the install: after uninstall, only the user's own content may remain.

All user-facing output goes through the library's `section`, `ok`, `note`, and `fail`, with the platform name (`Claude Code`, `Cursor`, `Codex`, `Claude Desktop`) as the label, in that install order. Messages are full sentences: say what happened and the one thing the user does next. Hide command output with `quietly` so it only appears on failure. Do not `echo` directly.

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
