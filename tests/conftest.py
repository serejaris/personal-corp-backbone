from __future__ import annotations

import os
import shlex
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = str(REPO_ROOT / "src")
FAKE_CLAUDE = REPO_ROOT / "tests" / "fixtures" / "fake_claude_cli.py"


@pytest.fixture(autouse=True)
def _configure_backbone_test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    cmd = f"{shlex.quote(sys.executable)} {shlex.quote(str(FAKE_CLAUDE))}"
    monkeypatch.setenv("BACKBONE_CLAUDE_CMD", cmd)
    monkeypatch.setenv("BACKBONE_CLAUDE_MODEL", "test-opus")
    monkeypatch.setenv("BACKBONE_CLAUDE_EFFORT", "medium")
    monkeypatch.setenv("BACKBONE_CLAUDE_TIMEOUT_SEC", "5")
    monkeypatch.setenv("BACKBONE_CLAUDE_RETRIES", "0")


@pytest.fixture
def cli_cmd() -> list[str]:
    return [sys.executable, "-m", "backbone.cli"]


@pytest.fixture
def cli_env() -> dict[str, str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = SRC_PATH if not existing else f"{SRC_PATH}:{existing}"
    return env
