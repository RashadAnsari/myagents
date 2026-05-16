.PHONY: validate-claude

# Validate the Albino plugin using the Claude CLI tool.
validate-claude:
	claude plugin validate plugins/albino
