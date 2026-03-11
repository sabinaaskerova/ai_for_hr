"""Analytics Engine — агрегация метрик по подразделениям."""
from typing import Optional
from sqlalchemy import select, func, case, Integer
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Goal, Employee, Department, KpiTimeseries


async def get_department_smart_stats(db: AsyncSession, department_id: int, quarter: Optional[str] = None) -> dict:
    query = (
        select(
            func.avg(Goal.smart_s).label("avg_s"),
            func.avg(Goal.smart_m).label("avg_m"),
            func.avg(Goal.smart_a).label("avg_a"),
            func.avg(Goal.smart_r).label("avg_r"),
            func.avg(Goal.smart_t).label("avg_t"),
            func.avg(Goal.smart_index).label("avg_smart"),
            func.count(Goal.id).label("total"),
        )
        .join(Employee, Goal.employee_id == Employee.id)
        .where(Employee.department_id == department_id)
    )
    if quarter:
        query = query.where(Goal.quarter == quarter)

    result = await db.execute(query)
    row = result.one()
    return {
        "avg_s": round(row.avg_s or 0, 2),
        "avg_m": round(row.avg_m or 0, 2),
        "avg_a": round(row.avg_a or 0, 2),
        "avg_r": round(row.avg_r or 0, 2),
        "avg_t": round(row.avg_t or 0, 2),
        "avg_smart": round(row.avg_smart or 0, 2),
        "total": row.total or 0,
    }


def compute_maturity_index(
    avg_smart: float,
    strategic_link_ratio: float,
    impact_goal_ratio: float,
    no_dup_ratio: float = 1.0,
) -> float:
    """
    Maturity Index = smart*0.4 + strategic_link*5*0.3 + impact*5*0.2 + no_dup*5*0.1
    Нормализован в диапазон 0-5.
    """
    return round(
        avg_smart * 0.4
        + strategic_link_ratio * 5 * 0.3
        + impact_goal_ratio * 5 * 0.2
        + no_dup_ratio * 5 * 0.1,
        2,
    )


async def get_quarterly_trends(db: AsyncSession, department_id: Optional[int] = None) -> list[dict]:
    quarters = [
        "2024-Q1", "2024-Q2", "2024-Q3", "2024-Q4",
        "2025-Q1", "2025-Q2", "2025-Q3", "2025-Q4",
    ]
    results = []
    for q in quarters:
        query = select(
            func.avg(Goal.smart_index).label("avg_smart"),
            func.count(Goal.id).label("total"),
            func.sum(
                case(
                    (Goal.strategic_link.in_(["стратегическая", "функциональная"]), 1),
                    else_=0,
                )
            ).label("strategic_count"),
            func.sum(
                case(
                    (Goal.goal_type == "impact-based", 1),
                    else_=0,
                )
            ).label("impact_count"),
        ).where(Goal.quarter == q)

        if department_id:
            query = query.join(Employee, Goal.employee_id == Employee.id).where(
                Employee.department_id == department_id
            )

        row = (await db.execute(query)).one()
        total = row.total or 1
        results.append({
            "quarter": q,
            "avg_smart_index": round(row.avg_smart or 0, 2),
            "strategic_link_ratio": round((row.strategic_count or 0) / total, 2),
            "impact_goal_ratio": round((row.impact_count or 0) / total, 2),
        })
    return [r for r in results if r["avg_smart_index"] > 0]
