#!/usr/bin/env python3
"""backlog.json 조회·작업추가·상태수정 CLI 진입점 (argparse 배선만 담당).

실제 로직: backlog_read.py(list/get/next, 읽기 전용), backlog_write.py(add/set-status, 쓰기),
공용 IO/검증은 backlog_lib.py, CLI 전용 헬퍼는 backlog_cli_common.py.

사용 예:
  python3 scripts/backlog.py list --status todo
  python3 scripts/backlog.py get P3.2
  python3 scripts/backlog.py next
  python3 scripts/backlog.py list --json   # 전수 순회(문서화용) - 필터 없으면 전체 태스크
  python3 scripts/backlog.py add --parent P3 --title "..." --category feature --done-when "..."
  python3 scripts/backlog.py set-status P3.2 in_progress --note "착수"
"""
from __future__ import annotations

import argparse
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DEFAULT_BACKLOG_PATH = os.path.join(PROJECT_ROOT, "backlog.json")
DEFAULT_BACKUP_DIR = os.path.join(PROJECT_ROOT, ".claude", "backlog-backups")

sys.path.insert(0, SCRIPT_DIR)
from backlog_read import cmd_get, cmd_list, cmd_next
from backlog_write import cmd_add, cmd_set_status


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="backlog.json 조회/작업추가/상태수정 CLI")
    p.add_argument("--path", default=DEFAULT_BACKLOG_PATH, help="backlog.json 경로 (기본: 프로젝트 루트)")
    p.add_argument("--backup-dir", default=DEFAULT_BACKUP_DIR, help="쓰기 전 백업 디렉토리")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("list", help="목록 조회 (읽기 전용, 필터 없으면 전체)")
    sp.add_argument("--status")
    sp.add_argument("--priority", help="P0|P1|P2|P3|null")
    sp.add_argument("--category")
    sp.add_argument("--parent", help="상위 id 또는 'null'")
    sp.add_argument("--owner", help="담당자 또는 'null'")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_list)

    sp = sub.add_parser("get", help="문자열 id로 상세 조회 (읽기 전용)")
    sp.add_argument("id")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_get)

    sp = sub.add_parser("next", help="의존성이 모두 done인 착수 후보 조회 (읽기 전용)")
    sp.add_argument("--limit", type=int, default=None)
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_next)

    sp = sub.add_parser("add", help="작업 추가 (쓰기)")
    sp.add_argument("--id")
    sp.add_argument("--title")
    sp.add_argument("--category")
    sp.add_argument("--priority")
    sp.add_argument("--parent")
    sp.add_argument("--summary")
    sp.add_argument("--done-when", dest="done_when")
    sp.add_argument("--est", type=int)
    sp.add_argument("--gate")
    sp.add_argument("--where")
    sp.add_argument("--deps", help="쉼표로 구분된 id 목록")
    sp.add_argument("--doc")
    sp.add_argument("--if-hash", dest="if_hash")
    sp.set_defaults(func=cmd_add)

    sp = sub.add_parser("set-status", help="상태 수정 (쓰기)")
    sp.add_argument("id")
    sp.add_argument("new_status")
    sp.add_argument("--note")
    sp.add_argument("--owner")
    sp.add_argument("--if-hash", dest="if_hash")
    sp.set_defaults(func=cmd_set_status)

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
