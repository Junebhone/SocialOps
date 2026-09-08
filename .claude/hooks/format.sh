#!/usr/bin/env bash
# PostToolUse hook: auto-format the file Claude just edited. Never fails the tool call.
set -u
input=$(cat)
file=$(echo "$input" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
[ -z "$file" ] && exit 0
[ -f "$file" ] || exit 0
case "$file" in
  *.py)
    command -v ruff >/dev/null 2>&1 && ruff format "$file" >/dev/null 2>&1 && ruff check --fix "$file" >/dev/null 2>&1
    ;;
  *.ts|*.tsx|*.js|*.jsx|*.css|*.json|*.md)
    if [ -f "$CLAUDE_PROJECT_DIR/web/node_modules/.bin/prettier" ]; then
      "$CLAUDE_PROJECT_DIR/web/node_modules/.bin/prettier" --write "$file" >/dev/null 2>&1
    fi
    ;;
esac
exit 0
