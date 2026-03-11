"""Бизнес-логика работы с целями (CRUD + поиск похожих)."""
import logging
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Goal, Employee, GoalReview

log = logging.getLogger(__name__)


async def get_similar_goals(
    db: AsyncSession,
    goal_text: str,
    department_id: int,
    position: str,
    limit: int = 10,
) -> list[dict]:
    """
    Находит похожие цели из истории для оценки достижимости (F-20).
    Использует простой keyword-based поиск + фильтр по департаменту.
    """
    # Берём ключевые слова из текста цели
    stop_words = {"и", "в", "на", "по", "для", "с", "о", "от", "до", "за", "из", "к", "а", "что", "как"}
    words = [w.lower() for w in goal_text.split() if len(w) > 4 and w.lower() not in stop_words]
    if not words:
        return []

    # Ищем цели в том же департаменте
    result = await db.execute(
        select(Goal, GoalReview)
        .outerjoin(GoalReview, Goal.id == GoalReview.goal_id)
        .join(Employee, Goal.employee_id == Employee.id)
        .where(Employee.department_id == department_id)
        .where(Goal.status.in_(["approved", "rejected", "revision_requested"]))
        .order_by(Goal.id.desc())
        .limit(200)
    )
    rows = result.all()

    # Фильтруем по схожести текста
    similar = []
    for goal, review in rows:
        text_lower = goal.goal_text.lower()
        matches = sum(1 for w in words if w in text_lower)
        if matches >= max(1, len(words) // 3):
            similar.append({
                "goal_text": goal.goal_text,
                "status": goal.status,
                "smart_index": goal.smart_index,
                "verdict": review.verdict if review else None,
                "similarity": matches / len(words),
            })

    similar.sort(key=lambda x: x["similarity"], reverse=True)
    return similar[:limit]


async def get_historical_approval_rate(
    db: AsyncSession,
    department_id: int,
    position_keywords: list[str],
) -> dict:
    """Статистика одобрения целей для оценки Achievable."""
    result = await db.execute(
        select(
            GoalReview.verdict,
            func.count(GoalReview.id).label("cnt")
        )
        .join(Goal, GoalReview.goal_id == Goal.id)
        .join(Employee, Goal.employee_id == Employee.id)
        .where(Employee.department_id == department_id)
        .group_by(GoalReview.verdict)
    )
    counts = {row.verdict: row.cnt for row in result.all()}
    total = sum(counts.values())
    if total == 0:
        return {"approval_rate": 0.7, "total": 0}

    approved = counts.get("approved", 0)
    return {
        "approval_rate": round(approved / total, 2),
        "approved": approved,
        "rejected": counts.get("rejected", 0),
        "needs_revision": counts.get("needs_revision", 0),
        "total": total,
    }
