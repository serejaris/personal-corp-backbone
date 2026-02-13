from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import subprocess
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SUPPORTED_PROFILES = {"lesson_analysis", "digest_topics", "mentor_session"}
LESSON_REQUIRED_FIELDS = {
    "summary",
    "detailed_summary",
    "questions_asked",
    "concepts_explained",
    "practical_activities",
    "theory_practice_balance",
    "interactivity",
    "learning_outcomes_stated",
    "lesson_structure",
    "improvement_suggestions",
    "homework",
    "preparation_for_next",
    "next_lesson_focus",
}

_TOKEN_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9-]+")
_SENTENCE_RE = re.compile(r"[.!?]\s+|\n+")
CLAUDE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": sorted(LESSON_REQUIRED_FIELDS),
    "properties": {
        "summary": {"type": "string"},
        "detailed_summary": {"type": ["string", "null"]},
        "questions_asked": {"type": "array", "items": {"type": "string"}},
        "concepts_explained": {"type": "array", "items": {"type": "string"}},
        "practical_activities": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["activity", "duration_estimate", "participation"],
                "properties": {
                    "activity": {"type": "string"},
                    "duration_estimate": {"type": ["string", "null"]},
                    "participation": {"type": ["string", "null"]},
                },
            },
        },
        "theory_practice_balance": {
            "type": "object",
            "additionalProperties": False,
            "required": ["theory_percent", "practice_percent", "assessment"],
            "properties": {
                "theory_percent": {"type": "integer"},
                "practice_percent": {"type": "integer"},
                "assessment": {"type": ["string", "null"]},
            },
        },
        "interactivity": {
            "type": "object",
            "additionalProperties": False,
            "required": ["questions_to_students", "polls_or_checks", "breakouts_or_pair_work"],
            "properties": {
                "questions_to_students": {"type": "integer"},
                "polls_or_checks": {"type": "array", "items": {"type": "string"}},
                "breakouts_or_pair_work": {"type": "boolean"},
            },
        },
        "learning_outcomes_stated": {"type": "boolean"},
        "lesson_structure": {
            "type": "object",
            "additionalProperties": False,
            "required": ["has_opening", "has_closing", "transitions_clear"],
            "properties": {
                "has_opening": {"type": "boolean"},
                "has_closing": {"type": "boolean"},
                "transitions_clear": {"type": "boolean"},
            },
        },
        "improvement_suggestions": {"type": "array", "items": {"type": "string"}},
        "homework": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["task", "description", "deadline"],
                "properties": {
                    "task": {"type": "string"},
                    "description": {"type": ["string", "null"]},
                    "deadline": {"type": ["string", "null"]},
                },
            },
        },
        "preparation_for_next": {"type": "array", "items": {"type": "string"}},
        "next_lesson_focus": {"type": ["string", "null"]},
    },
}


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
    lines = [re.sub(r"\s+", " ", line).strip() for line in raw.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def _chunk_adapter(text: str, chunk_size: int = 1000) -> list[str]:
    if not text:
        return []
    return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]


def _extract_fast(chunks: list[str]) -> dict[str, int]:
    words = sum(len(chunk.split()) for chunk in chunks)
    return {"chunks": len(chunks), "words": words}


def _semantic_dedupe(chunks: list[str]) -> list[str]:
    seen = set()
    out = []
    for chunk in chunks:
        key = hashlib.sha256(chunk.encode("utf-8")).hexdigest()
        if key not in seen:
            seen.add(key)
            out.append(chunk)
    return out


def _sentences(text: str) -> list[str]:
    return [part.strip(" .!?,") for part in _SENTENCE_RE.split(text) if part.strip()]


def _extract_topics(text: str) -> list[str]:
    lower = text.lower()
    topics: list[str] = []
    known = [
        ("микросервис", "Микросервисная архитектура"),
        ("event-driven", "Event-driven подход"),
        ("транскрипт", "Анализ транскриптов"),
        ("чанк", "Чанкирование контента"),
        ("дайджест", "Генерация дайджестов"),
        ("github issue", "Управление задачами через GitHub Issues"),
        ("пайплайн", "Пайплайн обработки"),
        ("тест-гейт", "Тест-гейты качества"),
    ]
    for needle, label in known:
        if needle in lower and label not in topics:
            topics.append(label)

    if len(topics) >= 8:
        return topics[:8]

    blocked = {
        "сегодня",
        "уроке",
        "потом",
        "как",
        "чтобы",
        "всего",
        "через",
        "задачи",
    }
    token_counts: dict[str, int] = {}
    for token in _TOKEN_RE.findall(lower):
        if len(token) < 7 or token in blocked:
            continue
        token_counts[token] = token_counts.get(token, 0) + 1

    for token, _ in sorted(token_counts.items(), key=lambda kv: (-kv[1], kv[0])):
        label = token.capitalize()
        if label not in topics:
            topics.append(label)
        if len(topics) >= 8:
            break
    return topics


def _build_digest_topics(text: str, fast: dict[str, int]) -> dict[str, Any]:
    topics = _extract_topics(text)
    sentences = _sentences(text)
    return {
        "topics": topics[:15],
        "summary": sentences[0] if sentences else text[:200],
        "metrics": {"word_count": fast["words"], "chunk_count": fast["chunks"]},
    }


def _build_mentor_session(text: str, fast: dict[str, int]) -> dict[str, Any]:
    sentences = _sentences(text)
    next_actions = [
        "Сформировать список задач на неделю",
        "Зафиксировать риски и допущения",
        "Подготовить артефакты для ретроспективы",
    ]
    return {
        "summary": ". ".join(sentences[:2]) if sentences else text[:200],
        "next_actions": next_actions,
        "metrics": {"word_count": fast["words"], "chunk_count": fast["chunks"]},
    }


def _claude_command() -> list[str]:
    raw = os.environ.get("BACKBONE_CLAUDE_CMD", "claude")
    cmd = shlex.split(raw.strip()) if raw.strip() else []
    if not cmd:
        raise PipelineError("BACKBONE_CLAUDE_CMD is empty")
    return cmd


def _build_lesson_prompt(transcript: str) -> str:
    return f"""
Ты анализируешь транскрипт урока и должен вернуть ТОЛЬКО JSON по заданной схеме.
Важные правила:
1) Никакого markdown, только валидный JSON-объект.
2) Заполняй все обязательные поля.
3) Не добавляй дополнительные поля.
4) Если данных мало, используй null или короткие списки, но сохрани типы.
5) Для theory_practice_balance: проценты от 0 до 100, сумма ровно 100.
6) Язык ответа: русский (допускаются технические англ. термины из исходного текста).
7) practical_activities и homework должны быть конкретными и привязанными к содержанию транскрипта.

ТРАНСКРИПТ УРОКА:
{transcript}
""".strip()


def _pick_model_name(claude_output: dict[str, Any], configured_model: str) -> str:
    usage = claude_output.get("modelUsage")
    if not isinstance(usage, dict) or not usage:
        return configured_model

    best_name = configured_model
    best_cost = -1.0
    for name, data in usage.items():
        if not isinstance(data, dict):
            continue
        cost = data.get("costUSD")
        if isinstance(cost, (int, float)) and float(cost) > best_cost:
            best_name = str(name)
            best_cost = float(cost)
    return best_name


def _extract_structured_output(claude_output: dict[str, Any]) -> dict[str, Any]:
    if claude_output.get("is_error") is True:
        raise PipelineError("Claude returned is_error=true")

    structured = claude_output.get("structured_output")
    if isinstance(structured, dict):
        return structured

    result_text = claude_output.get("result")
    if isinstance(result_text, str) and result_text.strip():
        try:
            parsed = json.loads(result_text)
        except json.JSONDecodeError as e:
            raise PipelineError(f"Claude result is not valid JSON: {e}") from e
        if isinstance(parsed, dict):
            return parsed

    raise PipelineError("Claude output has no structured JSON payload")


def _generate_lesson_analysis_via_claude(transcript: str) -> tuple[dict[str, Any], dict[str, str]]:
    cmd = _claude_command()
    model = os.environ.get("BACKBONE_CLAUDE_MODEL", "opus")
    effort = os.environ.get("BACKBONE_CLAUDE_EFFORT", "medium")
    timeout_sec = int(os.environ.get("BACKBONE_CLAUDE_TIMEOUT_SEC", "180"))
    retries = int(os.environ.get("BACKBONE_CLAUDE_RETRIES", "2"))

    prompt = _build_lesson_prompt(transcript)
    schema_json = json.dumps(CLAUDE_SCHEMA, ensure_ascii=False)

    last_error = "unknown"
    for attempt in range(1, retries + 2):
        try:
            proc = subprocess.run(
                [
                    *cmd,
                    "-p",
                    "--output-format",
                    "json",
                    "--json-schema",
                    schema_json,
                    "--model",
                    model,
                    "--effort",
                    effort,
                    "--tools",
                    "",
                    "--no-session-persistence",
                    prompt,
                ],
                capture_output=True,
                text=True,
                timeout=timeout_sec,
            )
        except FileNotFoundError as e:
            raise PipelineError(f"Claude command not found: {cmd[0]}") from e
        except subprocess.TimeoutExpired as e:
            last_error = f"timeout after {timeout_sec}s"
            if attempt > retries:
                raise PipelineError(f"Claude call failed: {last_error}") from e
            continue

        if proc.returncode != 0:
            tail = (proc.stderr or proc.stdout or "").strip()[-1500:]
            last_error = f"exit={proc.returncode}; {tail}"
            if attempt > retries:
                raise PipelineError(f"Claude call failed: {last_error}")
            continue

        out = proc.stdout.strip()
        if not out:
            last_error = "empty stdout"
            if attempt > retries:
                raise PipelineError(f"Claude call failed: {last_error}")
            continue

        try:
            claude_output = json.loads(out)
        except json.JSONDecodeError as e:
            last_error = f"invalid json stdout: {e}"
            if attempt > retries:
                raise PipelineError(f"Claude call failed: {last_error}") from e
            continue

        structured = _extract_structured_output(claude_output)
        return structured, {
            "analysis_provider": "claude_code",
            "analysis_model": _pick_model_name(claude_output, model),
        }

    raise PipelineError(f"Claude call failed: {last_error}")


def _expect_type(name: str, value: Any, expected: type | tuple[type, ...]) -> None:
    if not isinstance(value, expected):
        raise PipelineError(f"Schema validation failed for '{name}': wrong type")


def _expect_optional_str(name: str, value: Any) -> None:
    if value is not None and not isinstance(value, str):
        raise PipelineError(f"Schema validation failed for '{name}': must be string or null")


def _validate_string_list(name: str, value: Any) -> None:
    if not isinstance(value, list):
        raise PipelineError(f"Schema validation failed for '{name}': must be list")
    if any((not isinstance(item, str)) or (not item.strip()) for item in value):
        raise PipelineError(f"Schema validation failed for '{name}': list must contain non-empty strings")


def _validate_lesson_contract(result: dict[str, Any]) -> None:
    result_keys = set(result.keys())
    missing = sorted(LESSON_REQUIRED_FIELDS - result_keys)
    extra = sorted(result_keys - LESSON_REQUIRED_FIELDS)
    if missing or extra:
        parts: list[str] = []
        if missing:
            parts.append(f"missing={','.join(missing)}")
        if extra:
            parts.append(f"extra={','.join(extra)}")
        raise PipelineError(f"Schema validation failed for lesson_analysis: {'; '.join(parts)}")

    _expect_type("summary", result["summary"], str)
    _expect_optional_str("detailed_summary", result["detailed_summary"])
    _validate_string_list("questions_asked", result["questions_asked"])
    _validate_string_list("concepts_explained", result["concepts_explained"])

    practical = result["practical_activities"]
    _expect_type("practical_activities", practical, list)
    for idx, item in enumerate(practical):
        _expect_type(f"practical_activities[{idx}]", item, dict)
        if set(item.keys()) != {"activity", "duration_estimate", "participation"}:
            raise PipelineError("Schema validation failed for 'practical_activities': wrong object keys")
        _expect_type(f"practical_activities[{idx}].activity", item["activity"], str)
        _expect_optional_str(f"practical_activities[{idx}].duration_estimate", item["duration_estimate"])
        _expect_optional_str(f"practical_activities[{idx}].participation", item["participation"])

    balance = result["theory_practice_balance"]
    _expect_type("theory_practice_balance", balance, dict)
    if set(balance.keys()) != {"theory_percent", "practice_percent", "assessment"}:
        raise PipelineError("Schema validation failed for 'theory_practice_balance': wrong object keys")
    _expect_type("theory_practice_balance.theory_percent", balance["theory_percent"], int)
    _expect_type("theory_practice_balance.practice_percent", balance["practice_percent"], int)
    _expect_optional_str("theory_practice_balance.assessment", balance["assessment"])
    if not (0 <= balance["theory_percent"] <= 100):
        raise PipelineError("Schema validation failed for 'theory_practice_balance.theory_percent': out of range")
    if not (0 <= balance["practice_percent"] <= 100):
        raise PipelineError("Schema validation failed for 'theory_practice_balance.practice_percent': out of range")
    if balance["theory_percent"] + balance["practice_percent"] != 100:
        raise PipelineError("Schema validation failed for 'theory_practice_balance': percentages must sum to 100")

    interactivity = result["interactivity"]
    _expect_type("interactivity", interactivity, dict)
    if set(interactivity.keys()) != {"questions_to_students", "polls_or_checks", "breakouts_or_pair_work"}:
        raise PipelineError("Schema validation failed for 'interactivity': wrong object keys")
    _expect_type("interactivity.questions_to_students", interactivity["questions_to_students"], int)
    if interactivity["questions_to_students"] < 0:
        raise PipelineError("Schema validation failed for 'interactivity.questions_to_students': must be >= 0")
    _validate_string_list("interactivity.polls_or_checks", interactivity["polls_or_checks"])
    _expect_type("interactivity.breakouts_or_pair_work", interactivity["breakouts_or_pair_work"], bool)

    _expect_type("learning_outcomes_stated", result["learning_outcomes_stated"], bool)

    structure = result["lesson_structure"]
    _expect_type("lesson_structure", structure, dict)
    if set(structure.keys()) != {"has_opening", "has_closing", "transitions_clear"}:
        raise PipelineError("Schema validation failed for 'lesson_structure': wrong object keys")
    _expect_type("lesson_structure.has_opening", structure["has_opening"], bool)
    _expect_type("lesson_structure.has_closing", structure["has_closing"], bool)
    _expect_type("lesson_structure.transitions_clear", structure["transitions_clear"], bool)

    _validate_string_list("improvement_suggestions", result["improvement_suggestions"])

    homework = result["homework"]
    _expect_type("homework", homework, list)
    for idx, item in enumerate(homework):
        _expect_type(f"homework[{idx}]", item, dict)
        if set(item.keys()) != {"task", "description", "deadline"}:
            raise PipelineError("Schema validation failed for 'homework': wrong object keys")
        _expect_type(f"homework[{idx}].task", item["task"], str)
        _expect_optional_str(f"homework[{idx}].description", item["description"])
        _expect_optional_str(f"homework[{idx}].deadline", item["deadline"])

    _validate_string_list("preparation_for_next", result["preparation_for_next"])
    _expect_optional_str("next_lesson_focus", result["next_lesson_focus"])


def _schema_validate(profile: str, result: dict[str, Any]) -> None:
    if profile == "lesson_analysis":
        _validate_lesson_contract(result)
        return

    if profile == "digest_topics":
        required = {"topics", "summary", "metrics"}
    else:
        required = {"summary", "next_actions", "metrics"}

    missing = [k for k in required if k not in result]
    if missing:
        raise PipelineError(f"Schema validation failed, missing: {', '.join(missing)}")


def _generate(profile: str, normalized: str, fast: dict[str, int], deduped: list[str]) -> dict[str, Any]:
    if profile == "digest_topics":
        return _build_digest_topics(normalized, fast)
    if profile == "mentor_session":
        return _build_mentor_session(normalized, fast)
    raise PipelineError(f"Unsupported generation profile '{profile}'")


def run(profile: str, source: str) -> RunResult:
    if profile not in SUPPORTED_PROFILES:
        raise PipelineError(f"Unsupported profile '{profile}'")

    src = Path(source)
    if not src.exists() or src.is_dir():
        raise PipelineError("Source file does not exist or is a directory")

    raw = src.read_text(encoding="utf-8").strip()
    if not raw:
        raise PipelineError("Source file is empty")

    timings_ms: dict[str, int] = {}

    t0 = time.perf_counter()
    normalized = _normalize_input(raw)
    timings_ms["normalize"] = int((time.perf_counter() - t0) * 1000)

    t0 = time.perf_counter()
    chunks = _chunk_adapter(normalized)
    timings_ms["chunk_adapter"] = int((time.perf_counter() - t0) * 1000)

    t0 = time.perf_counter()
    fast = _extract_fast(chunks)
    timings_ms["extract_fast"] = int((time.perf_counter() - t0) * 1000)

    t0 = time.perf_counter()
    deduped = _semantic_dedupe(chunks)
    timings_ms["semantic_dedupe"] = int((time.perf_counter() - t0) * 1000)

    analysis_meta: dict[str, str] = {}
    t0 = time.perf_counter()
    if profile == "lesson_analysis":
        generated, analysis_meta = _generate_lesson_analysis_via_claude(normalized)
    else:
        generated = _generate(profile, normalized, fast, deduped)
        analysis_meta = {
            "analysis_provider": "deterministic",
            "analysis_model": "n/a",
        }
    timings_ms["generate"] = int((time.perf_counter() - t0) * 1000)

    t0 = time.perf_counter()
    _schema_validate(profile, generated)
    timings_ms["schema_validate"] = int((time.perf_counter() - t0) * 1000)

    request_id = str(uuid.uuid4())
    artifact_id = str(uuid.uuid4())

    chunk_count = max(1, fast["chunks"])
    quality = {
        "source_chars": len(normalized),
        "word_count": fast["words"],
        "chunk_count": fast["chunks"],
        "deduped_chunks": len(deduped),
        "dedupe_ratio": round(len(deduped) / chunk_count, 3),
    }

    payload = {
        "artifact_id": artifact_id,
        "request_id": request_id,
        "profile": profile,
        "status": "success",
        "created_at": _now_iso(),
        **analysis_meta,
        "quality": quality,
        "timings_ms": timings_ms,
        "result": generated,
    }

    artifacts_dir = repo_root() / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifacts_dir / f"{artifact_id}.json"
    artifact_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    events_dir = repo_root() / "reports"
    events_dir.mkdir(parents=True, exist_ok=True)
    events_path = events_dir / "events.jsonl"
    event = {
        "ts": _now_iso(),
        "event": "analysis_run_completed",
        "artifact_id": artifact_id,
        "profile": profile,
        "source": str(src),
        **analysis_meta,
        "quality": quality,
    }
    with events_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

    return RunResult(artifact_id=artifact_id, artifact_path=str(artifact_path), request_id=request_id)
