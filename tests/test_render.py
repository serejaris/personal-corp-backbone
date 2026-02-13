from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from backbone.pipeline import PipelineError, run
from backbone.render import render_lesson_brief


@pytest.mark.unit
def test_render_lesson_brief_creates_markdown(tmp_path: Path) -> None:
    rr = run(profile="lesson_analysis", source="tests/fixtures/lesson_transcript.txt")
    out = tmp_path / "analysis.md"
    rendered = render_lesson_brief(artifact_path=rr.artifact_path, output_path=str(out))

    assert rendered.exists()
    text = rendered.read_text(encoding="utf-8")
    assert "# Lesson Brief" in text
    assert "## Summary" in text
    assert "## Quiz (5-7 questions)" in text
    assert "## Glossary (8-12 terms)" in text
    assert "## Sources" in text


@pytest.mark.integration
def test_cli_render_lesson_brief_success(tmp_path: Path) -> None:
    rr = run(profile="lesson_analysis", source="tests/fixtures/lesson_transcript.txt")
    out = tmp_path / "lesson_analysis.md"

    proc = subprocess.run(
        ["backbone", "render", "lesson-brief", "--artifact", rr.artifact_path, "--output", str(out)],
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["output_path"] == str(out)
    assert out.exists()


@pytest.mark.unit
def test_render_lesson_brief_rejects_wrong_profile(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact.json"
    artifact.write_text(
        json.dumps(
            {
                "profile": "digest_topics",
                "status": "success",
                "result": {"topics": ["x"], "summary": "s", "metrics": {"word_count": 1, "chunk_count": 1}},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    with pytest.raises(PipelineError):
        render_lesson_brief(artifact_path=str(artifact), output_path=str(tmp_path / "x.md"))
