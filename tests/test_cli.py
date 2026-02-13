from __future__ import annotations

import subprocess
from typing import Sequence

import pytest


@pytest.mark.integration
def test_cli_task_list(cli_cmd: Sequence[str], cli_env: dict[str, str]) -> None:
    proc = subprocess.run([*cli_cmd, "task", "list"], capture_output=True, text=True, env=cli_env)
    assert proc.returncode == 0
    assert "T001" in proc.stdout


@pytest.mark.integration
def test_cli_run_success(cli_cmd: Sequence[str], cli_env: dict[str, str]) -> None:
    proc = subprocess.run(
        [*cli_cmd, "run", "--profile", "lesson_analysis", "--source", "tests/fixtures/lesson_transcript.txt"],
        capture_output=True,
        text=True,
        env=cli_env,
    )
    assert proc.returncode == 0
    assert "artifact_id" in proc.stdout


@pytest.mark.integration
def test_cli_run_invalid_profile(cli_cmd: Sequence[str], cli_env: dict[str, str]) -> None:
    proc = subprocess.run(
        [*cli_cmd, "run", "--profile", "bad", "--source", "tests/fixtures/lesson_transcript.txt"],
        capture_output=True,
        text=True,
        env=cli_env,
    )
    assert proc.returncode == 1
    assert "Unsupported profile" in proc.stderr
