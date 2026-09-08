#!/usr/bin/env bash
# PreToolUse hook on Bash: if the command is a git commit, run tests first and block on failure.
set -u
input=$(cat)
cmd=$(echo "$input" | jq -r '.tool_input.command // empty' 2>/dev/null)
case "$cmd" in
  *"git commit"*)
    cd "$CLAUDE_PROJECT_DIR" || exit 0
    if [ -f Makefile ] && grep -q '^test:' Makefile && docker compose ps --status running 2>/dev/null | grep -q api; then
      if ! make test >/tmp/socialops-test.log 2>&1; then
        echo "BLOCKED: make test failed. Fix tests before committing. Last 40 lines:" >&2
        tail -40 /tmp/socialops-test.log >&2
        exit 2
      fi
    fi
    ;;
esac
exit 0
