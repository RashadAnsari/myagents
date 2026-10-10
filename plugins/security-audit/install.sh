#!/usr/bin/env bash
# Installs or updates Cloudflare's third-party security-audit skill
# (https://github.com/cloudflare/security-audit-skill). Run by the root install.sh.
set -euo pipefail
# shellcheck source=../../scripts/install-lib.sh
source "$MYAGENTS_DIR/scripts/install-lib.sh"

skills_cli_skill https://github.com/cloudflare/security-audit-skill security-audit

finish
