"""Логика генерации целей: RAG + LLM + self-check."""
import logging
from typing import Optional, AsyncGenerator

from app.config import settings
from app.core import prompts
from app.core.llm_client import call_llm_json
from app.core.schemas import GeneratedGoal, EvaluateRequest

log = logging.getLogger(__name__)

MAX_RETRY = 2


async def _build_user_msg(
    n_goals, quarter, full_name, position, grade, department,
    manager_name, manager_goals, existing_goals, focus_priorities, rag_chunks, kpi_data,
):
    from app.core.evaluator import _format_rag_context, _format_kpi_context
    rag_context = _format_rag_context(rag_chunks)
    kpi_context = _format_kpi_context(kpi_data)
    existing_str = "\n".join(f"- {g}" for g in existing_goals[:10]) if existing_goals else "Нет существующих целей."
    manager_goals_str = "\n".join(f"- {g}" for g in manager_goals[:3]) if manager_goals else "Цели руководителя не указаны."
    focus_str = focus_priorities or "Не указаны. Используй KPI подразделения как ориентир."
    user_msg = prompts.GENERATION_USER.format(
        n_goals=n_goals, quarter=quarter, full_name=full_name, position=position,
        grade=grade, department=department, manager_name=manager_name,
        focus_priorities=focus_str, rag_context=rag_context, kpi_context=kpi_context,
        manager_goals=manager_goals_str, existing_goals=existing_str,
    )
    return user_msg, rag_context


async def _self_check_goal(raw, position, department, quarter, rag_chunks, kpi_data, rag_context):
    from app.core.evaluator import evaluate_smart, build_smart_scores
    goal_text = raw.get("goal_text", "")
    smart_result = None
    requires_review = False
    for attempt in range(MAX_RETRY + 1):
        try:
            eval_req = EvaluateRequest(goal_text=goal_text, position=position, department=department, quarter=quarter)
            smart_result = await evaluate_smart(eval_req, rag_context)
            if smart_result.smart_index >= 0.625 or attempt == MAX_RETRY:
                break
            if attempt < MAX_RETRY:
                from app.core.evaluator import reformulate_goal
                ref_data = await reformulate_goal(
                    goal_text=goal_text, position=position, department=department, quarter=quarter,
                    smart_result=smart_result, rag_chunks=rag_chunks, kpi_data=kpi_data,
                )
                goal_text = ref_data.get("reformulated_goal", goal_text)
            else:
                requires_review = True
        except Exception as e:
            log.error(f"Ошибка self-check: {e}")
            requires_review = True
            break

    from app.core.evaluator import build_smart_scores
    return GeneratedGoal(
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
    )


async def generate_goals_stream(
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
) -> AsyncGenerator[dict, None]:
    """Потоковая генерация целей — каждая готовая цель отдаётся как SSE событие."""
    user_msg, rag_context = await _build_user_msg(
        n_goals, quarter, full_name, position, grade, department,
        manager_name, manager_goals, existing_goals, focus_priorities, rag_chunks, kpi_data,
    )
    messages = [{"role": "user", "content": user_msg}]
    raw_goals = await call_llm_json(
        messages=messages, temperature=settings.llm_temperature_gen,
        max_tokens=4000, system=prompts.GENERATION_SYSTEM,
    )
    if not isinstance(raw_goals, list):
        raw_goals = raw_goals.get("goals", []) if isinstance(raw_goals, dict) else []
    raw_goals = raw_goals[:n_goals]

    # Нормализуем веса до начала стриминга
    total_w = sum(r.get("weight", 25) for r in raw_goals)
    if raw_goals and total_w > 0 and abs(total_w - 100) > 5:
        for r in raw_goals:
            r["weight"] = round(r.get("weight", 25) / total_w * 100)
        raw_goals[-1]["weight"] += 100 - sum(r["weight"] for r in raw_goals)

    yield {"type": "start", "total": len(raw_goals)}

    result_goals = []
    warnings = []
    for i, raw in enumerate(raw_goals):
        if not raw.get("goal_text", ""):
            continue
        goal = await _self_check_goal(raw, position, department, quarter, rag_chunks, kpi_data, rag_context)
        result_goals.append(goal)
        yield {"type": "goal", "index": i, "goal": goal.model_dump()}

    # Дублирование с существующими целями
    for g in result_goals:
        if existing_goals and _simple_similarity(g.goal_text, existing_goals) > 0.7:
            warnings.append(f"Возможное дублирование: «{g.goal_text[:80]}…»")

    if all(g.goal_type == "activity-based" for g in result_goals) and result_goals:
        warnings.append("Все цели activity-based. Рекомендуется добавить output-based или impact-based.")

    total_weight = sum(g.weight for g in result_goals)
    yield {"type": "done", "warnings": warnings, "total_weight": total_weight}


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
    """Генерация целей (не-стриминг версия, использует generate_goals_stream внутри)."""
    result_goals = []
    warnings = []
    async for event in generate_goals_stream(
        employee_id=employee_id, full_name=full_name, position=position, grade=grade,
        department=department, department_id=department_id, quarter=quarter,
        focus_priorities=focus_priorities, n_goals=n_goals, manager_name=manager_name,
        manager_goals=manager_goals, existing_goals=existing_goals,
        rag_chunks=rag_chunks, kpi_data=kpi_data,
    ):
        if event["type"] == "goal":
            result_goals.append(GeneratedGoal(**event["goal"]))
        elif event["type"] == "done":
            warnings = event["warnings"]
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
