"""backlog.py 서브명령들이 공유하는 소소한 CLI 유틸리티.

backlog_lib.py와의 차이: 이 모듈은 sys.exit를 부르는 CLI 전용 헬퍼를 담고,
backlog_lib.py는 훅에서도 재사용하는 순수 IO/검증 로직만 담는다.
"""
from __future__ import annotations

import re
import sys
from datetime import datetime, timezone

import backlog_lib as bl

ID_RE = re.compile(r"^P\d+(\.\d+)?$")


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fail(msg: str) -> None:
    print(f"오류: {msg}", file=sys.stderr)
    sys.exit(1)


def load_or_fail(path: str):
    try:
        return bl.load(path)
    except bl.BacklogError as e:
        fail(str(e))


def priority_rank(enums_priority: list, value):
    try:
        return enums_priority.index(value)
    except ValueError:
        return len(enums_priority)


def next_child_id(data, parent_id: str) -> str:
    prefix = parent_id + "."
    max_n = 0
    for t in data.get("tasks", []):
        tid = t.get("id", "")
        if tid.startswith(prefix):
            rest = tid[len(prefix):]
            if rest.isdigit():
                max_n = max(max_n, int(rest))
    return f"{parent_id}.{max_n + 1}"
