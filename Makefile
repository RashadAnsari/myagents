.PHONY: install-claude validate-claude

# Validate the Albino plugin using the Claude CLI tool.
validate-claude:
	claude plugin validate plugins/albino

# Install the Albino plugin using the Claude CLI tool.
install-claude: validate-claude
	claude plugin marketplace add ./
	claude plugin install albino@myagents
