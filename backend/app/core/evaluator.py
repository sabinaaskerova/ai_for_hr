"""Логика оценки целей: SMART + тип + стратегическая связка (два отдельных LLM-вызова)."""
import logging
from typing import Optional

from app.config import settings
from app.core import prompts
from app.core.llm_client import call_llm_json
from app.core.schemas import (
    EvaluateRequest,
    SmartCriterionResult,
    SmartEvaluationResult,
    SmartScores,
    StrategicLinkResult,
)

log = logging.getLogger(__name__)


def _normalize(raw_score: int) -> float:
    """Нормализация LLM-оценки 1-5 → 0.0-1.0."""
    return round((max(1, min(5, raw_score)) - 1) / 4, 3)


async def evaluate_smart(request: EvaluateRequest, rag_context: str = "") -> SmartEvaluationResult:
    """
    Вызов 1: SMART оценка + классификация типа цели.
    LLM возвращает 1-5 (для качества CoT), нормализуем в 0.0-1.0.
    temperature=0 для детерминизма.
    """
    user_msg = prompts.SMART_EVALUATION_USER.format(
        goal_text=request.goal_text,
        position=request.position,
        department=request.department,
        quarter=request.quarter or "текущий квартал",
    )

    messages = [{"role": "user", "content": user_msg}]

    data = await call_llm_json(
        messages=messages,
        temperature=settings.llm_temperature_eval,
        max_tokens=3000,
        system=prompts.SMART_EVALUATION_SYSTEM,
    )

    def parse_criterion(key: str) -> SmartCriterionResult:
        c = data.get(key, {})
        raw = int(c.get("score", 3))
        return SmartCriterionResult(
            score=_normalize(raw),
            reasoning=c.get("reasoning", ""),
            recommendation=c.get("recommendation", ""),
        )

    s = parse_criterion("S")
    m = parse_criterion("M")
    a = parse_criterion("A")
    r = parse_criterion("R")
    t = parse_criterion("T")

    computed_index = round((s.score + m.score + a.score + r.score + t.score) / 5, 3)

    return SmartEvaluationResult(
        S=s, M=m, A=a, R=r, T=t,
        smart_index=computed_index,
        goal_type=data.get("goal_type", "output-based"),
        goal_type_reasoning=data.get("goal_type_reasoning", ""),
        reformulation_suggested=data.get("reformulation_suggested", computed_index < 0.625),
        reformulation_hint=data.get("reformulation_hint"),
    )


def build_smart_scores(smart: SmartEvaluationResult) -> SmartScores:
    """Строим плоскую ТЗ-модель из детального SmartEvaluationResult."""
    return SmartScores(
        specific=smart.S.score,
        measurable=smart.M.score,
        achievable=smart.A.score,
        relevant=smart.R.score,
        time_bound=smart.T.score,
    )


def collect_recommendations(smart: SmartEvaluationResult) -> list[str]:
    """Собираем рекомендации по всем критериям в единый список."""
    recs = []
    for label, criterion in [
        ("S (Конкретность)", smart.S),
        ("M (Измеримость)", smart.M),
        ("A (Достижимость)", smart.A),
        ("R (Релевантность)", smart.R),
        ("T (Ограниченность во времени)", smart.T),
    ]:
        if criterion.recommendation:
            recs.append(f"{label}: {criterion.recommendation}")
    return recs


async def evaluate_strategic_link(
    goal_text: str,
    position: str,
    department: str,
    rag_chunks: list[dict],
    kpi_data: list[dict],
    manager_goals: list[str],
) -> StrategicLinkResult:
    """
    Вызов 2 (отдельный!): Стратегическая связка.
    Не объединять со SMART-оценкой.
    """
    rag_context = _format_rag_context(rag_chunks)
    kpi_context = _format_kpi_context(kpi_data)
    mgr_goals_str = _format_manager_goals(manager_goals)

    user_msg = prompts.STRATEGIC_LINK_USER.format(
        goal_text=goal_text,
        position=position,
        department=department,
        rag_context=rag_context,
        kpi_context=kpi_context,
        manager_goals=mgr_goals_str,
    )

    messages = [{"role": "user", "content": user_msg}]

    data = await call_llm_json(
        messages=messages,
        temperature=settings.llm_temperature_eval,
        max_tokens=1500,
        system=prompts.STRATEGIC_LINK_SYSTEM,
    )

    return StrategicLinkResult(
        link_level=data.get("link_level", "операционная"),
        source_type=data.get("source_type", "нет"),
        source_name=data.get("source_name"),
        source_quote=data.get("source_quote"),
        confidence=float(data.get("confidence", 0.5)),
        reasoning=data.get("reasoning", ""),
    )


async def reformulate_goal(
    goal_text: str,
    position: str,
    department: str,
    quarter: str,
    smart_result: SmartEvaluationResult,
    rag_chunks: list[dict],
    kpi_data: list[dict],
) -> dict:
    """Переформулировка слабой цели."""
    # Порог 0.5 соответствует оценке 3 на шкале 1-5 (=(3-1)/4=0.5)
    weak_criteria = [
        k for k, v in [
            ("S", smart_result.S.score),
            ("M", smart_result.M.score),
            ("A", smart_result.A.score),
            ("R", smart_result.R.score),
            ("T", smart_result.T.score),
        ]
        if v < 0.5
    ]

    user_msg = prompts.REFORMULATION_USER.format(
        goal_text=goal_text,
        position=position,
        department=department,
        quarter=quarter,
        smart_index=smart_result.smart_index,
        goal_type=smart_result.goal_type,
        weak_criteria=", ".join(weak_criteria) if weak_criteria else "нет критически слабых",
        rag_context=_format_rag_context(rag_chunks),
        kpi_context=_format_kpi_context(kpi_data),
    )

    messages = [{"role": "user", "content": user_msg}]

    data = await call_llm_json(
        messages=messages,
        temperature=settings.llm_temperature_gen,
        max_tokens=2000,
        system=prompts.REFORMULATION_SYSTEM,
    )

    return data


def _format_rag_context(chunks: list[dict]) -> str:
    if not chunks:
        return "Нет релевантных документов."
    parts = []
    for i, chunk in enumerate(chunks[:3], 1):
        meta = chunk.get("metadata", {})
        title = meta.get("title", "Документ")
        text = chunk.get("chunk_text", "")[:600]
        score = chunk.get("relevance_score", 0)
        parts.append(f"**[{i}] {title}** (релевантность: {score:.2f})\n{text}")
    return "\n\n---\n\n".join(parts)


def _format_kpi_context(kpi_data: list[dict]) -> str:
    if not kpi_data:
        return "KPI данные недоступны."
    lines = []
    for k in kpi_data[:5]:
        line = f"- {k['metric_name']}: {k['metric_value']} {k.get('metric_unit', '')} (цель: {k.get('target_value', 'н/д')})"
        lines.append(line)
    return "\n".join(lines)


def _format_manager_goals(goals: list[str]) -> str:
    if not goals:
        return "Цели руководителя не указаны."
    return "\n".join(f"- {g}" for g in goals[:3])
