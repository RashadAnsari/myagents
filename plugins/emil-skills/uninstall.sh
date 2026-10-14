#!/usr/bin/env bash
# Removes every skill install.sh added from emilkowalski/skills. Run by the
# root uninstall.sh.
set -euo pipefail
# shellcheck source=../../scripts/install-lib.sh
source "$MYAGENTS_DIR/scripts/install-lib.sh"

skills_cli_repo_remove https://github.com/emilkowalski/skills

finish
