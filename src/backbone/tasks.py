from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .models import TaskRecord

TASK_PATTERN = re.compile(r"^- \[(?P<check>[ xX])\] (?P<body>.+)$")


class TaskError(RuntimeError):
    pass


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def tasks_file() -> Path:
    return repo_root() / "TASKS.md"


def verify_state_file() -> Path:
    return repo_root() / ".backbone" / "verify_state.json"


def parse_task_line(line: str, line_no: int) -> TaskRecord | None:
    m = TASK_PATTERN.match(line.strip())
    if not m:
        return None

    body = m.group("body")
    parts = [p.strip() for p in body.split(" | ")]
    if len(parts) < 6:
        raise TaskError(f"Malformed task line at {line_no}: {line.strip()}")

    task_id = parts[0]
    fields: dict[str, str] = {}
    for p in parts[1:]:
        if "=" not in p:
            raise TaskError(f"Malformed key=value segment at {line_no}: {p}")
        k, v = p.split("=", 1)
        fields[k.strip()] = v.strip()

    status = fields.get("status")
    if status not in {"backlog", "in_progress", "blocked", "done"}:
        raise TaskError(f"Invalid status '{status}' at {line_no}")

    req_tests = [t.strip() for t in fields.get("required_tests", "").split(",") if t.strip()]
    evidence = [e.strip() for e in fields.get("evidence", "").split(",") if e.strip()]

    return TaskRecord(
        task_id=task_id,
        checked=m.group("check").lower() == "x",
        status=status,
        title=fields.get("title", ""),
        required_tests=req_tests,
        evidence=evidence,
        dod=fields.get("dod", ""),
        line_no=line_no,
        raw_line=line.rstrip("\n"),
    )


def load_tasks() -> list[TaskRecord]:
    lines = tasks_file().read_text(encoding="utf-8").splitlines()
    tasks: list[TaskRecord] = []
    for i, line in enumerate(lines, start=1):
        parsed = parse_task_line(line, i)
        if parsed:
            tasks.append(parsed)
    return tasks


def get_task(task_id: str) -> TaskRecord:
    tasks = load_tasks()
    for t in tasks:
        if t.task_id == task_id:
            return t
    raise TaskError(f"Task '{task_id}' not found")


def _line_for_task(task: TaskRecord, *, status: str | None = None, checked: bool | None = None) -> str:
    status = status or task.status
    checked = task.checked if checked is None else checked
    mark = "x" if checked else " "
    req = ",".join(task.required_tests)
    evid = ",".join(task.evidence)
    return (
        f"- [{mark}] {task.task_id} | status={status} | title={task.title} | "
        f"required_tests={req} | evidence={evid} | dod={task.dod}"
    )


def update_task(task_id: str, *, status: str | None = None, checked: bool | None = None) -> None:
    path = tasks_file()
    lines = path.read_text(encoding="utf-8").splitlines()

    updated = False
    for i, line in enumerate(lines, start=1):
        t = parse_task_line(line, i)
        if t and t.task_id == task_id:
            lines[i - 1] = _line_for_task(t, status=status, checked=checked)
            updated = True
            break

    if not updated:
        raise TaskError(f"Task '{task_id}' not found")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def start_task(task_id: str) -> TaskRecord:
    task = get_task(task_id)
    if task.status not in {"backlog", "blocked"}:
        raise TaskError(f"Cannot start task from status '{task.status}'")
    update_task(task_id, status="in_progress", checked=False)
    return get_task(task_id)


def _run_pytest_marker(marker: str) -> tuple[bool, str]:
    cmd = ["pytest", "-m", marker]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    out = (proc.stdout + "\n" + proc.stderr).strip()
    return proc.returncode == 0, out


def _load_verify_state() -> dict:
    path = verify_state_file()
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _save_verify_state(state: dict) -> None:
    path = verify_state_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def verify_task(task_id: str) -> dict:
    task = get_task(task_id)
    root = repo_root()

    missing_evidence = [p for p in task.evidence if not (root / p).exists()]
    if missing_evidence:
        raise TaskError(f"Missing evidence files: {', '.join(missing_evidence)}")

    test_results: dict[str, dict] = {}
    for marker in task.required_tests:
        ok, output = _run_pytest_marker(marker)
        test_results[marker] = {"ok": ok, "output_tail": output[-2000:]}
        if not ok:
            raise TaskError(f"Required tests failed for marker '{marker}'")

    state = _load_verify_state()
    stamp = datetime.now(timezone.utc).isoformat()
    state[task_id] = {
        "verified_at": stamp,
        "required_tests": task.required_tests,
        "results": test_results,
    }
    _save_verify_state(state)

    return state[task_id]


def done_task(task_id: str) -> TaskRecord:
    task = get_task(task_id)
    if task.status != "in_progress":
        raise TaskError(f"Task must be in_progress before done, got '{task.status}'")

    state = _load_verify_state()
    task_state = state.get(task_id)
    if not task_state:
        raise TaskError("Task has no successful verify record")

    update_task(task_id, status="done", checked=True)
    return get_task(task_id)
