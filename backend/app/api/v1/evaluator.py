import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.schemas import (
    EvaluateRequest, EvaluateResponse,
    BatchEvaluateRequest, BatchEvaluateResponse, BatchGoalResult, BatchWarning,
    ReformulateRequest, ReformulateResponse,
)

router = APIRouter()
log = logging.getLogger(__name__)


@router.post("/evaluate", response_model=EvaluateResponse)
async def evaluate_goal(
    request: EvaluateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Оценка одной цели: SMART + тип + стратегическая связка."""
    try:
        from app.core.evaluator import (
            evaluate_smart, evaluate_strategic_link,
            build_smart_scores, collect_recommendations,
        )
        from app.core.rag import retrieve_for_evaluation
        from app.models import KpiTimeseries, Employee
        from sqlalchemy import select

        # Загружаем данные сотрудника если передан employee_id
        dept_id = None
        position = request.position
        department = request.department
        if request.employee_id:
            emp_res = await db.execute(select(Employee).where(Employee.id == request.employee_id))
            emp = emp_res.scalar_one_or_none()
            if emp:
                dept_id = emp.department_id
                position = emp.position  # берём из БД, не из запроса

        rag_chunks = await retrieve_for_evaluation(request.goal_text, dept_id)

        # KPI данные подразделения
        kpi_data = []
        if dept_id:
            kpi_res = await db.execute(
                select(KpiTimeseries)
                .where(KpiTimeseries.department_id == dept_id)
                .order_by(KpiTimeseries.quarter.desc())
                .limit(10)
            )
            kpi_data = [
                {"metric_name": k.metric_name, "metric_value": k.metric_value,
                 "metric_unit": k.metric_unit, "target_value": k.target_value}
                for k in kpi_res.scalars().all()
            ]

        # Загружаем цели руководителя для стратегической связки
        manager_goals = []
        if request.employee_id and request.quarter:
            mgr_res = await db.execute(select(Employee.manager_id).where(Employee.id == request.employee_id))
            manager_id = mgr_res.scalar_one_or_none()
            if manager_id:
                from app.models import Goal as GoalModel
                mgr_goals_res = await db.execute(
                    select(GoalModel.goal_text)
                    .where(GoalModel.employee_id == manager_id, GoalModel.quarter == request.quarter)
                    .limit(5)
                )
                manager_goals = [r[0] for r in mgr_goals_res.all()]

        # Вызов 1: SMART + тип цели
        eval_req_with_context = request.model_copy(update={"position": position, "department": department})
        smart_result = await evaluate_smart(eval_req_with_context, rag_context="")

        # Вызов 2: Стратегическая связка (отдельный LLM-вызов)
        strategic_result = await evaluate_strategic_link(
            goal_text=request.goal_text,
            position=position,
            department=department,
            rag_chunks=rag_chunks,
            kpi_data=kpi_data,
            manager_goals=manager_goals,
        )

        smart_scores = build_smart_scores(smart_result)
        recommendations = collect_recommendations(smart_result)

        improved_goal = None
        if smart_result.reformulation_suggested and smart_result.reformulation_hint:
            improved_goal = smart_result.reformulation_hint

        # F-20: проверка достижимости на основе исторических данных
        achievability_warning = None
        if dept_id:
            try:
                from app.services.goal_service import get_similar_goals
                similar = await get_similar_goals(db, request.goal_text, dept_id, position)
                if similar:
                    rejected = [g for g in similar if g.get("verdict") == "rejected"]
                    rejection_rate = len(rejected) / len(similar)
                    if rejection_rate > 0.5:
                        achievability_warning = (
                            f"⚠ Предупреждение о достижимости: {len(rejected)} из {len(similar)} похожих целей "
                            f"в этом подразделении были отклонены ({int(rejection_rate*100)}%). "
                            f"Проверьте реалистичность цели."
                        )
            except Exception as e:
                log.warning(f"Ошибка F-20 проверки достижимости: {e}")

        # F-21: проверка дублирования с существующими целями сотрудника
        duplicate_warning = None
        if request.employee_id:
            try:
                from app.models import Goal as GoalModel
                from app.core.generator import _simple_similarity
                quarter_filter = request.quarter if request.quarter else None
                q = select(GoalModel.goal_text).where(GoalModel.employee_id == request.employee_id)
                if quarter_filter:
                    q = q.where(GoalModel.quarter == quarter_filter)
                existing_res = await db.execute(q.limit(20))
                existing_texts = [r[0] for r in existing_res.all()]
                if existing_texts:
                    sim = _simple_similarity(request.goal_text, existing_texts)
                    if sim > 0.40:
                        # Найдём наиболее похожую
                        best = max(existing_texts, key=lambda t: _simple_similarity(request.goal_text, [t]))
                        duplicate_warning = (
                            f"⚠ Возможное дублирование: цель схожа с уже существующей целью сотрудника "
                            f"({int(sim * 100)}% совпадение). "
                            f"Похожая цель: «{best[:100]}…»"
                        )
            except Exception as e:
                log.warning(f"Ошибка F-21 проверки дублирования: {e}")

        return EvaluateResponse(
            goal_id=request.goal_id,
            goal_text=request.goal_text,
            smart_scores=smart_scores,
            smart_index=smart_result.smart_index,
            recommendations=recommendations,
            improved_goal=improved_goal,
            achievability_warning=achievability_warning,
            duplicate_warning=duplicate_warning,
            smart_detail=smart_result,
            strategic_link=strategic_result,
        )

    except Exception as e:
        log.error(f"Ошибка оценки: {e}", exc_info=True)
        raise HTTPException(500, f"Ошибка AI-оценки: {str(e)}")


@router.post("/evaluate/batch", response_model=BatchEvaluateResponse)
async def evaluate_batch(
    request: BatchEvaluateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Пакетная оценка набора целей сотрудника."""
    try:
        from app.core.evaluator import (
            evaluate_smart, evaluate_strategic_link,
            build_smart_scores, collect_recommendations,
        )
        from app.core.rag import retrieve_for_evaluation
        from app.models import KpiTimeseries, Employee
        from sqlalchemy import select

        emp_res = await db.execute(select(Employee).where(Employee.id == request.employee_id))
        emp = emp_res.scalar_one_or_none()
        dept_id = emp.department_id if emp else None

        kpi_data = []
        if dept_id:
            kpi_res = await db.execute(
                select(KpiTimeseries)
                .where(KpiTimeseries.department_id == dept_id)
                .order_by(KpiTimeseries.quarter.desc())
                .limit(10)
            )
            kpi_data = [
                {"metric_name": k.metric_name, "metric_value": k.metric_value,
                 "metric_unit": k.metric_unit, "target_value": k.target_value}
                for k in kpi_res.scalars().all()
            ]

        warnings = []
        goal_results = []
        total_weight = sum(g.weight for g in request.goals)
        type_dist: dict[str, int] = {}

        # Проверки batch-уровня
        n = len(request.goals)
        if n < 3:
            warnings.append(BatchWarning(type="count", message=f"Слишком мало целей: {n}. Рекомендуется 3-5."))
        elif n > 5:
            warnings.append(BatchWarning(type="count", message=f"Слишком много целей: {n}. Рекомендуется не более 5."))

        if abs(total_weight - 100) > 1:
            warnings.append(BatchWarning(type="weights", message=f"Сумма весов = {total_weight}%. Должна быть 100%."))

        for goal_input in request.goals:
            eval_req = EvaluateRequest(
                goal_text=goal_input.goal_text,
                position=request.position,
                department=request.department,
                quarter=request.quarter,
                employee_id=request.employee_id,
                goal_id=goal_input.goal_id,
            )

            rag_chunks = await retrieve_for_evaluation(goal_input.goal_text, dept_id)
            smart = await evaluate_smart(eval_req)
            strategic = await evaluate_strategic_link(
                goal_text=goal_input.goal_text,
                position=request.position,
                department=request.department,
                rag_chunks=rag_chunks,
                kpi_data=kpi_data,
                manager_goals=[],
            )

            type_dist[smart.goal_type] = type_dist.get(smart.goal_type, 0) + 1

            improved_goal = None
            if smart.reformulation_suggested and smart.reformulation_hint:
                improved_goal = smart.reformulation_hint

            goal_results.append(BatchGoalResult(
                goal_id=goal_input.goal_id,
                goal_text=goal_input.goal_text,
                weight=goal_input.weight,
                smart_scores=build_smart_scores(smart),
                smart_index=smart.smart_index,
                recommendations=collect_recommendations(smart),
                improved_goal=improved_goal,
                smart_detail=smart,
                strategic_link=strategic,
            ))

        # Проверка баланса типов
        if type_dist.get("activity-based", 0) == n:
            warnings.append(BatchWarning(
                type="goal_types",
                message="Все цели activity-based. Добавьте как минимум одну impact-based цель.",
            ))

        avg_smart = round(sum(r.smart_index * (r.weight / 100) for r in goal_results), 3)

        return BatchEvaluateResponse(
            goals=goal_results,
            warnings=warnings,
            overall_smart_index=avg_smart,
            total_weight=total_weight,
            type_distribution=type_dist,
        )

    except Exception as e:
        log.error(f"Ошибка batch-оценки: {e}", exc_info=True)
        raise HTTPException(500, f"Ошибка AI batch-оценки: {str(e)}")


@router.post("/reformulate", response_model=ReformulateResponse)
async def reformulate_goal_endpoint(
    request: ReformulateRequest,
):
    """Переформулировка слабой цели с before/after SMART-оценками."""
    try:
        from app.core.evaluator import (
            evaluate_smart, reformulate_goal,
            build_smart_scores,
        )
        from app.core.rag import retrieve_for_evaluation

        eval_req = EvaluateRequest(
            goal_text=request.goal_text,
            position=request.position,
            department=request.department,
        )

        rag_chunks = await retrieve_for_evaluation(request.goal_text)
        kpi_data = []

        # Original evaluation
        original_smart = await evaluate_smart(eval_req)

        # Reformulate
        ref_data = await reformulate_goal(
            goal_text=request.goal_text,
            position=request.position,
            department=request.department,
            quarter="текущий квартал",
            smart_result=original_smart,
            rag_chunks=rag_chunks,
            kpi_data=kpi_data,
        )

        reformulated_text = ref_data.get("reformulated_goal", request.goal_text)

        # Evaluate reformulated
        ref_eval_req = EvaluateRequest(
            goal_text=reformulated_text,
            position=request.position,
            department=request.department,
        )
        reformulated_smart = await evaluate_smart(ref_eval_req)

        return ReformulateResponse(
            original_goal=request.goal_text,
            reformulated_goal=reformulated_text,
            original_smart_scores=build_smart_scores(original_smart),
            original_smart_index=original_smart.smart_index,
            reformulated_smart_scores=build_smart_scores(reformulated_smart),
            reformulated_smart_index=reformulated_smart.smart_index,
            original_smart_detail=original_smart,
            reformulated_smart_detail=reformulated_smart,
            improvements=ref_data.get("improvements", []),
        )

    except Exception as e:
        log.error(f"Ошибка переформулировки: {e}", exc_info=True)
        raise HTTPException(500, f"Ошибка переформулировки: {str(e)}")
