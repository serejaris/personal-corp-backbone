from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


SUPPORTED_PROFILES = {"lesson_analysis", "digest_topics", "mentor_session"}


class PipelineError(RuntimeError):
    pass


@dataclass(slots=True)
class RunResult:
    artifact_id: str
    artifact_path: str
    request_id: str


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_input(raw: str) -> str:
    return "\n".join(line.strip() for line in raw.splitlines()).strip()


def _chunk_adapter(text: str, chunk_size: int = 1000) -> list[str]:
    if not text:
        return []
    return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]


def _extract_fast(chunks: list[str]) -> dict:
    words = sum(len(c.split()) for c in chunks)
    return {"chunks": len(chunks), "words": words}


def _semantic_dedupe(chunks: list[str]) -> list[str]:
    seen = set()
    out = []
    for c in chunks:
        key = hashlib.sha256(c.encode("utf-8")).hexdigest()
        if key not in seen:
            seen.add(key)
            out.append(c)
    return out


def _generate_quality(profile: str, normalized: str, fast: dict, deduped: list[str]) -> dict:
    if profile == "lesson_analysis":
        return {
            "summary": normalized[:240],
            "topics": sorted({w.lower().strip(".,:;!?()[]{}\"'") for w in normalized.split() if len(w) > 5})[:10],
            "metrics": {"word_count": fast["words"], "chunk_count": fast["chunks"], "deduped_chunks": len(deduped)},
        }
    if profile == "digest_topics":
        return {
            "topics": sorted({w.lower().strip(".,:;!?()[]{}\"'") for w in normalized.split() if len(w) > 6})[:15],
            "metrics": {"word_count": fast["words"], "chunk_count": fast["chunks"]},
        }
    return {
        "summary": normalized[:200],
        "metrics": {"word_count": fast["words"], "chunk_count": fast["chunks"]},
    }


def _schema_validate(profile: str, result: dict) -> None:
    if profile == "lesson_analysis":
        required = {"summary", "topics", "metrics"}
    elif profile == "digest_topics":
        required = {"topics", "metrics"}
    else:
        required = {"summary", "metrics"}

    missing = [k for k in required if k not in result]
    if missing:
        raise PipelineError(f"Schema validation failed, missing: {', '.join(missing)}")


def run(profile: str, source: str) -> RunResult:
    if profile not in SUPPORTED_PROFILES:
        raise PipelineError(f"Unsupported profile '{profile}'")

    src = Path(source)
    if not src.exists() or src.is_dir():
        raise PipelineError("Source file does not exist or is a directory")

    raw = src.read_text(encoding="utf-8").strip()
    if not raw:
        raise PipelineError("Source file is empty")

    normalized = _normalize_input(raw)
    chunks = _chunk_adapter(normalized)
    fast = _extract_fast(chunks)
    deduped = _semantic_dedupe(chunks)
    generated = _generate_quality(profile, normalized, fast, deduped)
    _schema_validate(profile, generated)

    request_id = str(uuid.uuid4())
    artifact_id = str(uuid.uuid4())

    payload = {
        "artifact_id": artifact_id,
        "request_id": request_id,
        "profile": profile,
        "status": "success",
        "created_at": _now_iso(),
        "result": generated,
    }

    artifacts_dir = repo_root() / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifacts_dir / f"{artifact_id}.json"
    artifact_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    events_dir = repo_root() / "reports"
    events_dir.mkdir(parents=True, exist_ok=True)
    events_path = events_dir / "events.jsonl"
    events_path.write_text(
        events_path.read_text(encoding="utf-8") + json.dumps({
            "ts": _now_iso(),
            "event": "analysis_run_completed",
            "artifact_id": artifact_id,
            "profile": profile,
            "source": str(src),
        }, ensure_ascii=False) + "\n"
        if events_path.exists()
        else json.dumps({
            "ts": _now_iso(),
            "event": "analysis_run_completed",
            "artifact_id": artifact_id,
            "profile": profile,
            "source": str(src),
        }, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return RunResult(artifact_id=artifact_id, artifact_path=str(artifact_path), request_id=request_id)
