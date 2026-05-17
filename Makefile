.PHONY: validate format lint test

# Run all validation, formatting, linting, and testing tasks for the Albino plugin.
local: validate format lint test

# Validate the Albino plugin using the Claude CLI tool.
validate:
	claude plugin validate plugins/albino

# Format the Project Memory MCP server.
format:
	bun run --cwd plugins/albino/mcp-servers/project-memory format

# Lint and typecheck the Project Memory MCP server.
lint:
	bun run --cwd plugins/albino/mcp-servers/project-memory lint
	bun run --cwd plugins/albino/mcp-servers/project-memory typecheck

# Test the Project Memory MCP server.
test:
	bun run --cwd plugins/albino/mcp-servers/project-memory test
