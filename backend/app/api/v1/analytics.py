from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Goal, Department, KpiTimeseries
from app.core.schemas import DashboardResponse, DepartmentMetrics, TrendsResponse, TrendPoint

router = APIRouter()


@router.get("/analytics/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    quarter: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    # Загружаем все департаменты
    dept_res = await db.execute(select(Department))
    departments = {d.id: d for d in dept_res.scalars().all()}

    dept_metrics = []
    all_smart = []
    all_strategic = []
    all_impact = []
    criterion_avgs = {"S": [], "M": [], "A": [], "R": [], "T": []}

    for dept_id, dept in departments.items():
        from app.models import Employee
        goals_q = (
            select(Goal)
            .join(Employee, Goal.employee_id == Employee.id)
            .where(Employee.department_id == dept_id)
        )
        if quarter:
            goals_q = goals_q.where(Goal.quarter == quarter)

        result = await db.execute(goals_q)
        goals = result.scalars().all()

        if not goals:
            continue

        def avg(vals):
            clean = [v for v in vals if v is not None]
            return round(sum(clean) / len(clean), 2) if clean else 0.0

        avg_smart = avg([g.smart_index for g in goals])
        avg_s = avg([g.smart_s for g in goals])
        avg_m = avg([g.smart_m for g in goals])
        avg_a = avg([g.smart_a for g in goals])
        avg_r = avg([g.smart_r for g in goals])
        avg_t = avg([g.smart_t for g in goals])

        strategic = len([g for g in goals if g.strategic_link in ("стратегическая", "функциональная")])
        impact = len([g for g in goals if g.goal_type == "impact-based"])
        approved = len([g for g in goals if g.status == "approved"])
        rejected = len([g for g in goals if g.status == "rejected"])
        no_dup_ratio = 1.0  # упрощение — дубли не считаем здесь

        strategic_ratio = round(strategic / len(goals), 2)
        impact_ratio = round(impact / len(goals), 2)
        activity_ratio = round(len([g for g in goals if g.goal_type == "activity-based"]) / len(goals), 2)

        maturity = round(
            avg_smart * 0.4 + strategic_ratio * 5 * 0.3 + impact_ratio * 5 * 0.2 + no_dup_ratio * 5 * 0.1, 2
        )

        dept_metrics.append(DepartmentMetrics(
            department_id=dept_id,
            department_name=dept.name,
            avg_smart_index=avg_smart,
            avg_s=avg_s, avg_m=avg_m, avg_a=avg_a, avg_r=avg_r, avg_t=avg_t,
            strategic_link_ratio=strategic_ratio,
            impact_goal_ratio=impact_ratio,
            activity_goal_ratio=activity_ratio,
            maturity_index=maturity,
            total_goals=len(goals),
            goals_approved=approved,
            goals_rejected=rejected,
        ))
        all_smart.append(avg_smart)
        all_strategic.append(strategic_ratio)
        all_impact.append(impact_ratio)
        for key, val in [("S", avg_s), ("M", avg_m), ("A", avg_a), ("R", avg_r), ("T", avg_t)]:
            criterion_avgs[key].append(val)

    def safe_avg(lst):
        return round(sum(lst) / len(lst), 2) if lst else 0.0

    overall_smart = safe_avg(all_smart)
    overall_strategic = safe_avg(all_strategic)
    overall_impact = safe_avg(all_impact)
    overall_maturity = round(
        overall_smart * 0.4 + overall_strategic * 5 * 0.3 + overall_impact * 5 * 0.2 + 0.1 * 5, 2
    )

    # Weakest criterion
    crit_means = {k: safe_avg(v) for k, v in criterion_avgs.items()}
    weakest = min(crit_means, key=lambda k: crit_means[k]) if crit_means else "M"

    dept_metrics_sorted = sorted(dept_metrics, key=lambda d: d.avg_smart_index, reverse=True)
    top_dept = dept_metrics_sorted[0].department_name if dept_metrics_sorted else ""
    bottom_dept = dept_metrics_sorted[-1].department_name if dept_metrics_sorted else ""

    return DashboardResponse(
        overall_smart_index=overall_smart,
        strategic_link_ratio=overall_strategic,
        impact_goal_ratio=overall_impact,
        maturity_index=overall_maturity,
        departments=dept_metrics,
        weakest_criterion=weakest,
        top_department=top_dept,
        bottom_department=bottom_dept,
    )


@router.get("/analytics/department/{dept_id}", response_model=DepartmentMetrics)
async def get_department_analytics(
    dept_id: int,
    quarter: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    dept_res = await db.execute(select(Department).where(Department.id == dept_id))
    dept = dept_res.scalar_one_or_none()
    if not dept:
        from fastapi import HTTPException
        raise HTTPException(404, "Департамент не найден")

    from app.models import Employee
    goals_q = (
        select(Goal)
        .join(Employee, Goal.employee_id == Employee.id)
        .where(Employee.department_id == dept_id)
    )
    if quarter:
        goals_q = goals_q.where(Goal.quarter == quarter)

    result = await db.execute(goals_q)
    goals = result.scalars().all()

    def avg(vals):
        clean = [v for v in vals if v is not None]
        return round(sum(clean) / len(clean), 2) if clean else 0.0

    avg_smart = avg([g.smart_index for g in goals])
    strategic_ratio = round(len([g for g in goals if g.strategic_link in ("стратегическая", "функциональная")]) / max(len(goals), 1), 2)
    impact_ratio = round(len([g for g in goals if g.goal_type == "impact-based"]) / max(len(goals), 1), 2)
    activity_ratio = round(len([g for g in goals if g.goal_type == "activity-based"]) / max(len(goals), 1), 2)
    maturity = round(avg_smart * 0.4 + strategic_ratio * 5 * 0.3 + impact_ratio * 5 * 0.2 + 5 * 0.1, 2)

    return DepartmentMetrics(
        department_id=dept_id,
        department_name=dept.name,
        avg_smart_index=avg_smart,
        avg_s=avg([g.smart_s for g in goals]),
        avg_m=avg([g.smart_m for g in goals]),
        avg_a=avg([g.smart_a for g in goals]),
        avg_r=avg([g.smart_r for g in goals]),
        avg_t=avg([g.smart_t for g in goals]),
        strategic_link_ratio=strategic_ratio,
        impact_goal_ratio=impact_ratio,
        activity_goal_ratio=activity_ratio,
        maturity_index=maturity,
        total_goals=len(goals),
        goals_approved=len([g for g in goals if g.status == "approved"]),
        goals_rejected=len([g for g in goals if g.status == "rejected"]),
    )


@router.get("/analytics/trends", response_model=TrendsResponse)
async def get_trends(
    department_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    from app.models import Employee
    quarters = ["2024-Q1", "2024-Q2", "2024-Q3", "2024-Q4",
                "2025-Q1", "2025-Q2", "2025-Q3", "2025-Q4"]

    trends = []
    for q in quarters:
        goals_q = select(Goal).where(Goal.quarter == q)
        if department_id:
            goals_q = goals_q.join(Employee, Goal.employee_id == Employee.id).where(Employee.department_id == department_id)

        result = await db.execute(goals_q)
        goals = result.scalars().all()

        if not goals:
            continue

        def avg(vals):
            clean = [v for v in vals if v is not None]
            return round(sum(clean) / len(clean), 2) if clean else 0.0

        trends.append(TrendPoint(
            quarter=q,
            avg_smart_index=avg([g.smart_index for g in goals]),
            strategic_link_ratio=round(len([g for g in goals if g.strategic_link in ("стратегическая", "функциональная")]) / len(goals), 2),
            impact_goal_ratio=round(len([g for g in goals if g.goal_type == "impact-based"]) / len(goals), 2),
        ))

    return TrendsResponse(department_id=department_id, trends=trends)
