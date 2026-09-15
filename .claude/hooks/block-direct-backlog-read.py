#!/usr/bin/env python3
"""PreToolUse hook: backlog.json '직접 읽기'를 막고 scripts/backlog.py CLI 사용을 유도한다.

적용 범위 (이것만 확인함, 그 이상을 보장하지 않음):
  - Read 도구가 backlog.json을 file_path로 지정하는 경우
  - Grep/Glob 도구가 backlog.json 단독 파일을 대상으로 지정하는 경우
    (디렉터리 전체 검색은 막지 않는다 — 일반 문서 검색을 깨뜨리지 않기 위함)
  - Bash에서 cat/head/tail/less/more/jq/sed/awk/strings/xxd/od/python/node 등으로
    backlog.json을 직접 여는 것으로 보이는 명령

이 훅은 "임의의 셸 코드를 통한 모든 우회를 막는 보안 장치"가 아니다.
예: base64로 인코딩한 뒤 디코드, 파일을 다른 이름으로 복사한 뒤 그 사본을 읽기,
    /proc 등 우회 경로, 훅이 파싱하지 못하는 복잡한 따옴표/치환 등은 막지 못한다.

scripts/backlog.py CLI를 사용하는 Bash 호출(명령에 'scripts/backlog.py' 또는
'backlog_lib.py' 참조가 있는 경우)은 항상 허용한다 — CLI 내부의 파일 읽기/쓰기까지
막으면 CLI 자체가 동작할 수 없기 때문이다.

CLI가 없거나 실패하는 경우 이 훅은 그것을 스스로 진단하지 않는다. 차단 메시지에
scripts/backlog.py, scripts/backlog_lib.py 존재 여부와 오류 메시지를 직접 확인하라고
안내할 뿐이며, 대신 cat 등으로 우회하라고 하지 않는다.

주의: 이 훅은 task.gate 필드를 읽거나 실행하지 않는다 (해당 없음이지만 원칙 고정).
"""
from __future__ import annotations

import json
import os
import shlex
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backlog_target import is_target

READ_VERBS = {
    "cat", "head", "tail", "less", "more", "bat", "strings", "xxd", "od",
    "hexdump", "jq", "nl", "sed", "awk", "python", "python3", "node", "view",
}

CLI_MARKERS = ("scripts/backlog.py", "backlog_lib.py")

DENY_MESSAGE = (
    "backlog.json은 직접 읽지 말고 CLI를 쓰세요:\n"
    "  python3 scripts/backlog.py list [--status ..|--priority ..|--category ..|--parent ..]\n"
    "  python3 scripts/backlog.py get <id>\n"
    "  python3 scripts/backlog.py next\n"
    "\n"
    "(적용 범위: Read 도구 / Grep·Glob의 backlog.json 단독 대상 / Bash의 cat·head·tail·jq·"
    "sed·awk·python 등 일반적인 직접 읽기 시도만 차단합니다. 임의 셸 우회를 전부 막는 "
    "보안 장치가 아닙니다. CLI가 없거나 실패하면 scripts/backlog.py, "
    "scripts/backlog_lib.py 존재 여부와 오류 메시지를 확인하세요 — cat으로 우회하지 마세요.)"
)


def deny(reason: str = DENY_MESSAGE) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }, ensure_ascii=False))


def check_read(tool_input: dict) -> bool:
    return is_target(tool_input.get("file_path", ""))


def check_grep_or_glob(tool_input: dict) -> bool:
    # Grep: path(파일/디렉터리), glob(파일 필터). Glob 도구: pattern(파일 경로/글롭), path(기준 디렉터리).
    for key in ("path", "glob", "pattern"):
        val = tool_input.get(key)
        if val and is_target(val):
            return True
    return False


def check_bash(tool_input: dict) -> bool:
    command = tool_input.get("command", "") or ""
    if not command:
        return False
    if any(marker in command for marker in CLI_MARKERS):
        return False  # CLI 자체 호출은 항상 허용

    segments = _split_shell_segments(command)

    for seg in segments:
        seg = seg.strip()
        if not seg:
            continue
        try:
            tokens = shlex.split(seg)
        except ValueError:
            continue
        if not tokens:
            continue
        prog = os.path.basename(tokens[0])
        if prog not in READ_VERBS:
            continue

        if prog in ("python", "python3", "node") and "-c" in tokens:
            idx = tokens.index("-c")
            if idx + 1 < len(tokens) and "backlog.json" in tokens[idx + 1]:
                return True
            continue

        for tok in tokens[1:]:
            if tok.startswith("-"):
                continue
            if is_target(tok):
                return True
    return False


def _split_shell_segments(command: str):
    import re
    return re.split(r"&&|\|\||\||;|\n", command)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return 0

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}

    hit = False
    if tool_name == "Read":
        hit = check_read(tool_input)
    elif tool_name in ("Grep", "Glob"):
        hit = check_grep_or_glob(tool_input)
    elif tool_name == "Bash":
        hit = check_bash(tool_input)

    if hit:
        deny()
    return 0


if __name__ == "__main__":
    sys.exit(main())
