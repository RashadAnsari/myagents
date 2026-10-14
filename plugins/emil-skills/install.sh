#!/usr/bin/env bash
# Installs or updates Emil Kowalski's third-party design engineering skills
# (https://github.com/emilkowalski/skills) with the Skills CLI, as its README
# documents: npx skills@latest add emilkowalski/skills
# Run by the root install.sh.
set -euo pipefail
# shellcheck source=../../scripts/install-lib.sh
source "$MYAGENTS_DIR/scripts/install-lib.sh"

skills_cli_repo https://github.com/emilkowalski/skills

finish
