#!/usr/bin/env bash
# Claude Code sends the tool call as JSON on stdin.
input=$(cat)
if echo "$input" | grep -qE '\.env|id_rsa|credentials|\.ssh/'; then
  echo "Blocked by deny-secrets hook: touching secret files is not allowed" >&2
  exit 2   # exit code 2 = block this tool call
fi
exit 0     # anything else = allow
