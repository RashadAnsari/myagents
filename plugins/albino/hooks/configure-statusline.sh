#!/usr/bin/env bash
input=$(cat)

CWD=$(echo "$input" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(d.get('workspace', {}).get('current_dir') or d.get('cwd', ''))
" 2>/dev/null)

CTX_PCT=$(echo "$input" | python3 -c "
import sys, json
d = json.load(sys.stdin)
pct = d.get('context_window', {}).get('used_percentage')
print(int(pct) if pct is not None else '')
" 2>/dev/null)

MODEL=$(echo "$input" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(d.get('model', {}).get('display_name') or '')
" 2>/dev/null)

DIR="${CWD##*/}"
BRANCH=$(git -C "$CWD" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
DIRTY=$(git -C "$CWD" status --porcelain 2>/dev/null | grep -q . && echo "1" || echo "")
TIME=$(date +%H:%M)

R=$'\033[0m'
BG=$'\033[1;32m'
CY=$'\033[36m'
BB=$'\033[1;34m'
RE=$'\033[31m'
BL=$'\033[34m'
BY=$'\033[1;33m'
YE=$'\033[33m'

# Build parts array, join with single space
parts=()
parts+=("${BG}➜${R}")
parts+=("${CY}${DIR}${R}")

[ -n "$BRANCH" ] && parts+=("${BB}git:(${RE}${BRANCH}${BL})${R}")

[ -n "$MODEL" ] && parts+=("${BB}[${RE}${MODEL}${BL}]${R}")

if [ -n "$CTX_PCT" ]; then
  [ "$CTX_PCT" -ge 80 ] && CC=$'\033[31m' || { [ "$CTX_PCT" -ge 50 ] && CC=$'\033[33m' || CC=$'\033[32m'; }
  parts+=("${CC}Ctx(${CTX_PCT}%)${R}")
fi

[ -n "$DIRTY" ] && parts+=("${YE}✗${R}")

parts+=("${BY}⌚ ${TIME}${R}")

(IFS=' '; printf "%s\n" "${parts[*]}")
