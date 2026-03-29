from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Goal, GoalEvent, GoalStatus, EventType
from app.core.schemas import GoalShort

router = APIRouter()


class AcceptGoalRequest(BaseModel):
    employee_id: int
    quarter: str
    goal_text: str
    metric: Optional[str] = None
    deadline: Optional[str] = None
    weight: Optional[float] = None
    goal_type: Optional[str] = None
    strategic_link: Optional[str] = None
    smart_s: Optional[float] = None
    smart_m: Optional[float] = None
    smart_a: Optional[float] = None
    smart_r: Optional[float] = None
    smart_t: Optional[float] = None
    smart_index: Optional[float] = None
    source_document: Optional[str] = None
    source_quote: Optional[str] = None
    is_generated: bool = True


@router.post("/goals", status_code=201)
async def create_goal(req: AcceptGoalRequest, db: AsyncSession = Depends(get_db)):
    """F-13: Сохранение принятой AI-цели в БД. F-15: Записывает GoalEvent 'created'."""
    year = int(req.quarter.split("-")[0]) if req.quarter else 2026
    goal = Goal(
        employee_id=req.employee_id,
        goal_text=req.goal_text,
        metric=req.metric,
        deadline=req.deadline,
        weight=req.weight,
        quarter=req.quarter,
        year=year,
        status=GoalStatus.draft.value,
        goal_type=req.goal_type,
        strategic_link=req.strategic_link,
        smart_s=req.smart_s,
        smart_m=req.smart_m,
        smart_a=req.smart_a,
        smart_r=req.smart_r,
        smart_t=req.smart_t,
        smart_index=req.smart_index,
        source_document=req.source_document,
        source_quote=req.source_quote,
        is_generated=req.is_generated,
    )
    db.add(goal)
    await db.flush()  # получаем goal.id до commit

    # F-15: Версионирование — записываем событие создания
    event = GoalEvent(
        goal_id=goal.id,
        event_type=EventType.created.value,
        actor_id=req.employee_id,
        comment="Цель принята из AI-набора",
        metadata_json={
            "source": "ai_generated",
            "smart_index": req.smart_index,
            "goal_type": req.goal_type,
        },
    )
    db.add(event)
    await db.commit()
    await db.refresh(goal)

    return {
        "id": goal.id,
        "goal_text": goal.goal_text,
        "quarter": goal.quarter,
        "status": goal.status,
        "smart_index": goal.smart_index,
        "message": "Цель сохранена",
    }


@router.get("/goals/{goal_id}")
async def get_goal(goal_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Goal).where(Goal.id == goal_id))
    goal = result.scalar_one_or_none()
    if not goal:
        raise HTTPException(404, "Цель не найдена")
    return {
        "id": goal.id,
        "goal_text": goal.goal_text,
        "metric": goal.metric,
        "deadline": goal.deadline,
        "weight": goal.weight,
        "quarter": goal.quarter,
        "status": goal.status,
        "goal_type": goal.goal_type,
        "strategic_link": goal.strategic_link,
        "smart_s": goal.smart_s,
        "smart_m": goal.smart_m,
        "smart_a": goal.smart_a,
        "smart_r": goal.smart_r,
        "smart_t": goal.smart_t,
        "smart_index": goal.smart_index,
        "source_document": goal.source_document,
        "source_quote": goal.source_quote,
    }
