#!/usr/bin/env python3
"""PostToolUse(Edit|Write) hook: 방금 편집한 파일 하나에 대해 빠른 코드 품질 검사.

길이/lint/build(구문검증)는 scripts/quality_check.py --fast에 위임한다.
대상 확장자가 아니면(.py/.sh 아님) 조용히 통과한다.

timeout 설계:
  - scripts/quality_check.py 내부 외부툴 호출 1회당 20s (quality_check.py 상수)
  - 이 래퍼가 quality_check.py 전체 실행에 거는 timeout: 45s (내부 20s*2 호출 여유 포함)
  - settings.json에 설정하는 바깥 hook timeout: 60s (이 래퍼의 45s보다 커야 함)
  시간 초과는 실패로 남기고(=exit 0로 조용히 넘기지 않고 block) 통과로 처리하지 않는다.
"""
import json
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
QUALITY_CHECK = os.path.join(PROJECT_ROOT, "scripts", "quality_check.py")
WRAPPER_TIMEOUT_SEC = 45


def block(reason: str) -> None:
    print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False))


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return 0

    file_path = payload.get("tool_input", {}).get("file_path", "")
    if not file_path:
        return 0

    try:
        proc = subprocess.run(
            [sys.executable, QUALITY_CHECK, "--fast", "--file", file_path],
            capture_output=True, text=True, timeout=WRAPPER_TIMEOUT_SEC, check=False,
        )
    except subprocess.TimeoutExpired:
        block(
            f"코드 품질 빠른 검사가 {WRAPPER_TIMEOUT_SEC}s 내에 끝나지 않아 시간 초과(미검증)로 처리합니다. "
            f"'{file_path}' 상태를 확인하세요 (통과로 간주하지 않음)."
        )
        return 0

    if proc.returncode == 0:
        return 0  # PASS 또는 대상 아님(skip) - 조용히 통과

    block(
        "코드 품질 빠른 검사 실패 (길이/lint/build):\n"
        + proc.stdout.strip()
        + ("\n" + proc.stderr.strip() if proc.stderr.strip() else "")
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
