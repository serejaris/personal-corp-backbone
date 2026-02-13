from __future__ import annotations

import subprocess

import pytest


@pytest.mark.integration
def test_cli_task_list() -> None:
    proc = subprocess.run(["backbone", "task", "list"], capture_output=True, text=True)
    assert proc.returncode == 0
    assert "T001" in proc.stdout


@pytest.mark.integration
def test_cli_run_success() -> None:
    proc = subprocess.run(
        ["backbone", "run", "--profile", "lesson_analysis", "--source", "tests/fixtures/lesson_transcript.txt"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert "artifact_id" in proc.stdout


@pytest.mark.integration
def test_cli_run_invalid_profile() -> None:
    proc = subprocess.run(
        ["backbone", "run", "--profile", "bad", "--source", "tests/fixtures/lesson_transcript.txt"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 1
    assert "Unsupported profile" in proc.stderr
