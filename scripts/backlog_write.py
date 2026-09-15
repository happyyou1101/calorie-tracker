"""backlog.json 쓰기 서브명령: add / set-status.

공통 규칙: 파싱·스키마·참조·순환의존성 검증을 모두 통과해야 저장하고,
저장 전 백업 + 원자적 쓰기를 쓰며, 실패 시 원본을 그대로 보존한다.
task.gate 필드는 여기서도 절대 실행하지 않는다 (opaque 문자열로만 저장).
"""
from __future__ import annotations

import backlog_lib as bl
from backlog_cli_common import ID_RE, fail, load_or_fail, next_child_id, now_iso


def cmd_add(args) -> int:
    data, _raw, digest = load_or_fail(args.path)

    if args.if_hash and args.if_hash != digest:
        fail(
            f"버전 충돌: --if-hash={args.if_hash[:12]}.. 이 현재 파일 sha256={digest[:12]}.. 와 다릅니다. "
            f"다시 조회한 뒤 재시도하세요. (원본은 변경하지 않았습니다)"
        )

    missing = []
    if not args.title:
        missing.append("--title")
    if not args.category:
        missing.append("--category")
    if not args.done_when:
        missing.append("--done-when")
    if missing:
        fail("필수 항목이 없어 추측해서 저장하지 않았습니다. 다음을 입력하세요: " + ", ".join(missing))

    enums = data.get("enums", {})
    id_set = bl.all_ids(data)

    if args.category not in enums.get("category", []):
        fail(f"category '{args.category}' 가 enums.category {enums.get('category')} 에 없습니다")
    if args.priority is not None and args.priority not in enums.get("priority", []):
        fail(f"priority '{args.priority}' 가 enums.priority {enums.get('priority')} 에 없습니다")

    parent = args.parent
    if parent is not None and parent not in id_set:
        fail(f"parent '{parent}' 가 존재하지 않는 id 입니다")

    deps = [d.strip() for d in args.deps.split(",") if d.strip()] if args.deps else []
    missing_deps = [d for d in deps if d not in id_set]
    if missing_deps:
        fail(f"deps에 존재하지 않는 id: {missing_deps}")

    if args.id:
        new_id = args.id
        if not ID_RE.match(new_id):
            fail(f"id '{new_id}' 형식이 기존 규칙(P<번호> 또는 P<번호>.<번호>)과 다릅니다")
        if parent is not None and not new_id.startswith(parent + "."):
            fail(f"id '{new_id}' 가 parent '{parent}' 하위 형식('{parent}.N')이 아닙니다")
        if new_id in id_set:
            fail(f"id '{new_id}' 가 이미 존재합니다 (중복)")
    else:
        if parent is not None:
            new_id = next_child_id(data, parent)
        else:
            fail("parent가 없는 최상위 작업은 --id를 직접 지정해야 합니다 (번호 체계를 추측하지 않음)")

    if args.est is not None:
        max_est = data.get("meta", {}).get("max_est_min")
        if isinstance(max_est, (int, float)) and args.est > max_est:
            fail(f"est={args.est} 가 meta.max_est_min={max_est} 를 초과합니다")

    new_task = {
        "id": new_id,
        "status": "todo",
        "priority": args.priority,
        "category": args.category,
        "title": args.title,
        "summary": args.summary or "",
        "where": args.where,
        "parent": parent,
        "deps": deps,
        "doc": args.doc,
        "done_when": args.done_when,
        "est_min": args.est,
        "gate": args.gate,
        "owner": None,
        "claimed_at": None,
        "updated_at": now_iso(),
        "log": [],
    }

    new_tasks = data.get("tasks", []) + [new_task]
    new_data = dict(data)
    new_data["tasks"] = new_tasks

    cycle = bl.find_cycle(new_tasks)
    if cycle:
        fail("순환 의존성이 발생해 추가하지 않았습니다: " + " -> ".join(cycle))

    errors = bl.validate(new_data)
    if errors:
        fail("추가 후 검증 실패, 저장하지 않았습니다:\n- " + "\n- ".join(errors))

    backup_path = bl.backup(args.path, args.backup_dir)
    bl.atomic_write_json(args.path, new_data)

    print(f"추가됨: {new_id} (backup: {backup_path})")
    _, _raw2, digest2 = bl.load(args.path)
    print(f"새 source sha256={digest2[:12]}")
    return 0


def cmd_set_status(args) -> int:
    data, _raw, digest = load_or_fail(args.path)

    if args.if_hash and args.if_hash != digest:
        fail(
            f"버전 충돌: --if-hash={args.if_hash[:12]}.. 이 현재 파일 sha256={digest[:12]}.. 와 다릅니다. "
            f"다시 조회한 뒤 재시도하세요. (원본은 변경하지 않았습니다)"
        )

    task = bl.find_task(data, args.id)
    if task is None:
        fail(f"id '{args.id}' 를 찾을 수 없습니다")

    enums_status = data.get("enums", {}).get("status", [])
    if args.new_status not in enums_status:
        fail(f"status '{args.new_status}' 가 enums.status {enums_status} 에 없습니다")

    old_status = task.get("status")

    notes_required_for = {"done", "needs_info", "blocked"}
    if args.new_status in notes_required_for and not (args.note or "").strip():
        fail(
            f"status를 '{args.new_status}' 로 바꾸려면 --note (근거)가 필요합니다 "
            f"(meta.note/.claude/rules/backlog.md에 명시된 규칙)"
        )

    task["status"] = args.new_status
    task["updated_at"] = now_iso()
    log_entry = {
        "at": task["updated_at"],
        "owner": args.owner,
        "status": args.new_status,
        "note": args.note or "",
    }
    task.setdefault("log", []).append(log_entry)

    errors = bl.validate(data)
    if errors:
        fail("변경 후 검증 실패, 저장하지 않았습니다:\n- " + "\n- ".join(errors))

    backup_path = bl.backup(args.path, args.backup_dir)
    bl.atomic_write_json(args.path, data)

    print(f"{args.id}: {old_status} -> {args.new_status} (backup: {backup_path})")
    _, _raw2, digest2 = bl.load(args.path)
    print(f"새 source sha256={digest2[:12]}")
    return 0
