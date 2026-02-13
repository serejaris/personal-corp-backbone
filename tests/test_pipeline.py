from __future__ import annotations

import json
from pathlib import Path

import pytest

from backbone.pipeline import PipelineError, run


@pytest.mark.unit
def test_run_invalid_profile() -> None:
    with pytest.raises(PipelineError):
        run(profile="unknown", source="tests/fixtures/lesson_transcript.txt")


@pytest.mark.unit
def test_run_empty_source() -> None:
    with pytest.raises(PipelineError):
        run(profile="lesson_analysis", source="tests/fixtures/empty.txt")


@pytest.mark.integration
def test_run_valid_fixture() -> None:
    result = run(profile="lesson_analysis", source="tests/fixtures/lesson_transcript.txt")
    p = Path(result.artifact_path)
    assert p.exists()

    payload = json.loads(p.read_text(encoding="utf-8"))
    assert payload["status"] == "success"
    assert payload["profile"] == "lesson_analysis"
    assert "summary" in payload["result"]
    assert "topics" in payload["result"]


@pytest.mark.smoke
def test_run_digest_profile_smoke() -> None:
    result = run(profile="digest_topics", source="tests/fixtures/lesson_transcript.txt")
    payload = json.loads(Path(result.artifact_path).read_text(encoding="utf-8"))
    assert "topics" in payload["result"]
