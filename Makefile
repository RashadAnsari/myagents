.PHONY: validate format lint test

# Run all validation, formatting, linting, and testing tasks for the Albino plugin.
local: validate format lint test

# Validate the Albino plugin and enforce AGENTS.md sync rules.
validate:
	claude plugin validate plugins/albino

# Format the Project Memory MCP server.
format:
	uv run --directory plugins/albino/mcp-servers/project-memory ruff format src tests

# Lint the Project Memory MCP server.
lint:
	uv run --directory plugins/albino/mcp-servers/project-memory ruff check src tests

# Test the Project Memory MCP server.
test:
	uv run --directory plugins/albino/mcp-servers/project-memory pytest
