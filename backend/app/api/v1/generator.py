import json
import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db, AsyncSessionLocal
from app.core.schemas import GenerateRequest, GenerateResponse

router = APIRouter()
log = logging.getLogger(__name__)


async def _load_context(request: GenerateRequest):
    """Загружает контекст для генерации из БД."""
    from app.models import Employee, Department, Goal, KpiTimeseries
    from app.core.rag import retrieve_for_generation

    async with AsyncSessionLocal() as db:
        emp_res = await db.execute(select(Employee).where(Employee.id == request.employee_id))
        emp = emp_res.scalar_one_or_none()
        if not emp:
            raise HTTPException(404, "Сотрудник не найден")

        dept_res = await db.execute(select(Department).where(Department.id == emp.department_id))
        dept = dept_res.scalar_one_or_none()
        dept_name = dept.name if dept else "Подразделение"

        manager_name = "Не указан"
        manager_goals = []
        if emp.manager_id:
            mgr_res = await db.execute(select(Employee).where(Employee.id == emp.manager_id))
            mgr = mgr_res.scalar_one_or_none()
            if mgr:
                manager_name = mgr.full_name
                mgr_goals_res = await db.execute(
                    select(Goal).where(Goal.employee_id == emp.manager_id, Goal.quarter == request.quarter).limit(5)
                )
                manager_goals = [g.goal_text for g in mgr_goals_res.scalars().all()]

        existing_res = await db.execute(
            select(Goal).where(Goal.employee_id == request.employee_id, Goal.quarter == request.quarter).limit(10)
        )
        existing_goals = [g.goal_text for g in existing_res.scalars().all()]

        kpi_res = await db.execute(
            select(KpiTimeseries).where(KpiTimeseries.department_id == emp.department_id)
            .order_by(KpiTimeseries.quarter.desc()).limit(10)
        )
        kpi_data = [
            {"metric_name": k.metric_name, "metric_value": k.metric_value,
             "metric_unit": k.metric_unit, "target_value": k.target_value}
            for k in kpi_res.scalars().all()
        ]

    rag_chunks = await retrieve_for_generation(
        position=emp.position, department=dept_name, quarter=request.quarter,
        focus_priorities=request.focus_priorities, department_id=emp.department_id,
    )
    return emp, dept_name, manager_name, manager_goals, existing_goals, kpi_data, rag_chunks


@router.post("/generate/stream")
async def generate_goals_stream_endpoint(request: GenerateRequest):
    """SSE streaming: цели отдаются по мере готовности."""
    from app.core.generator import generate_goals_stream

    async def event_stream():
        try:
            emp, dept_name, manager_name, manager_goals, existing_goals, kpi_data, rag_chunks = \
                await _load_context(request)
            async for event in generate_goals_stream(
                employee_id=request.employee_id, full_name=emp.full_name,
                position=emp.position, grade=emp.grade, department=dept_name,
                department_id=emp.department_id, quarter=request.quarter,
                focus_priorities=request.focus_priorities, n_goals=request.n_goals,
                manager_name=manager_name, manager_goals=manager_goals,
                existing_goals=existing_goals, rag_chunks=rag_chunks, kpi_data=kpi_data,
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            log.error(f"Ошибка SSE генерации: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/generate", response_model=GenerateResponse)
async def generate_goals(request: GenerateRequest):
    """Генерация 3-5 SMART-целей (обычный JSON, без стриминга)."""
    try:
        from app.core.generator import generate_goals as gen_goals
        emp, dept_name, manager_name, manager_goals, existing_goals, kpi_data, rag_chunks = \
            await _load_context(request)
        goals, warnings = await gen_goals(
            employee_id=request.employee_id, full_name=emp.full_name,
            position=emp.position, grade=emp.grade, department=dept_name,
            department_id=emp.department_id, quarter=request.quarter,
            focus_priorities=request.focus_priorities, n_goals=request.n_goals,
            manager_name=manager_name, manager_goals=manager_goals,
            existing_goals=existing_goals, rag_chunks=rag_chunks, kpi_data=kpi_data,
        )
        return GenerateResponse(
            employee_id=request.employee_id, quarter=request.quarter,
            goals=goals, total_weight=sum(g.weight for g in goals), warnings=warnings,
        )
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Ошибка генерации целей: {e}", exc_info=True)
        raise HTTPException(500, f"Ошибка генерации: {str(e)}")
