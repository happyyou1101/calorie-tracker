"""backlog.json 공용 IO/검증 로직.

이 모듈은 CLI(scripts/backlog.py)와 PostToolUse 훅(.claude/hooks/validate-backlog.py)이
같은 검증 규칙을 공유하기 위한 것이다.

주의: task.gate 필드는 어떤 함수도 셸/코드로 실행하지 않는다. 항상 opaque 문자열로만 다룬다.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone


class BacklogError(Exception):
    """사용자에게 그대로 보여줄 수 있는 명확한 오류."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_raw(path: str) -> bytes:
    if not os.path.isfile(path):
        raise BacklogError(f"파일을 찾을 수 없습니다: {path}")
    with open(path, "rb") as f:
        return f.read()


def load(path: str):
    """(data, raw_bytes, sha256) 반환. JSON 파싱 실패 시 BacklogError."""
    raw = read_raw(path)
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception as e:
        raise BacklogError(f"JSON 파싱 실패: {e}") from e
    return data, raw, sha256_bytes(raw)


def source_meta(path: str, raw: bytes, digest: str) -> dict:
    st = os.stat(path)
    return {
        "path": os.path.abspath(path),
        "sha256": digest,
        "bytes": len(raw),
        "mtime": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
    }


def validate(data) -> list[str]:
    """구조적으로 기계 판정 가능한 오류만 검사한다 (근거의 질적 타당성 등은 검사하지 않음)."""
    errors: list[str] = []

    if not isinstance(data, dict):
        return ["최상위가 JSON object가 아님"]

    for key in ("$schema_version", "meta", "enums", "tasks"):
        if key not in data:
            errors.append(f"최상위 키 누락: {key}")
    if errors:
        return errors

    enums = data.get("enums", {})
    status_enum = set(enums.get("status", []))
    priority_enum = set(enums.get("priority", []))
    category_enum = set(enums.get("category", []))
    max_est = data.get("meta", {}).get("max_est_min")

    tasks = data.get("tasks", [])
    if not isinstance(tasks, list):
        return ["tasks가 배열이 아님"]

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

    cycle = find_cycle(tasks)
    if cycle:
        errors.append("deps 순환 의존성 발견: " + " -> ".join(cycle))

    return errors


def find_cycle(tasks) -> list[str] | None:
    graph = {t.get("id"): (t.get("deps") or []) for t in tasks}
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {tid: WHITE for tid in graph}
    path: list[str] = []

    def visit(node):
        color[node] = GRAY
        path.append(node)
        for dep in graph.get(node, []):
            if dep not in graph:
                continue  # 없는 id 참조는 validate()의 다른 규칙이 이미 잡음
            if color.get(dep) == GRAY:
                idx = path.index(dep)
                return path[idx:] + [dep]
            if color.get(dep, WHITE) == WHITE:
                result = visit(dep)
                if result:
                    return result
        path.pop()
        color[node] = BLACK
        return None

    for tid in list(graph.keys()):
        if color[tid] == WHITE:
            result = visit(tid)
            if result:
                return result
    return None


def find_task(data, task_id):
    for t in data.get("tasks", []):
        if t.get("id") == task_id:
            return t
    return None


def all_ids(data) -> set:
    return {t.get("id") for t in data.get("tasks", [])}


def backup(path: str, backup_dir: str) -> str:
    os.makedirs(backup_dir, exist_ok=True)
    raw = read_raw(path)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    dest = os.path.join(backup_dir, f"{os.path.basename(path)}.{stamp}.bak")
    with open(dest, "wb") as f:
        f.write(raw)
    return dest


def atomic_write_json(path: str, data) -> None:
    directory = os.path.dirname(os.path.abspath(path))
    fd, tmp_path = tempfile.mkstemp(prefix=".backlog-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise
