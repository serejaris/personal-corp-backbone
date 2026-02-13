from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

TaskStatus = Literal["backlog", "in_progress", "blocked", "done"]


@dataclass(slots=True)
class TaskRecord:
    task_id: str
    checked: bool
    status: TaskStatus
    title: str
    required_tests: list[str]
    evidence: list[str]
    dod: str
    line_no: int
    raw_line: str
