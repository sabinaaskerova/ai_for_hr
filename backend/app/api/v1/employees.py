from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Employee, Department, Goal
from app.core.schemas import EmployeeShort, EmployeeDetail, GoalShort, EmployeeListResponse

router = APIRouter()


@router.get("/employees", response_model=EmployeeListResponse)
async def list_employees(
    search: Optional[str] = Query(None, description="Поиск по имени"),
    department_id: Optional[int] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Employee)
        .join(Department, Employee.department_id == Department.id)
        .where(Employee.is_active == True)
        .options(selectinload(Employee.department))
    )
    if search:
        query = query.where(Employee.full_name.ilike(f"%{search}%"))
    if department_id:
        query = query.where(Employee.department_id == department_id)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar_one()

    result = await db.execute(query.offset(offset).limit(limit))
    employees = result.scalars().all()

    # Загружаем менеджеров
    manager_ids = [e.manager_id for e in employees if e.manager_id]
    managers: dict[int, Employee] = {}
    if manager_ids:
        mgr_result = await db.execute(select(Employee).where(Employee.id.in_(manager_ids)))
        for m in mgr_result.scalars().all():
            managers[m.id] = m

    items = [
        EmployeeShort(
            id=e.id,
            full_name=e.full_name,
            position=e.position,
            grade=e.grade,
            department_id=e.department_id,
            department_name=e.department.name,
            manager_id=e.manager_id,
            manager_name=managers[e.manager_id].full_name if e.manager_id and e.manager_id in managers else None,
        )
        for e in employees
    ]
    return EmployeeListResponse(employees=items, total=total)


@router.get("/employees/{employee_id}", response_model=EmployeeDetail)
async def get_employee(employee_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Employee)
        .where(Employee.id == employee_id)
        .options(selectinload(Employee.department))
    )
    emp = result.scalar_one_or_none()
    if not emp:
        from fastapi import HTTPException
        raise HTTPException(404, "Сотрудник не найден")

    manager = None
    if emp.manager_id:
        mgr_res = await db.execute(select(Employee).where(Employee.id == emp.manager_id))
        manager = mgr_res.scalar_one_or_none()

    # Last quarter goals
    goals_res = await db.execute(
        select(Goal)
        .where(Goal.employee_id == employee_id)
        .order_by(Goal.quarter.desc(), Goal.id.desc())
        .limit(10)
    )
    goals = goals_res.scalars().all()

    return EmployeeDetail(
        id=emp.id,
        full_name=emp.full_name,
        position=emp.position,
        grade=emp.grade,
        department_id=emp.department_id,
        department_name=emp.department.name,
        manager_id=emp.manager_id,
        manager_name=manager.full_name if manager else None,
        goals=[
            GoalShort(
                id=g.id,
                goal_text=g.goal_text,
                weight=g.weight,
                quarter=g.quarter,
                status=g.status,
                smart_index=g.smart_index,
                goal_type=g.goal_type,
            )
            for g in goals
        ],
    )


@router.get("/employees/{employee_id}/goals")
async def get_employee_goals(
    employee_id: int,
    quarter: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Goal).where(Goal.employee_id == employee_id)
    if quarter:
        query = query.where(Goal.quarter == quarter)
    query = query.order_by(Goal.quarter.desc())

    result = await db.execute(query)
    goals = result.scalars().all()
    return [
        GoalShort(
            id=g.id,
            goal_text=g.goal_text,
            weight=g.weight,
            quarter=g.quarter,
            status=g.status,
            smart_index=g.smart_index,
            goal_type=g.goal_type,
        )
        for g in goals
    ]


@router.get("/departments")
async def list_departments(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Department).order_by(Department.name))
    depts = result.scalars().all()
    return [{"id": d.id, "name": d.name, "code": d.code} for d in depts]


@router.get("/kpi/{department_id}")
async def get_department_kpi(department_id: int, db: AsyncSession = Depends(get_db)):
    from app.models import KpiTimeseries
    result = await db.execute(
        select(KpiTimeseries)
        .where(KpiTimeseries.department_id == department_id)
        .order_by(KpiTimeseries.quarter, KpiTimeseries.metric_name)
    )
    kpis = result.scalars().all()
    return [
        {
            "quarter": k.quarter,
            "metric_name": k.metric_name,
            "metric_value": k.metric_value,
            "metric_unit": k.metric_unit,
            "target_value": k.target_value,
            "baseline_value": k.baseline_value,
        }
        for k in kpis
    ]
