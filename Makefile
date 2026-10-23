.PHONY: local validate diagram

ARCHIFY ?= $(HOME)/.agents/skills/archify/bin/archify.mjs

# Run all checks for the Albino plugin.
local: validate

# Validate the Albino plugin and enforce AGENTS.md sync rules.
validate:
	claude plugin validate plugins/albino

# Render docs/architecture.json with archify and export docs/architecture.png for the README.
diagram:
	node $(ARCHIFY) finalize architecture docs/architecture.json .archify/architecture.html --repo-root . --quality showcase
	node scripts/export-diagram-png.mjs .archify/architecture.html docs/architecture.png
