# PLAN

## Mission
Build a local-first analysis backbone with strict task tracking and mandatory automated tests for every completed step.

## Principles
1. One source of truth: `PLAN.md` + `TASKS.md`
2. No task closure without automated test pass
3. Every transition produces evidence
4. Start from real usage path: `ai-whisper -> cohorts -> tg-digest-opus`

## Phases

## M0 Bootstrap
- Repo scaffold and governance docs
- CI pipeline with mandatory tests
- Task lifecycle CLI skeleton

## M1 Planning Engine
- Machine-readable task registry in `TASKS.md`
- Transition rules (`backlog/in_progress/blocked/done`)
- Verification state and evidence log

## M2 Analysis Backbone Skeleton
- `backbone run --profile --source`
- Deterministic stage pipeline with artifact persistence
- Basic profile-level schema validation

## M3 First Real Integration
- `lesson_analysis` profile hardened for cohorts
- Fixture-based regression harness
- Quality metrics in reports

## Exit Criteria for v0.1
- All tasks marked done have passing `backbone task verify`
- CI green on default branch
- At least one successful `lesson_analysis` run artifact generated
