#!/usr/bin/env python3
"""Stop hook: 종료 전 프로젝트 전체 코드 품질(길이/lint/build) 전체 검사.

동기 실행 규약: 실패 시 stderr에 구체적 수정 안내를 쓰고 exit 2로 종료를 막아
재작업을 요청한다. stop_hook_active가 true인 재진입에서도 여전히 실패라면
그 사실을 감추지 않되(=완료로 처리하지 않되), 무한 반복을 막기 위해 이번엔
종료를 허용한다(exit 0) — Claude Code 공식 규약: "Stop/SubagentStop 훅에서
stop_hook_active를 확인하고 true인 동안은 success를 반환하라"를 따른 것이다.

timeout 설계:
  - scripts/quality_check.py 내부 외부툴 호출 1회당 20s (quality_check.py 상수)
  - 이 래퍼가 quality_check.py --full 전체 실행에 거는 timeout: 90s
  - settings.json에 설정하는 바깥 Stop hook timeout: 120s (이 래퍼의 90s보다 커야 함)
  바깥 hook timeout이 반드시 먼저 개입해 줄 것이라 가정하지 않는다 — 이 래퍼가
  스스로 90s에서 자른다. 시간 초과는 FAIL(미검증)로 남기고 완료 근거로 쓰지 않는다.
"""
import json
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
QUALITY_CHECK = os.path.join(PROJECT_ROOT, "scripts", "quality_check.py")
WRAPPER_TIMEOUT_SEC = 90


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError):
        payload = {}

    stop_hook_active = bool(payload.get("stop_hook_active", False))

    try:
        proc = subprocess.run(
            [sys.executable, QUALITY_CHECK, "--full"],
            capture_output=True, text=True, timeout=WRAPPER_TIMEOUT_SEC, check=False,
        )
        timed_out = False
        detail = proc.stdout.strip()
        passed = proc.returncode == 0
    except subprocess.TimeoutExpired:
        timed_out = True
        detail = f"전체 품질 검사가 {WRAPPER_TIMEOUT_SEC}s 내에 끝나지 않아 시간 초과(미검증) 처리됨."
        passed = False

    if passed:
        return 0

    reason = (
        "코드 품질 전체 검사 실패 - 완료로 볼 수 없습니다"
        + (" (시간 초과)" if timed_out else "")
        + ":\n" + detail
        + "\n\n수정 후 다시 시도하세요. FAIL/NOT_CONFIGURED/TIMEOUT 항목을 모두 PASS로 만들어야 합니다."
    )

    if stop_hook_active:
        # 이미 한 번 막았는데 여전히 실패. 무한 루프 방지를 위해 종료는 허용하되,
        # 실패가 해결됐다고 보고하지 않는다 - 눈에 띄게 남긴다.
        print(
            "⚠ 코드 품질 검사 실패가 남아있는 상태에서 종료를 허용합니다 (무한 루프 방지).\n"
            "이 실패는 해결된 것이 아닙니다. 다음 세션/작업에서 반드시 다시 확인하세요.\n"
            + reason
        )
        return 0

    print(reason, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
