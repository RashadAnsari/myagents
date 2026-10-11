#!/usr/bin/env bash
# Installs or updates the third-party Archify skill (https://github.com/tt-a1i/archify)
# with the Skills CLI, using the flags of its documented non-interactive install:
#   npx -y skills add tt-a1i/archify --skill archify --agent <tool> --global --copy --yes
# Run by the root install.sh.
set -euo pipefail
# shellcheck source=../../scripts/install-lib.sh
source "$MYAGENTS_DIR/scripts/install-lib.sh"

skills_cli_skill https://github.com/tt-a1i/archify archify --copy

finish
