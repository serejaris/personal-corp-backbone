# DECISIONS

## ADR-001: Tracking format
- Decision: Keep execution truth in `PLAN.md` + machine-readable `TASKS.md`
- Why: Works in terminal, diff-friendly, no external dependency

## ADR-002: Test gate strictness
- Decision: Use full automated tests as a hard gate for task closure
- Why: Prevent silent regressions in iterative agent-driven delivery

## ADR-003: First integration path
- Decision: Prioritize `lesson_analysis` path (`ai-whisper -> cohorts`) before mentor
- Why: Reflects current real usage frequency and business value

## ADR-004: Contract strictness for lesson output
- Decision: Validate `lesson_analysis` output against strict key/type contract compatible with cohorts `LessonParsed`
- Why: Prevent drift between local backbone artifacts and downstream cohorts consumer schema
