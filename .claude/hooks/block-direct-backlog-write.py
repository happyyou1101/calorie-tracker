#!/usr/bin/env python3
"""PreToolUse(Edit|Write) hook: backlog.json '직접 수정'을 막고 CLI의 add/set-status를 강제한다.

목적: "Read로 원본을 읽은 뒤 Edit으로 고치는" 경로를 원천 차단해, backlog.json에
가해지는 모든 변경이 스키마 검증·백업·원자적 쓰기를 갖춘 scripts/backlog.py
add/set-status를 거치도록 한다.

적용 범위: Edit/Write 도구가 backlog.json을 file_path로 지정하는 경우만 차단한다.
CLI(scripts/backlog.py)는 내부적으로 파이썬 open()/os.replace로 파일을 쓰며 이
도구를 거치지 않으므로 이 훅의 영향을 받지 않는다. 임의 셸 우회를 막는
보안 장치가 아니다(범위 밖의 경로는 이 훅이 보장하지 않는다).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backlog_target import is_target

DENY_MESSAGE = (
    "backlog.json은 Edit/Write로 직접 수정하지 말고 CLI를 쓰세요:\n"
    "  python3 scripts/backlog.py add --parent <id> --title .. --category .. --done-when ..\n"
    "  python3 scripts/backlog.py set-status <id> <status> --note ..\n"
    "\n"
    "(적용 범위: Edit/Write 도구가 backlog.json을 대상으로 하는 경우만 차단합니다. "
    "CLI 내부의 파일 쓰기는 이 도구를 거치지 않으므로 영향받지 않습니다.)"
)


def deny() -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": DENY_MESSAGE,
        }
    }, ensure_ascii=False))


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return 0

    tool_input = payload.get("tool_input", {}) or {}
    if is_target(tool_input.get("file_path", "")):
        deny()
    return 0


if __name__ == "__main__":
    sys.exit(main())
