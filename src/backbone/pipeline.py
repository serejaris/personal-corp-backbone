from __future__ import annotations

import hashlib
import json
import re
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
_QUESTION_RE = re.compile(r"([^?]+\?)")


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


def _build_questions(text: str, topics: list[str]) -> list[str]:
    explicit = [m.strip() for m in _QUESTION_RE.findall(text.replace("\n", " ")) if m.strip()]
    if explicit:
        return explicit[:5]

    questions: list[str] = []
    if topics:
        questions.append(f"Как применить {topics[0].lower()} в текущем проекте?")
    if len(topics) > 1:
        questions.append(f"Какие риски при внедрении {topics[1].lower()}?")
    if not questions:
        questions.append("Какие шаги нужны для улучшения следующего занятия?")
    return questions


def _build_practical_activities(text: str) -> list[dict[str, str | None]]:
    lower = text.lower()
    activities: list[dict[str, str | None]] = []
    if "чанк" in lower:
        activities.append(
            {
                "activity": "Практика по разбиению транскрипта на чанки",
                "duration_estimate": "20m",
                "participation": "все",
            }
        )
    if "ключев" in lower and "тем" in lower:
        activities.append(
            {
                "activity": "Выделение ключевых тем для дайджеста",
                "duration_estimate": "15m",
                "participation": "все",
            }
        )
    if "github" in lower and "issue" in lower:
        activities.append(
            {
                "activity": "Фиксация задач в GitHub Issues",
                "duration_estimate": "10m",
                "participation": "часть",
            }
        )
    if not activities:
        activities.append(
            {
                "activity": "Разбор кейса урока и декомпозиция задач",
                "duration_estimate": "15m",
                "participation": "все",
            }
        )
    return activities


def _build_theory_practice_balance(text: str) -> dict[str, int | str]:
    lower = text.lower()
    theory_signals = sum(lower.count(w) for w in ("обсудили", "разобрали", "архитектур", "подход"))
    practice_signals = sum(lower.count(w) for w in ("сделали", "практик", "разбиени", "выделили", "постро"))
    total = theory_signals + practice_signals

    if total == 0:
        theory = 60
    else:
        theory = round((theory_signals / total) * 100)

    theory = max(20, min(80, theory))
    practice = 100 - theory

    if abs(theory - practice) <= 20:
        assessment = "хорошо"
    elif theory > practice:
        assessment = "много теории"
    else:
        assessment = "много практики"

    return {
        "theory_percent": theory,
        "practice_percent": practice,
        "assessment": assessment,
    }


def _build_interactivity(text: str) -> dict[str, Any]:
    lower = text.lower()
    questions_to_students = text.count("?") + lower.count("обсудили")
    polls_or_checks: list[str] = []
    if "ключев" in lower and "тем" in lower:
        polls_or_checks.append("Проверка понимания по ключевым темам")
    if "тест" in lower:
        polls_or_checks.append("Мини-чек по тест-гейтам")
    breakouts = any(k in lower for k in ("в парах", "в групп", "breakout"))

    return {
        "questions_to_students": questions_to_students,
        "polls_or_checks": polls_or_checks,
        "breakouts_or_pair_work": breakouts,
    }


def _build_lesson_structure(text: str) -> dict[str, bool]:
    lower = text.lower()
    return {
        "has_opening": lower.startswith("сегодня"),
        "has_closing": any(w in lower for w in ("потом", "в конце", "итог", "следующ")),
        "transitions_clear": any(w in lower for w in ("потом", "затем", "далее")),
    }


def _build_improvement_suggestions(
    balance: dict[str, int | str], interactivity: dict[str, Any], breakouts: bool
) -> list[str]:
    suggestions: list[str] = []
    if int(balance["practice_percent"]) < 45:
        suggestions.append("Добавить больше практики в середину занятия")
    if interactivity["questions_to_students"] < 2:
        suggestions.append("Добавить контрольные вопросы после каждого смыслового блока")
    if not breakouts:
        suggestions.append("Вставить работу в парах на 10 минут для закрепления")
    if not suggestions:
        suggestions.append("Сохранить текущий темп, добавить финальную рефлексию")
    return suggestions


def _build_homework(text: str, topics: list[str]) -> list[dict[str, str | None]]:
    lower = text.lower()
    items: list[dict[str, str | None]] = []
    if "github" in lower and "issue" in lower:
        items.append(
            {
                "task": "Описать задачи в GitHub Issues",
                "description": "Сформулировать 3 issues для следующего шага пайплайна",
                "deadline": None,
            }
        )
    if "пайплайн" in lower:
        items.append(
            {
                "task": "Собрать минимальный пайплайн с тест-гейтами",
                "description": "Проверить прохождение unit/integration/smoke",
                "deadline": None,
            }
        )
    if not items:
        topic = topics[0] if topics else "урока"
        items.append(
            {
                "task": "Подготовить мини-резюме урока",
                "description": f"Описать как применить тему '{topic}' на практике",
                "deadline": None,
            }
        )
    return items


def _build_lesson_analysis(text: str, fast: dict[str, int], deduped: list[str]) -> dict[str, Any]:
    sentences = _sentences(text)
    topics = _extract_topics(text)
    questions = _build_questions(text, topics)
    practical_activities = _build_practical_activities(text)
    balance = _build_theory_practice_balance(text)
    interactivity = _build_interactivity(text)
    structure = _build_lesson_structure(text)
    homework = _build_homework(text, topics)
    suggestions = _build_improvement_suggestions(balance, interactivity, interactivity["breakouts_or_pair_work"])

    summary = sentences[0] if sentences else text[:240]
    detailed_summary = ". ".join(sentences[:3]) if sentences else text[:500]

    return {
        "summary": summary,
        "detailed_summary": detailed_summary or None,
        "questions_asked": questions,
        "concepts_explained": topics,
        "practical_activities": practical_activities,
        "theory_practice_balance": balance,
        "interactivity": interactivity,
        "learning_outcomes_stated": len(topics) >= 2 and fast["words"] >= 10,
        "lesson_structure": structure,
        "improvement_suggestions": suggestions,
        "homework": homework,
        "preparation_for_next": [
            "Собрать обратную связь от участников по сложности материала",
            "Подготовить данные и артефакты для следующего занятия",
        ],
        "next_lesson_focus": topics[0] if topics else "Развитие структуры занятия",
    }


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
    if profile == "lesson_analysis":
        return _build_lesson_analysis(normalized, fast, deduped)
    if profile == "digest_topics":
        return _build_digest_topics(normalized, fast)
    return _build_mentor_session(normalized, fast)


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

    t0 = time.perf_counter()
    generated = _generate(profile, normalized, fast, deduped)
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
        "quality": quality,
    }
    with events_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

    return RunResult(artifact_id=artifact_id, artifact_path=str(artifact_path), request_id=request_id)
