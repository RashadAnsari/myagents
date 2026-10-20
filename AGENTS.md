# Agent Rules & Conventions

Rules for all agents and subagents working in this repository.

---

## Review Crew Sync Rule

**When a new review agent is added to `plugins/albino/agents/`, the following MUST be updated in the same change:**

**`plugins/albino/skills/reviewcrew/SKILL.md`**: add the new agent to the "Spawn All Reviewers in Parallel" list (Step 1) and add its corresponding section to the report structure (Step 3).

**`plugins/albino/skills/pr-review/SKILL.md`**: add the new agent to the predefined reviewer list in Step 6 ("Select Relevant Reviewers"), including the detection rule that determines when it should be included based on changed file types or paths. If the agent is always relevant regardless of file type, add it to the "Always include" list.

**`plugins/albino/skills/audit/SKILL.md`**: add the new agent as a row in the reviewer table in Step 1, with its short name, what it covers, and any aliases the user might type for it.

**Failure to update all three files when adding a review agent is a violation of this rule.**

Review agents are any agent file whose name ends in `-reviewer.md` inside `plugins/albino/agents/`.

Codex needs no manual update here. `plugins/albino/scripts/gen-codex-agents.sh` generates the Codex TOML definitions from the Markdown agent files at install time, so the Markdown stays the single source of truth.

---

## Skill Reminder Rule

The mandatory skill list is injected once at session start via two mechanisms that must always stay in sync:

- `plugins/albino/hooks/session-start.sh`: runs on Claude Code (`SessionStart` hook), Cursor (`sessionStart` hook), and Codex (`SessionStart` hook). Claude Code and Codex share one output schema, so both use the same branch. The Cursor branch is currently a no-op due to a platform bug where `additional_context` is silently dropped. Keep the hook in place for when Cursor fixes it.
- `plugins/albino/rules/session-start.mdc`: active workaround for Cursor. Cursor loads it as an `alwaysApply` rule from the plugin's default `rules/` folder. This is the mechanism that actually delivers context to Cursor agents today.

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

## Albino Rules Rule

A rule is an instruction every agent follows, such as "pull requests have one commit". Each rule is one `plugins/albino/rules/<name>.mdc` file with a plain name and Cursor frontmatter (`description`, and `alwaysApply: true` or `globs`). That file is the single source of truth. Do not put `albino` in the file name or text: the install script adds the albino marking to every copy it writes. `session-start.mdc` is not one of these: it is the Cursor-only copy of the session-start hook text, and the script skips it.

- Cursor loads the `.mdc` files straight from the plugin.
- Claude Code and Codex cannot load rules from a plugin. `plugins/albino/scripts/sync-rules.sh` projects them at install time: one `~/.claude/rules/albino-<name>.md` per rule, with a generated-by-albino comment, (Cursor `globs` become Claude Code `paths`), and one block between `<!-- albino:rules:begin` and `<!-- albino:rules:end -->` markers in `$CODEX_HOME/AGENTS.md`, which has no path scoping.

The script only touches files and text that carry its marker, prunes what it wrote for rules that no longer exist, and removes everything it wrote on uninstall. It deletes `AGENTS.md` only when the albino block was all it held. To add, change, or remove a rule, edit the `.mdc` file; no installer change is needed. Update the rules table in `README.md` in the same change, and make sure no skill contradicts the rule.

---

## Codex Parity Rule

Codex is supported through `plugins/albino/.codex-plugin/`, beside the existing `.claude-plugin/` and `.cursor-plugin/` manifests. This mirrors how OpenAI ships its own plugins: none of the 62 plugins in `openai/plugins` uses a root `plugin.json`.

Do not add a root `plugin.json` or a root `mcp.json`. A root `plugin.json` makes Codex load the plugin through the Agent Plugins loader, which has no hook support and silently drops every hook the plugin declares (openai/codex#39895). It also stops Codex reading `.mcp.json`, forcing a duplicate MCP file.

One pair of files must stay in sync:

- `plugins/albino/.claude-plugin/plugin.json` and `plugins/albino/.codex-plugin/plugin.json`: same name, version, and author, the same description apart from the platform it names, and the same hook events wired to the same scripts. Both declare their hooks inline, as the Cursor manifest does.

`plugins/albino/.mcp.json` is shared by all three platforms. Each server sets `"cwd": "."`, which Codex resolves to the plugin root so the `$(pwd)` fallback in the command finds the plugin; Claude Code and Cursor use `${CLAUDE_PLUGIN_ROOT}` and ignore `cwd`. Declaring the file explicitly as `"mcpServers": "./.mcp.json"` in the Codex manifest is what makes Codex read it.

Codex has no equivalent of `claude plugin validate`. CI instead installs the plugin with the real CLI (`codex plugin marketplace add .` then `codex plugin add albino@myagents`), which catches a broken manifest or a wrong marketplace source path. It does not check hooks or MCP config, so those stay a review concern.

Codex cannot load subagents from a plugin. `plugins/albino/scripts/gen-codex-agents.sh` generates them into `$CODEX_HOME/agents/` as TOML. It prunes what it previously wrote when its source file is gone, and marks its output so it never touches anything hand-written in `$CODEX_HOME`.

Codex ships plugin hooks as untrusted. They are registered and enabled but do not run until the user reviews them once with `/hooks` in the Codex TUI. That is a per-machine step the installer cannot do.

---

## Skills Only Rule

The albino plugin has no `commands/` folder. Every workflow the user runs by name (`commit`, `pr-review`, `remember`, and the rest) is a skill in `plugins/albino/skills/<name>/SKILL.md`, and all three platforms load it from there:

- Claude Code merged custom commands into skills: a skill creates the same `/albino:<name>` command and takes `$ARGUMENTS`, `argument-hint`, `allowed-tools`, and inline shell expansion (`` !`cmd` ``).
- Cursor runs a skill with `/<name>`. Its `/migrate-to-skills` turns commands into skills the same way.
- Codex deprecated custom prompts in favor of skills and loads plugin skills through `"skills": "./skills/"` in its manifest. Run one with `$<name>` or `/skills`.

Do not add a `commands/` folder or a command generator back. Write every new workflow as a skill with `name` matching its folder.

Only Claude Code fills in `$ARGUMENTS` and runs `` !`cmd` `` lines. A skill that uses `$ARGUMENTS` must say, right after its first use, to take the value from the user's message when the placeholder is not filled in, and a skill that uses `` !`cmd` `` must tell the agent to run the commands itself when they are not expanded.

Every skill with side effects or a high cost (`commit`, `commit-pr`, `pr-review`, `forget`, `enrich`, `reviewcrew`, `statusline`) runs only when the user asks for it by name. It sets `disable-model-invocation: true` in `SKILL.md`, which Claude Code and Cursor read, and has an `agents/openai.yaml` with `policy: allow_implicit_invocation: false`, since Codex ignores that field. Give every new skill of that kind both. In Claude Code the model cannot see such a skill at all, so the user must type its `/` command. Cursor has had a bug where plugin skills with the flag vanish from the `/` menu (forum.cursor.com, March 2026); if they do, that is the cause.

---

## Plugin Installer Rule

The root `install.sh` and `uninstall.sh` only fetch the repo, run `plugins/<name>/install.sh` or `plugins/<name>/uninstall.sh` for every plugin folder that has an `install.sh`, and print a summary. `uninstall.sh` then deletes `~/.myagents`, keeping `agent-memory/` unless `--purge` is passed. Everything specific to a plugin (registration, platform setup, generated files) lives in that plugin's own scripts, never in the root scripts.

Every plugin folder must ship both `install.sh` and `uninstall.sh`. Each one reads `MYAGENTS_DIR` and `MYAGENTS_MARKETPLACE` from the environment, sources `scripts/install-lib.sh`, checks its own prerequisites (with `need` when a missing tool should stop the whole plugin), and ends with `finish`. `uninstall.sh` must undo every step `install.sh` takes on every platform, including files the plugin writes at runtime outside its own folder, and must leave anything the user created untouched. When you add an install step, add its removal in the same change.

System tools a plugin needs at install time or runtime go in `requirements.list` at the repository root, as `<command> <homebrew formula>`, not in the plugin's script. The root installer installs a formula only when its command is not on PATH, and installs Homebrew first when something is missing (`ensure_homebrew`). These tools, Homebrew, and its PATH line in the shell profile are the one exception to the undo rule: uninstall keeps them, since other software may depend on them.

A plugin from this repo must also be listed in `.claude-plugin/marketplace.json` and `.agents/plugins/marketplace.json`. A third-party plugin or standalone skill is a folder holding only the two scripts, which call the platform CLIs (or the Skills CLI, through `skills_cli_skill`), and is not listed in either marketplace file. Install and uninstall it the way its own README documents for each platform (its marketplace, its own CLI, or the Skills CLI), never with a method it does not mention. Where a documented tool needs to run unattended, wrap it rather than replace it, and comment why.

Every step must be idempotent. Running the installer any number of times must leave the same result as running it once, and an install rerun must update rather than fail: overwrite settings by key instead of appending, use `link_dir` for symlinks (plain `ln -sf` nests a second link inside an existing directory link), use `sync_checkout` for clones, and pair every install command with its update command. An uninstall rerun must report "Already removed." rather than fail: check that an item exists before removing it, since `claude plugin uninstall`, `claude plugin marketplace remove`, and `codex plugin marketplace remove` fail on a missing item.

Test a change by running the root installer twice and then the uninstaller twice under a throwaway `HOME`, with `MYAGENTS_REPO_URL` pointing at a local commit. Diff the config files against their state before the install: after uninstall, only the user's own content may remain.

All user-facing output goes through the library's `section`, `ok`, `note`, and `fail`, with the platform name (`Claude Code`, `Cursor`, `Codex`) as the label, in that install order. Messages are full sentences: say what happened and the one thing the user does next. Hide command output with `quietly` so it only appears on failure. Do not `echo` directly.

---

## README Sync Rule

After any change that affects the public surface of this project, update `README.md` (at `README.md` in the repository root) accordingly. This includes:

- Adding, removing, or renaming an agent, skill, command, or hook
- Changing what a command or agent does
- Changing the install process or script
- Adding or removing a plugin

Do not update README for internal implementation changes that are not visible to users (e.g. rewriting how an agent prompt is worded internally, fixing a bug inside a hook script).

---

## Architecture Diagram Rule

`README.md` shows `docs/architecture.png`, which is exported from `docs/architecture.json` with the archify skill. After any change, check whether the diagram is still accurate: a component, installer step, plugin, hook, MCP server, store, or relationship it shows was added, removed, renamed, or rewired, or a source line range it cites moved.

If it changed, edit `docs/architecture.json` following the archify skill (keep every node's `sources` pointing at the right lines, and set `meta.repository.revision` to the commit that holds those lines), then run:

```
make diagram
```

This validates and renders the diagram into `.archify/` (gitignored) and exports `docs/architecture.png`. Commit both `docs/architecture.json` and `docs/architecture.png`. Archify has no export command, so `scripts/export-diagram-png.mjs` clicks the viewer's Export > PNG in headless Chrome; set `CHROME` if Chrome is not in `/Applications`, and `ARCHIFY` if the skill is not in `~/.agents/skills/archify`.

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
