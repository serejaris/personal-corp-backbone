#!/usr/bin/env bash
set -euo pipefail

# Minimal doc check: required docs exist and are non-empty
for f in PLAN.md TASKS.md TEST_POLICY.md DECISIONS.md CHANGELOG.md README.md; do
  test -s "$f"
done

echo "docs-check: ok"
