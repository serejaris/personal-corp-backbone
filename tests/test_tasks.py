from __future__ import annotations

import json
from pathlib import Path

import pytest

from backbone.tasks import (
    TaskError,
    get_task,
    parse_task_line,
    start_task,
    tasks_file,
    update_task,
    verify_task,
)


@pytest.mark.unit
def test_parse_task_line() -> None:
    line = "- [ ] T001 | status=backlog | title=Demo | required_tests=unit,integration | evidence=reports/T001.md | dod=Done"
    task = parse_task_line(line, 1)
    assert task is not None
    assert task.task_id == "T001"
    assert task.status == "backlog"
    assert task.required_tests == ["unit", "integration"]


@pytest.mark.unit
def test_start_transition_rules() -> None:
    t = get_task("T001")
    update_task("T001", status="backlog", checked=False)
    started = start_task("T001")
    assert started.status == "in_progress"
    assert not started.checked

    update_task("T001", status="done", checked=True)
    with pytest.raises(TaskError):
        start_task("T001")

    # restore
    update_task("T001", status=t.status, checked=t.checked)


@pytest.mark.integration
def test_verify_fails_without_evidence() -> None:
    original = get_task("T004")
    update_task("T004", status="in_progress", checked=False)
    p = Path("reports/T004.md")
    had_file = p.exists()
    previous = p.read_text(encoding="utf-8") if had_file else ""
    if had_file:
        p.unlink()

    with pytest.raises(TaskError):
        verify_task("T004")

    if had_file:
        p.write_text(previous, encoding="utf-8")

    # restore
    update_task("T004", status=original.status, checked=original.checked)


@pytest.mark.integration
def test_verify_and_state_written() -> None:
    original = get_task("T002")
    update_task("T002", status="in_progress", checked=False)
    Path("reports/T002.md").write_text("evidence", encoding="utf-8")

    data = verify_task("T002")
    assert "verified_at" in data
    assert "unit" in data["required_tests"]

    state = json.loads(Path(".backbone/verify_state.json").read_text(encoding="utf-8"))
    assert "T002" in state

    # restore
    update_task("T002", status=original.status, checked=original.checked)
