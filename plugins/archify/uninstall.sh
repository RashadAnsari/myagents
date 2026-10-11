#!/usr/bin/env bash
# Removes the Archify skill with the Skills CLI that installed it. Run by the
# root uninstall.sh.
set -euo pipefail
# shellcheck source=../../scripts/install-lib.sh
source "$MYAGENTS_DIR/scripts/install-lib.sh"

skills_cli_skill_remove archify

finish
