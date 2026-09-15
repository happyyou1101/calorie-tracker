#!/usr/bin/env python3
"""PostToolUse(Edit|Write) hook: backlog.json 구조 무결성 검증.

주의: task.gate 필드는 절대 읽어서 실행하지 않는다 (검토만 대상).
"""
import json
import os
import sys


def block(reason: str) -> None:
    print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False))


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return 0

    file_path = payload.get("tool_input", {}).get("file_path", "")
    if os.path.basename(file_path) != "backlog.json":
        return 0

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as e:
        block(f"backlog.json JSON 파싱 실패: {e}. 문법 오류를 먼저 고치세요.")
        return 0

    errors = []
    enums = data.get("enums", {})
    status_enum = set(enums.get("status", []))
    priority_enum = set(enums.get("priority", []))
    category_enum = set(enums.get("category", []))
    max_est = data.get("meta", {}).get("max_est_min")

    tasks = data.get("tasks", [])
    ids = [t.get("id") for t in tasks]
    id_set = set(ids)

    if len(ids) != len(id_set):
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        errors.append(f"중복된 id 존재: {dupes}")

    for t in tasks:
        tid = t.get("id", "?")
        if t.get("status") not in status_enum:
            errors.append(f"{tid}: status '{t.get('status')}' 가 enums.status에 없음")
        if t.get("priority") not in priority_enum:
            errors.append(f"{tid}: priority '{t.get('priority')}' 가 enums.priority에 없음")
        if t.get("category") not in category_enum:
            errors.append(f"{tid}: category '{t.get('category')}' 가 enums.category에 없음")

        parent = t.get("parent")
        if parent is not None and parent not in id_set:
            errors.append(f"{tid}: parent '{parent}' 가 존재하지 않는 id")

        for dep in t.get("deps", []) or []:
            if dep not in id_set:
                errors.append(f"{tid}: deps에 존재하지 않는 id '{dep}'")

        if not (t.get("done_when") or "").strip():
            errors.append(f"{tid}: done_when이 비어있음")

        est = t.get("est_min")
        if est is not None and isinstance(max_est, (int, float)) and est > max_est:
            errors.append(f"{tid}: est_min={est} 가 meta.max_est_min={max_est} 초과")

        if t.get("status") == "done":
            log = t.get("log", []) or []
            done_logs = [
                l for l in log
                if l.get("status") == "done" and (l.get("note") or "").strip()
            ]
            if not done_logs:
                errors.append(f"{tid}: status=done 인데 log에 근거(note)가 없음")

    if errors:
        block(
            f"backlog.json 무결성 오류 {len(errors)}건:\n- "
            + "\n- ".join(errors)
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
