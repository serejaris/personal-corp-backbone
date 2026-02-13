# personal-corp-backbone

Terminal-first operational repository for running a strict plan with test-gated steps.

## What this repo does

- Keeps one source of truth for execution (`PLAN.md`, `TASKS.md`)
- Provides CLI commands to move tasks through status transitions
- Enforces automated-test gates before task completion
- Produces artifacts/events for analysis pipeline runs
- Emits strict `lesson_analysis` payload compatible with cohorts `LessonParsed`
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
```

## Artifact contract

`backbone run` writes `artifacts/<uuid>.json`:

- `profile`, `status`, `created_at`, IDs
- `quality`: source/chunk/dedupe counters
- `timings_ms`: per-stage deterministic runtime measurements
- `result`: profile payload (`lesson_analysis` is validated against strict cohorts-compatible schema)
