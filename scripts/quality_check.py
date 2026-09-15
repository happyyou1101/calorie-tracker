#!/usr/bin/env python3
"""코드 길이 / lint / build(동등 검증) 체크.

이 프로젝트는 별도 컴파일 빌드 단계가 없는 Python/Bash 스크립트 스택이다.
"build"에 해당하는 실제 수행 가능한 검증은 다음과 같다:
  - Python: `python3 -m py_compile <file>` (구문 오류 탐지 — 컴파일 타깃이 없는
    인터프리터 언어에서 실제로 실행 가능한 최소 검증)
  - Bash:   `bash -n <file>` (구문 검사 전용 모드, 실행하지 않음)
이 결과를 "빌드 성공"으로 과장하지 않고 항상 "build(구문 검증)"이라고 표기한다.

lint:
  - Python: `python3 -m ruff check <file>`
  - Bash:   shellcheck (PATH 또는 site.getuserbase()/bin에서 탐색)
도구가 없으면 NOT_CONFIGURED로 기록하고 통과로 처리하지 않는다 (exit code에 반영).

길이 기준: 300줄 (data/backlog.json, *.md, 백업/생성물 디렉터리는 제외).

내부 서브프로세스는 각각 timeout을 두어, 훅에 설정된 바깥쪽 timeout보다
먼저 스스로 실패를 판정한다 (바깥 timeout에 기대지 않음). 시간 초과는 FAIL로 남는다.
"""
from __future__ import annotations

import argparse
import html.parser
import json
import os
import shutil
import site
import subprocess
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LENGTH_LIMIT = 300
INNER_TIMEOUT_SEC = 20

EXCLUDE_DIR_NAMES = {
    ".git",
    "__pycache__",
    "node_modules",
    "venv",
    ".venv",
    "backlog-backups",
    ".pytest_cache",
    ".ruff_cache",
    ".pycache-check",
}
SOURCE_EXTS = {".py", ".sh", ".html"}


def find_shellcheck() -> str | None:
    p = shutil.which("shellcheck")
    if p:
        return p
    candidate = os.path.join(site.getuserbase(), "bin", "shellcheck")
    if os.path.isfile(candidate):
        return candidate
    return None


def iter_source_files(root: str):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIR_NAMES]
        for fn in filenames:
            ext = os.path.splitext(fn)[1]
            if ext in SOURCE_EXTS:
                yield os.path.join(dirpath, fn)


def run_cmd(cmd: list, timeout: int = INNER_TIMEOUT_SEC, env: dict | None = None):
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False, env=env)
        return ("PASS" if proc.returncode == 0 else "FAIL", proc.returncode, proc.stdout, proc.stderr)
    except subprocess.TimeoutExpired:
        return ("TIMEOUT", None, "", f"{timeout}s 내에 끝나지 않아 시간 초과 처리(미검증)")
    except FileNotFoundError as e:
        return ("NOT_CONFIGURED", None, "", str(e))


def check_length(path: str) -> dict:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        n = sum(1 for _ in f)
    return {"status": "PASS" if n <= LENGTH_LIMIT else "FAIL", "lines": n, "limit": LENGTH_LIMIT}


def check_lint(path: str) -> dict:
    ext = os.path.splitext(path)[1]
    if ext == ".py":
        status, _code, out, err = run_cmd([sys.executable, "-m", "ruff", "check", path])
        return {"status": status, "tool": "ruff", "detail": (out + err).strip()}
    if ext == ".sh":
        sc = find_shellcheck()
        if not sc:
            return {"status": "NOT_CONFIGURED", "tool": "shellcheck", "detail": "shellcheck 실행파일을 찾을 수 없음"}
        status, _code, out, err = run_cmd([sc, path])
        return {"status": status, "tool": "shellcheck", "detail": (out + err).strip()}
    if ext == ".html":
        try:
            with open(path, "r", encoding="utf-8") as f:
                html.parser.HTMLParser().feed(f.read())
        except (OSError, UnicodeDecodeError, html.parser.HTMLParseError) as e:
            return {"status": "FAIL", "tool": "html.parser", "detail": str(e)}
        return {"status": "PASS", "tool": "html.parser", "detail": "HTML 파싱 가능"}
    return {"status": "PASS", "tool": None, "detail": "대상 아님"}


def check_build(path: str) -> dict:
    ext = os.path.splitext(path)[1]
    if ext == ".py":
        cache_dir = os.path.join(PROJECT_ROOT, ".pycache-check")
        os.makedirs(cache_dir, exist_ok=True)
        env = os.environ.copy()
        env["PYTHONPYCACHEPREFIX"] = cache_dir
        status, _code, out, err = run_cmd([sys.executable, "-m", "py_compile", path], env=env)
        return {"status": status, "tool": "py_compile", "detail": (out + err).strip()}
    if ext == ".sh":
        status, _code, out, err = run_cmd(["bash", "-n", path])
        return {"status": status, "tool": "bash -n", "detail": (out + err).strip()}
    if ext == ".html":
        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
        except OSError as e:
            return {"status": "FAIL", "tool": "static-html", "detail": str(e)}
        missing = [tag for tag in ("<!doctype html", "<script", "</script>", "<input") if tag not in text.lower()]
        detail = "정적 대시보드 필수 요소 확인" if not missing else "누락: " + ", ".join(missing)
        return {"status": "PASS" if not missing else "FAIL", "tool": "static-html", "detail": detail}
    return {"status": "PASS", "tool": None, "detail": "대상 아님"}


def check_file(path: str) -> dict:
    return {
        "file": os.path.relpath(path, PROJECT_ROOT),
        "length": check_length(path),
        "lint": check_lint(path),
        "build": check_build(path),
    }


def overall_ok(result: dict) -> bool:
    return all(result[k]["status"] == "PASS" for k in ("length", "lint", "build"))


def render(results: list) -> str:
    lines = []
    for r in results:
        ok = overall_ok(r)
        mark = "PASS" if ok else "FAIL"
        lines.append(f"[{mark}] {r['file']}")
        lines.append(
            f"    length={r['length']['status']}({r['length']['lines']}/{r['length']['limit']}) "
            f"lint={r['lint']['status']}({r['lint']['tool']}) "
            f"build={r['build']['status']}({r['build']['tool']})"
        )
        if not ok:
            if r["length"]["status"] == "FAIL":
                lines.append(f"    -> {r['length']['lines']}줄로 기준({LENGTH_LIMIT}) 초과. 책임 기준으로 파일 분리 검토.")
            if r["lint"]["status"] != "PASS":
                lines.append(f"    -> lint({r['lint']['tool']}): {r['lint']['detail'][:300]}")
            if r["build"]["status"] != "PASS":
                lines.append(f"    -> build({r['build']['tool']}): {r['build']['detail'][:300]}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true", help="지정한 --file 하나만 검사")
    ap.add_argument("--full", action="store_true", help="프로젝트 전체 소스 파일 검사")
    ap.add_argument("--file", help="--fast에서 검사할 파일 경로")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.fast:
        if not args.file:
            print("오류: --fast는 --file이 필요합니다", file=sys.stderr)
            return 2
        ext = os.path.splitext(args.file)[1]
        if ext not in SOURCE_EXTS or not os.path.isfile(args.file):
            if args.json:
                print(json.dumps({"skipped": True, "reason": "대상 확장자 아님/파일 없음"}))
            return 0
        results = [check_file(args.file)]
    elif args.full:
        results = [check_file(p) for p in sorted(iter_source_files(PROJECT_ROOT))]
    else:
        print("오류: --fast 또는 --full 중 하나가 필요합니다", file=sys.stderr)
        return 2

    ok = all(overall_ok(r) for r in results)

    if args.json:
        print(json.dumps({"ok": ok, "results": results}, ensure_ascii=False, indent=2))
    else:
        print(render(results) if results else "(검사 대상 없음)")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
