from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Goal
from app.core.schemas import GoalShort

router = APIRouter()


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
