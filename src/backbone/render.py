from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .pipeline import PipelineError


def _load_artifact(path: Path) -> dict[str, Any]:
    if not path.exists() or path.is_dir():
        raise PipelineError("Artifact file does not exist or is a directory")

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise PipelineError(f"Artifact is not valid JSON: {e}") from e

    if payload.get("profile") != "lesson_analysis":
        raise PipelineError("Artifact profile must be 'lesson_analysis' for lesson brief rendering")
    if payload.get("status") != "success":
        raise PipelineError("Artifact status must be 'success'")
    if "result" not in payload or not isinstance(payload["result"], dict):
        raise PipelineError("Artifact has no valid result block")

    return payload


def _parse_duration_minutes(value: str | None) -> int | None:
    if not value:
        return None
    m = re.match(r"^\s*(\d+)\s*m\s*$", value.lower())
    if not m:
        return None
    return int(m.group(1))


def _mmss(minutes_total: int) -> str:
    h = minutes_total // 60
    m = minutes_total % 60
    if h:
        return f"{h:02d}:{m:02d}:00"
    return f"{m:02d}:00"


def _lesson_timeline(practical_activities: list[dict[str, Any]]) -> list[str]:
    if not practical_activities:
        return ["00:00 Введение и постановка задачи", "10:00 Практический блок", "30:00 Рефлексия и выводы"]

    timeline: list[str] = []
    cursor_min = 0
    for item in practical_activities[:8]:
        activity = str(item.get("activity", "")).strip() or "Практика"
        timeline.append(f"{_mmss(cursor_min)} {activity}")
        duration = _parse_duration_minutes(item.get("duration_estimate"))
        cursor_min += duration if duration is not None else 10
    return timeline


def _glossary_definition(term: str) -> str:
    known = {
        "Микросервисная архитектура": "Подход, где система делится на независимые сервисы с отдельными зонами ответственности.",
        "Event-driven подход": "Архитектура, в которой компоненты обмениваются событиями вместо жёстких синхронных вызовов.",
        "Анализ транскриптов": "Извлечение структуры, смыслов и actionable-выводов из текстовой расшифровки занятия.",
        "Чанкирование контента": "Разбиение длинного текста на смысловые блоки для стабильной обработки и контроля качества.",
        "Генерация дайджестов": "Сжатие длинного материала в краткие ключевые тезисы для быстрого потребления.",
        "Управление задачами через GitHub Issues": "Фиксация задач и прогресса в issue-трекере с прозрачным статусом и ответственностью.",
        "Пайплайн обработки": "Последовательность стадий от входных данных до финального артефакта с проверками на каждом шаге.",
        "Тест-гейты качества": "Обязательные автоматические проверки, без прохождения которых изменение не считается завершённым.",
    }
    return known.get(
        term,
        "Термин из урока: зафиксируй локальное определение под свой контекст и инструменты.",
    )


def _build_quiz(concepts: list[str], suggestions: list[str]) -> list[tuple[str, str]]:
    quiz: list[tuple[str, str]] = []
    for concept in concepts[:4]:
        quiz.append(
            (
                f"Что означает '{concept}' в контексте текущего урока?",
                f"'{concept}' — ключевая тема занятия. Сформулируй определение через практический пример из урока.",
            )
        )

    for suggestion in suggestions[:3]:
        quiz.append(
            (
                "Какое улучшение стоит внедрить в следующем занятии и почему?",
                f"Одно из конкретных улучшений: {suggestion}",
            )
        )
        if len(quiz) >= 7:
            break

    if len(quiz) < 5:
        quiz.extend(
            [
                ("Какая часть урока дала наибольшую практическую ценность?", "Та, где участники применяли подходы к реальному кейсу."),
                ("Что стоит подготовить перед следующим занятием?", "Артефакты, входные данные и список контрольных вопросов."),
            ]
        )
    return quiz[:7]


def render_lesson_brief(artifact_path: str, output_path: str) -> Path:
    artifact = Path(artifact_path)
    payload = _load_artifact(artifact)
    result = payload["result"]

    summary = str(result.get("summary", "")).strip()
    detailed_summary = str(result.get("detailed_summary", "")).strip()
    concepts: list[str] = [str(x).strip() for x in result.get("concepts_explained", []) if str(x).strip()]
    questions: list[str] = [str(x).strip() for x in result.get("questions_asked", []) if str(x).strip()]
    suggestions: list[str] = [str(x).strip() for x in result.get("improvement_suggestions", []) if str(x).strip()]
    preparation: list[str] = [str(x).strip() for x in result.get("preparation_for_next", []) if str(x).strip()]
    next_focus = result.get("next_lesson_focus")
    practical_activities = result.get("practical_activities", [])
    homework = result.get("homework", [])
    quality = payload.get("quality", {})

    if not isinstance(practical_activities, list):
        practical_activities = []
    if not isinstance(homework, list):
        homework = []

    timeline = _lesson_timeline(practical_activities)
    quiz = _build_quiz(concepts, suggestions)
    glossary_terms = concepts[:10] if concepts else ["Ключевая тема урока"]

    lines: list[str] = []
    lines.append("# Lesson Brief")
    lines.append("")
    lines.append("## Meta")
    lines.append(f"- Artifact: `{artifact}`")
    lines.append(f"- Created at: `{payload.get('created_at', 'unknown')}`")
    lines.append(f"- Word count: `{quality.get('word_count', 'unknown')}`")
    lines.append(f"- Chunk count: `{quality.get('chunk_count', 'unknown')}`")
    lines.append("")
    lines.append("## Summary")
    lines.append(summary or "N/A")
    lines.append("")
    lines.append("## Detailed Summary")
    lines.append(detailed_summary or summary or "N/A")
    lines.append("")
    lines.append("## Concepts")
    if concepts:
        lines.extend([f"- {item}" for item in concepts])
    else:
        lines.append("- N/A")
    lines.append("")
    lines.append("## Lesson Timeline (for timestamps panel)")
    lines.extend([f"- {item}" for item in timeline])
    lines.append("")
    lines.append("## Practical Activities")
    if practical_activities:
        for item in practical_activities:
            activity = str(item.get("activity", "")).strip() or "Практика"
            duration = str(item.get("duration_estimate", "")).strip() or "n/a"
            participation = str(item.get("participation", "")).strip() or "n/a"
            lines.append(f"- {activity} (`duration={duration}`, `participation={participation}`)")
    else:
        lines.append("- N/A")
    lines.append("")
    lines.append("## Questions Raised")
    if questions:
        lines.extend([f"- {item}" for item in questions])
    else:
        lines.append("- N/A")
    lines.append("")
    lines.append("## Homework")
    if homework:
        for item in homework:
            task = str(item.get("task", "")).strip() or "Task"
            description = str(item.get("description", "")).strip()
            deadline = item.get("deadline")
            suffix = []
            if description:
                suffix.append(f"description={description}")
            if deadline:
                suffix.append(f"deadline={deadline}")
            tail = f" ({'; '.join(suffix)})" if suffix else ""
            lines.append(f"- {task}{tail}")
    else:
        lines.append("- N/A")
    lines.append("")
    lines.append("## Improvement Suggestions")
    if suggestions:
        lines.extend([f"- {item}" for item in suggestions])
    else:
        lines.append("- N/A")
    lines.append("")
    lines.append("## Preparation For Next Lesson")
    if preparation:
        lines.extend([f"- {item}" for item in preparation])
    else:
        lines.append("- N/A")
    lines.append("")
    lines.append("## Next Lesson Focus")
    lines.append(str(next_focus).strip() if next_focus else "N/A")
    lines.append("")
    lines.append("## Quiz (5-7 questions)")
    for idx, (question, answer) in enumerate(quiz, start=1):
        lines.append(f"{idx}. Q: {question}")
        lines.append(f"   A: {answer}")
    lines.append("")
    lines.append("## Glossary (8-12 terms)")
    for term in glossary_terms:
        lines.append(f"- **{term}**: {_glossary_definition(term)}")
    lines.append("")
    lines.append("## Sources")
    lines.append(f"- Artifact JSON: `{artifact}`")
    lines.append("- Add external links that were actually used in lesson preparation (no broken URLs).")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return output
