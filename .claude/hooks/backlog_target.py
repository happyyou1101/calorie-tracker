"""backlog.json 대상 경로 판정 공용 로직 (read-block/write-block 훅 공유).

BACKLOG_HOOK_TARGET 환경변수는 테스트 전용 오버라이드다. 실제 settings.json
배선은 이 값을 설정하지 않으며, 그 경우 항상 프로젝트의 실제 backlog.json을
대상으로 한다.
"""
import os

HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(HOOKS_DIR))  # .claude/hooks -> .claude -> project root
TARGET_PATH = os.path.realpath(
    os.environ.get("BACKLOG_HOOK_TARGET") or os.path.join(PROJECT_ROOT, "backlog.json")
)


def is_target(path_str: str) -> bool:
    if not path_str:
        return False
    try:
        candidate = path_str
        if not os.path.isabs(candidate):
            candidate = os.path.join(PROJECT_ROOT, candidate)
        return os.path.realpath(candidate) == TARGET_PATH
    except (OSError, ValueError, TypeError):
        return False
