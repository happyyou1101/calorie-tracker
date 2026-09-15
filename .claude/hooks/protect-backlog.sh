#!/bin/bash
# PreToolUse(Bash) hook: block shell-based deletion/tampering of backlog.json
input=$(cat)

if ! command -v jq >/dev/null 2>&1; then
  exit 0
fi

cmd=$(echo "$input" | jq -r '.tool_input.command // empty')

if [ -z "$cmd" ]; then
  exit 0
fi

if echo "$cmd" | grep -q 'backlog\.json' \
  && echo "$cmd" | grep -Eq '(^|[^a-zA-Z_])(rm|mv|cp|sed|truncate|shred|dd|tee)([^a-zA-Z_]|$)|>'; then
  echo '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"backlog.json은 Bash로 삭제·덮어쓰기할 수 없습니다 (rm/mv/cp/sed/truncate/shred/dd/tee/리다이렉트 차단). Edit/Write 도구로 수정하세요."}}'
fi
