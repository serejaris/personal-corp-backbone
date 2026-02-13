from __future__ import annotations

import json
import sys
from pathlib import Path


def _read_snapshot_result() -> dict[str, object]:
    snapshot_path = Path(__file__).resolve().parents[1] / "fixtures" / "lesson_analysis_snapshot.json"
    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    result = payload.get("result")
    if not isinstance(result, dict):
        raise RuntimeError("snapshot fixture must contain object field: result")
    return result


def _parse_model(argv: list[str]) -> str:
    if "--model" in argv:
        idx = argv.index("--model")
        if idx + 1 < len(argv):
            return argv[idx + 1]
    return "test-opus"


def main() -> int:
    model = _parse_model(sys.argv[1:])
    result = _read_snapshot_result()

    response = {
        "is_error": False,
        "result": json.dumps(result, ensure_ascii=False),
        "structured_output": result,
        "modelUsage": {
            model: {
                "inputTokens": 123,
                "outputTokens": 456,
                "cacheReadInputTokens": 0,
                "cacheCreationInputTokens": 0,
                "costUSD": 0.001,
            }
        },
    }
    print(json.dumps(response, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
