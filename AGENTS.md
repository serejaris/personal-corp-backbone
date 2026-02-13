# AGENTS.md

Canonical agent instructions for this repository.

## Priority

- This file is the primary source of truth for Codex.
- If other agent-specific files exist, they must not contradict this file.

## Repository goal

Terminal-first analysis backbone with strict task gating and deterministic validation.

## Core workflow

`ai-whisper -> transcript -> backbone run --profile lesson_analysis -> artifact JSON -> compact report`

## Prerequisites

```bash
cd /Users/ris/Documents/GitHub/personal-corp-backbone
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

## Mandatory commands

1. Analyze transcript:
   - `backbone run --profile lesson_analysis --source /ABS/PATH/transcript.txt`
2. Validate code changes:
   - `pytest -m unit`
   - `pytest -m integration`
   - `pytest -m smoke`
3. Task lifecycle (when task files are touched):
   - `backbone task start <TASK_ID>`
   - `backbone task verify <TASK_ID>`
   - `backbone task done <TASK_ID>`

## ai-whisper integration

- Preferred source: `ai-whisper/.../pipeline/transcript.json`.
- Convert segments to txt before backbone run.
- For recordings with intro/noise at start, filter by timestamp (default `start_at=7.0`).

## Artifact contract

Each run must produce `artifacts/<uuid>.json` with:
- top-level: `profile`, `status`, ids, `created_at`
- top-level: `quality`
- top-level: `timings_ms`
- `result` with strict `lesson_analysis` contract

## Agent response contract

After analysis, include:
1. `artifact_path`
2. `result.summary`
3. 3-8 key concepts from `result.concepts_explained`
4. `result.improvement_suggestions`
5. `result.homework`
6. `quality.word_count` and `quality.chunk_count`
