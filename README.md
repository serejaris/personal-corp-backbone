# personal-corp-backbone

Terminal-first operational repository for running a strict plan with test-gated steps.

## What this repo does

- Keeps one source of truth for execution (`PLAN.md`, `TASKS.md`)
- Provides CLI commands to move tasks through status transitions
- Enforces automated-test gates before task completion
- Produces artifacts/events for analysis pipeline runs

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
