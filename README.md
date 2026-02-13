# personal-corp-backbone

Terminal-first operational repository for running strict task execution and LLM-first transcript analysis.

## What this repo does

- Keeps one source of truth for execution (`PLAN.md`, `TASKS.md`)
- Provides CLI commands to move tasks through status transitions
- Enforces automated-test gates before task completion
- Produces artifacts/events for analysis pipeline runs
- Uses Claude CLI for `lesson_analysis` and emits strict payload compatible with cohorts `LessonParsed`
- Stores `quality` and `timings_ms` for every run artifact

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest
backbone task list
```

## CLI

```bash
backbone task list
backbone task start T001
backbone task verify T001
backbone task done T001
backbone run --profile lesson_analysis --source tests/fixtures/lesson_transcript.txt
backbone render lesson-brief --artifact artifacts/<artifact>.json --output /tmp/analysis.md
```

## LLM settings (`lesson_analysis`)

`lesson_analysis` always calls Claude CLI with JSON schema output.

- `BACKBONE_CLAUDE_CMD` (default: `claude`)
- `BACKBONE_CLAUDE_MODEL` (default: `opus`)
- `BACKBONE_CLAUDE_EFFORT` (default: `medium`)
- `BACKBONE_CLAUDE_TIMEOUT_SEC` (default: `180`)
- `BACKBONE_CLAUDE_RETRIES` (default: `2`)

Example:

```bash
export BACKBONE_CLAUDE_CMD="claude"
export BACKBONE_CLAUDE_MODEL="opus"
backbone run --profile lesson_analysis --source /tmp/transcript.txt
```

## Artifact contract

`backbone run` writes `artifacts/<uuid>.json`:

- `profile`, `status`, `created_at`, IDs
- `quality`: source/chunk/dedupe counters
- `timings_ms`: per-stage deterministic runtime measurements
- `analysis_provider`, `analysis_model`: LLM provider/model metadata for the run
- `result`: profile payload (`lesson_analysis` is validated against strict cohorts-compatible schema)

## Lesson Brief Rendering

Convert a `lesson_analysis` artifact to reusable `analysis.md` for downstream HTML lesson skills:

```bash
OUT=$(backbone run --profile lesson_analysis --source /tmp/transcript.txt)
ART=$(echo "$OUT" | jq -r '.artifact_path')
backbone render lesson-brief --artifact "$ART" --output /tmp/analysis.md
```

## Testing

Tests stub Claude calls via `tests/fixtures/fake_claude_cli.py`, so they are deterministic and do not use networked LLM calls.
