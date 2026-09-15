"""backlog.json 읽기 전용 서브명령: list / get / next.

이 모듈의 함수들은 절대 backlog.json을 쓰지 않는다.
"""
from __future__ import annotations

import json
import os

import backlog_lib as bl
from backlog_cli_common import fail, load_or_fail, priority_rank


def cmd_list(args) -> int:
    data, raw, digest = load_or_fail(args.path)
    tasks = data.get("tasks", [])

    def keep(t):
        if args.status and t.get("status") != args.status:
            return False
        if args.priority is not None and t.get("priority") != (
            None if args.priority == "null" else args.priority
        ):
            return False
        if args.category and t.get("category") != args.category:
            return False
        if args.parent is not None and t.get("parent") != (
            None if args.parent == "null" else args.parent
        ):
            return False
        return not (
            args.owner is not None
            and t.get("owner") != (None if args.owner == "null" else args.owner)
        )

    filtered = [t for t in tasks if keep(t)]
    errors = bl.validate(data)

    if args.json:
        out = {
            "source": bl.source_meta(args.path, raw, digest),
            "total_tasks_in_file": len(tasks),
            "count": len(filtered),
            "validation_errors": errors,
            "tasks": filtered,
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(f"# source={os.path.basename(args.path)} sha256={digest[:12]} total={len(tasks)} shown={len(filtered)}")
        if errors:
            print(f"# ⚠ 기존 무결성 오류 {len(errors)}건 (아래 목록과 무관하게 존재)")
        for t in filtered:
            print(f"{t.get('id'):8} {t.get('status'):12} {t.get('priority') or '-':4} {t.get('category'):8} {t.get('title')}")
    return 0


def cmd_get(args) -> int:
    data, raw, digest = load_or_fail(args.path)
    task = bl.find_task(data, args.id)
    if task is None:
        ids = sorted(bl.all_ids(data))
        fail(f"id '{args.id}' 를 찾을 수 없습니다. 존재하는 id 예: {ids[:10]}{' ...' if len(ids) > 10 else ''}")

    if args.json:
        out = {"source": bl.source_meta(args.path, raw, digest), "task": task}
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(f"# source={os.path.basename(args.path)} sha256={digest[:12]}")
        print(json.dumps(task, ensure_ascii=False, indent=2))
    return 0


def cmd_next(args) -> int:
    data, raw, digest = load_or_fail(args.path)
    tasks = data.get("tasks", [])
    by_id = {t.get("id"): t for t in tasks}
    enums_priority = data.get("enums", {}).get("priority", [])

    candidates = []
    for t in tasks:
        if t.get("status") != "todo":
            continue
        deps = t.get("deps", []) or []
        if all(by_id.get(d, {}).get("status") == "done" for d in deps):
            candidates.append(t)

    candidates.sort(key=lambda t: (priority_rank(enums_priority, t.get("priority")), t.get("id")))
    if args.limit:
        candidates = candidates[: args.limit]

    if args.json:
        out = {
            "source": bl.source_meta(args.path, raw, digest),
            "count": len(candidates),
            "tasks": candidates,
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(f"# source={os.path.basename(args.path)} sha256={digest[:12]} candidates={len(candidates)}")
        for t in candidates:
            print(f"{t.get('id'):8} {t.get('priority') or '-':4} {t.get('category'):8} {t.get('title')}")
    return 0
