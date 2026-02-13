from __future__ import annotations

import json
from pathlib import Path

import pytest

from backbone.pipeline import PipelineError, run

LESSON_RESULT_KEYS = {
    "summary",
    "detailed_summary",
    "questions_asked",
    "concepts_explained",
    "practical_activities",
    "theory_practice_balance",
    "interactivity",
    "learning_outcomes_stated",
    "lesson_structure",
    "improvement_suggestions",
    "homework",
    "preparation_for_next",
    "next_lesson_focus",
}

TIMING_KEYS = {
    "normalize",
    "chunk_adapter",
    "extract_fast",
    "semantic_dedupe",
    "generate",
    "schema_validate",
}


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
    assert payload["analysis_provider"] == "claude_code"
    assert payload["analysis_model"] == "test-opus"
    assert set(payload["result"].keys()) == LESSON_RESULT_KEYS
    assert payload["result"]["summary"]
    assert payload["result"]["theory_practice_balance"]["theory_percent"] >= 0
    assert payload["result"]["theory_practice_balance"]["practice_percent"] >= 0
    assert payload["result"]["theory_practice_balance"]["theory_percent"] + payload["result"]["theory_practice_balance"]["practice_percent"] == 100
    assert set(payload["timings_ms"].keys()) == TIMING_KEYS
    assert payload["quality"]["word_count"] > 0
    assert payload["quality"]["chunk_count"] >= 1


@pytest.mark.integration
def test_lesson_analysis_snapshot_regression() -> None:
    result = run(profile="lesson_analysis", source="tests/fixtures/lesson_transcript.txt")
    payload = json.loads(Path(result.artifact_path).read_text(encoding="utf-8"))
    snapshot = json.loads(Path("tests/fixtures/lesson_analysis_snapshot.json").read_text(encoding="utf-8"))

    assert payload["result"] == snapshot["result"]
    assert payload["quality"] == snapshot["quality"]


@pytest.mark.smoke
def test_run_digest_profile_smoke() -> None:
    result = run(profile="digest_topics", source="tests/fixtures/lesson_transcript.txt")
    payload = json.loads(Path(result.artifact_path).read_text(encoding="utf-8"))
    assert "topics" in payload["result"]
    assert "summary" in payload["result"]
    assert payload["analysis_provider"] == "deterministic"
    assert payload["analysis_model"] == "n/a"
    assert "quality" in payload
