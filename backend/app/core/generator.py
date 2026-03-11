"""Логика генерации целей: RAG + LLM + self-check."""
import logging
from typing import Optional

from app.config import settings
from app.core import prompts
from app.core.llm_client import call_llm_json
from app.core.schemas import GeneratedGoal, EvaluateRequest

log = logging.getLogger(__name__)

MAX_RETRY = 2


async def generate_goals(
    employee_id: int,
    full_name: str,
    position: str,
    grade: str,
    department: str,
    department_id: int,
    quarter: str,
    focus_priorities: Optional[str],
    n_goals: int,
    manager_name: str,
    manager_goals: list[str],
    existing_goals: list[str],
    rag_chunks: list[dict],
    kpi_data: list[dict],
) -> tuple[list[GeneratedGoal], list[str]]:
    """
    Генерация целей:
    1. Формируем промпт с профилем + RAG + KPI
    2. Вызываем LLM
    3. Self-check: прогоняем через evaluator, retry если score < 3.5
    4. Проверяем дублирование с существующими целями
    """
    from app.core.evaluator import evaluate_smart, build_smart_scores, _format_rag_context, _format_kpi_context

    rag_context = _format_rag_context(rag_chunks)
    kpi_context = _format_kpi_context(kpi_data)
    existing_str = "\n".join(f"- {g}" for g in existing_goals[:10]) if existing_goals else "Нет существующих целей."
    manager_goals_str = "\n".join(f"- {g}" for g in manager_goals[:3]) if manager_goals else "Цели руководителя не указаны."
    focus_str = focus_priorities or "Не указаны. Используй KPI подразделения как ориентир."

    user_msg = prompts.GENERATION_USER.format(
        n_goals=n_goals,
        quarter=quarter,
        full_name=full_name,
        position=position,
        grade=grade,
        department=department,
        manager_name=manager_name,
        focus_priorities=focus_str,
        rag_context=rag_context,
        kpi_context=kpi_context,
        manager_goals=manager_goals_str,
        existing_goals=existing_str,
    )

    messages = [{"role": "user", "content": user_msg}]

    raw_goals = await call_llm_json(
        messages=messages,
        temperature=settings.llm_temperature_gen,
        max_tokens=4000,
        system=prompts.GENERATION_SYSTEM,
    )

    if not isinstance(raw_goals, list):
        raw_goals = raw_goals.get("goals", []) if isinstance(raw_goals, dict) else []

    # Self-check pipeline
    result_goals = []
    warnings = []

    for raw in raw_goals[:n_goals]:
        goal_text = raw.get("goal_text", "")
        if not goal_text:
            continue

        # Evaluate generated goal
        smart_result = None
        requires_review = False

        for attempt in range(MAX_RETRY + 1):
            try:
                eval_req = EvaluateRequest(
                    goal_text=goal_text,
                    position=position,
                    department=department,
                    quarter=quarter,
                )
                smart_result = await evaluate_smart(eval_req, rag_context)

                # 0.625 = 3.5/5 нормализованное через (3.5-1)/4
                if smart_result.smart_index >= 0.625 or attempt == MAX_RETRY:
                    break

                if attempt < MAX_RETRY:
                    log.info(f"Self-check: SMART={smart_result.smart_index}, retry {attempt + 1}")
                    # Переформулируем с помощью evaluator
                    from app.core.evaluator import reformulate_goal
                    ref_data = await reformulate_goal(
                        goal_text=goal_text,
                        position=position,
                        department=department,
                        quarter=quarter,
                        smart_result=smart_result,
                        rag_chunks=rag_chunks,
                        kpi_data=kpi_data,
                    )
                    goal_text = ref_data.get("reformulated_goal", goal_text)
                else:
                    requires_review = True

            except Exception as e:
                log.error(f"Ошибка self-check: {e}")
                requires_review = True
                break

        # Проверка дублирования с существующими целями
        if existing_goals and smart_result:
            similarity = _simple_similarity(goal_text, existing_goals)
            if similarity > 0.7:
                warnings.append(f"Возможное дублирование: '{goal_text[:80]}...' похожа на существующую цель")

        result_goals.append(GeneratedGoal(
            goal_text=goal_text,
            metric=raw.get("metric", ""),
            deadline=raw.get("deadline", ""),
            weight=int(raw.get("weight", 25)),
            source_document=raw.get("source_document", ""),
            source_quote=raw.get("source_quote", ""),
            goal_type=raw.get("goal_type", "output-based"),
            strategic_link=raw.get("strategic_link", "функциональная"),
            reasoning=raw.get("reasoning", ""),
            smart_scores=build_smart_scores(smart_result) if smart_result else None,
            smart_index=smart_result.smart_index if smart_result else None,
            requires_review=requires_review,
        ))

    # Проверяем сумму весов
    total_weight = sum(g.weight for g in result_goals)
    if abs(total_weight - 100) > 5:
        # Нормализуем веса
        if total_weight > 0:
            for g in result_goals:
                g.weight = round(g.weight / total_weight * 100)
            result_goals[-1].weight += 100 - sum(g.weight for g in result_goals)
        warnings.append(f"Веса целей скорректированы (было {total_weight}%, стало 100%)")

    # Проверяем баланс типов
    types = [g.goal_type for g in result_goals]
    if all(t == "activity-based" for t in types):
        warnings.append("Все цели являются activity-based. Рекомендуется добавить output-based или impact-based цели.")

    return result_goals, warnings


def _simple_similarity(text1: str, goals: list[str]) -> float:
    """Простая оценка схожести на основе пересечения слов."""
    words1 = set(text1.lower().split())
    max_sim = 0.0
    for g in goals:
        words2 = set(g.lower().split())
        if not words1 or not words2:
            continue
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        sim = intersection / union if union > 0 else 0
        max_sim = max(max_sim, sim)
    return max_sim
