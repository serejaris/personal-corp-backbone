# TEST_POLICY

## Mandatory rule
A task can be marked `done` only if `backbone task verify <TASK_ID>` succeeds.

## Required test suites
- `unit`: `pytest -m unit`
- `integration`: `pytest -m integration`
- `smoke`: `pytest -m smoke`

`required_tests` in `TASKS.md` defines the exact suites for each task.

## Evidence requirements
Each task references an `evidence` file path. `verify` requires this file to exist.

## CI policy
CI must run on each push and pull request. Failing tests block merge.

## Local parity
Before marking done, local `verify` must pass even if CI already passed.
