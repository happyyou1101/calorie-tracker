---
paths:
  - "backlog.json"
---

# backlog.json 취급 규칙

- 이 파일은 기계 파싱용 SSOT다. `enums`에 정의된 값(status/priority/category)
  밖의 값을 넣지 않는다.
- 새 태스크를 추가할 때: `done_when`은 필수, `est_min`은 리프 태스크에만
  부여하고 `meta.max_est_min` 이하로 맞춘다.
- `deps`/`parent`는 실제로 존재하는 `id`만 참조한다 (없는 id 참조 금지).
- `status`를 `done`으로 바꿀 때는 근거를 `log`에 남긴다. 근거 없이
  완료로 표시하지 않는다.
- 요구사항 문서(`calorie-tracker-requirements.md`)에 없는 내용을 추측해서
  태스크를 만들거나 범위를 넓히지 않는다. 애매하면 `needs_info` 상태로
  두고 `log`에 사유를 남긴 뒤 사용자에게 질문한다.
- 스키마(`$schema_version`, 필드 구성) 자체를 바꿔야 할 것 같으면
  먼저 사용자에게 확인한다 — 이 파일을 참조하는 다른 곳(문서·대화 맥락)이
  있을 수 있다.
