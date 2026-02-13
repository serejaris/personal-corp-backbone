# TASKS

Format (machine-readable):
`- [ ] T001 | status=backlog | title=... | required_tests=unit,integration | evidence=reports/T001.md | dod=...`

- [x] T001 | status=done | title=Bootstrap repository scaffold | required_tests=unit,integration | evidence=reports/T001.md | dod=Core folders and governance files exist and parse correctly
- [x] T002 | status=done | title=Implement task parser and registry loading | required_tests=unit | evidence=reports/T002.md | dod=CLI reads TASKS.md into typed records
- [x] T003 | status=done | title=Implement task start transition | required_tests=unit,integration | evidence=reports/T003.md | dod=Only valid transitions to in_progress are allowed
- [x] T004 | status=done | title=Implement task verify gate | required_tests=unit,integration | evidence=reports/T004.md | dod=Verify enforces required test suites and evidence files
- [x] T005 | status=done | title=Implement task done transition | required_tests=unit,integration | evidence=reports/T005.md | dod=Done requires prior successful verify
- [x] T006 | status=done | title=Implement analysis run skeleton | required_tests=unit,integration | evidence=reports/T006.md | dod=Run pipeline persists artifact and event log
- [x] T007 | status=done | title=Add profile schema validation | required_tests=unit | evidence=reports/T007.md | dod=Invalid profile fails, valid profile passes deterministic checks
- [x] T008 | status=done | title=Add fixture-driven integration tests | required_tests=integration | evidence=reports/T008.md | dod=Fixtures cover happy path and failure paths
- [x] T009 | status=done | title=Wire CI for full automated tests | required_tests=unit,integration | evidence=reports/T009.md | dod=GitHub Actions runs all required tests on PR/push
- [x] T010 | status=done | title=Prepare v0.1 changelog and decisions | required_tests=unit | evidence=reports/T010.md | dod=Changelog and ADR entries reflect delivered behavior
- [x] T011 | status=done | title=Harden lesson_analysis to cohorts contract | required_tests=unit,integration | evidence=reports/T011.md | dod=Lesson profile output matches cohorts LessonParsed shape with strict schema checks
- [x] T012 | status=done | title=Add regression snapshot for lesson_analysis | required_tests=integration | evidence=reports/T012.md | dod=Fixture snapshot detects contract regression for lesson output
- [x] T013 | status=done | title=Expose quality and stage timings in artifacts | required_tests=unit,smoke | evidence=reports/T013.md | dod=Run payload includes quality metrics and per-stage timing fields
