"""
Импорт данных из каталога hackathon_db в локальную PostgreSQL.

Запуск:
    python -m scripts.import_hackathon_data --data-dir ../../hackathon_db
"""
from __future__ import annotations

import argparse
import asyncio
import ast
import csv
import json
import logging
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text, update

# Добавляем корень backend для импорта app.*
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database import AsyncSessionLocal, create_tables
from app.models import Department, Document, Employee, Goal, GoalEvent, GoalReview, KpiTimeseries
from app.models.models import (
    DocumentType,
    EmployeeGrade,
    EventType,
    GoalStatus,
    ReviewVerdict,
)

log = logging.getLogger("import_hackathon_data")

DEFAULT_DATA_ROOT = Path(__file__).resolve().parents[2] / "hackathon_db"


# ─── HELPERS ──────────────────────────────────────────────────────────────────


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    dt = datetime.fromisoformat(value.replace(" ", "T"))
    if dt.tzinfo:
        return dt.replace(tzinfo=None)
    return dt


def parse_bool(value: str | None) -> bool:
    return (value or "").lower() in {"t", "true", "1", "yes"}


def parse_int(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def parse_float(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def compose_quarter(year: str | None, quarter: str | None) -> str:
    year = (year or "").strip()
    quarter = (quarter or "").strip()
    if year and quarter:
        return f"{year}-{quarter}"
    return quarter or year or "unknown"


def quarter_from_date(date_value: str | None) -> tuple[str, int]:
    if not date_value:
        return ("unknown", 0)
    dt = datetime.fromisoformat(date_value)
    quarter = (dt.month - 1) // 3 + 1
    return (f"{dt.year}-Q{quarter}", dt.year)


def collect_braced_field(row: list[str], start_idx: int) -> tuple[str, int]:
    """
    Склеивает поле CSV, которое содержит JSON/array и разрезалось на несколько колонок.
    Возвращает (значение, следующий индекс).
    """
    total = len(row)
    if start_idx >= total:
        return ("", total)

    first = row[start_idx]
    if not first:
        return ("", start_idx + 1)

    parts = [first]
    idx = start_idx

    if first.endswith('}"'):
        return (first, idx + 1)

    while idx + 1 < total:
        idx += 1
        parts.append(row[idx])
        if parts[-1].endswith('}"'):
            break

    return (",".join(parts), idx + 1)


JSON_KEY_FIX = re.compile(r"'([^']+)'\":")
JSON_QUOTED_VALUE = re.compile(r"'\"([^']+)\"'")
JSON_LEADING_DOUBLE = re.compile(r'"([A-Za-z0-9_]+)')


def parse_loose_json(raw: str) -> Any | None:
    """
    Большинство JSON-полей выгружены в виде {'key'": '"value"'}. Приводим к нормальному виду.
    """
    if not raw:
        return None

    text = raw.strip().strip('"').strip()
    if not text:
        return None

    text = text.replace('"\'', "'").replace('\'"', "'")
    text = JSON_KEY_FIX.sub(r"'\1':", text)
    text = JSON_QUOTED_VALUE.sub(r"'\1'", text)
    text = JSON_LEADING_DOUBLE.sub(r"\1", text)
    text = text.replace('\\"', '"')
    text = re.sub(r"\btrue\b", "True", text)
    text = re.sub(r"\bfalse\b", "False", text)
    text = re.sub(r"\bnull\b", "None", text)

    try:
        return ast.literal_eval(text)
    except Exception:
        log.debug("Не удалось распарсить JSON: %s", raw)
        return None


def parse_pg_array(raw: str) -> list[str]:
    if not raw:
        return []

    text = raw.strip().strip('"').strip()
    if not text or not text.startswith("{") or not text.endswith("}"):
        return [text] if text else []

    inner = text[1:-1]
    result: list[str] = []
    current = []
    in_quotes = False

    for ch in inner:
        if ch == '"':
            in_quotes = not in_quotes
            continue
        if ch == "," and not in_quotes:
            value = "".join(current).strip()
            if value:
                result.append(value)
            current = []
        else:
            current.append(ch)

    tail = "".join(current).strip()
    if tail:
        result.append(tail)

    clean = [item.strip("' ") for item in result if item.strip("' ")]
    return clean


def load_positions(path: Path) -> dict[int, tuple[str, str]]:
    mapping: dict[int, tuple[str, str]] = {}
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        for row in reader:
            if not row:
                continue
            pos_id = parse_int(row[0])
            if not pos_id:
                continue
            mapping[pos_id] = (row[1], row[2])
    return mapping


async def purge_tables(session):
    await session.execute(
        text(
            "TRUNCATE TABLE goal_events, goal_reviews, goals, documents, employees, "
            "departments, kpi_timeseries RESTART IDENTITY CASCADE"
        )
    )


# ─── IMPORTERS ────────────────────────────────────────────────────────────────


async def import_departments(session, path: Path) -> int:
    items: list[Department] = []
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        for row in reader:
            if not row:
                continue
            dep_id = parse_int(row[0])
            if not dep_id:
                continue
            items.append(
                Department(
                    id=dep_id,
                    name=row[1].strip(),
                    code=(row[2] or f"D{dep_id}").strip(),
                    description=None,
                    created_at=parse_datetime(row[5]),
                )
            )
    session.add_all(items)
    return len(items)


async def import_employees(session, path: Path, positions: dict[int, tuple[str, str]]) -> tuple[int, list[tuple[int, int]]]:
    items: list[Employee] = []
    manager_links: list[tuple[int, int]] = []
    all_employee_ids: set[int] = set()
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        for row in reader:
            if not row:
                continue
            emp_id = parse_int(row[0])
            if not emp_id:
                continue
            all_employee_ids.add(emp_id)

            position_name = ""
            grade_value = "middle"
            pos_id = parse_int(row[5])
            if pos_id and pos_id in positions:
                position_name, grade_value = positions[pos_id]

            try:
                grade = EmployeeGrade(grade_value)
            except ValueError:
                grade = EmployeeGrade.middle

            manager_id = parse_int(row[6])
            if manager_id and manager_id != emp_id:
                manager_links.append((emp_id, manager_id))

            items.append(
                Employee(
                    id=emp_id,
                    full_name=row[2].strip(),
                    email=row[3].strip() or None,
                    department_id=parse_int(row[4]) or 1,
                    position=position_name or "Не указана",
                    grade=grade.value,
                    manager_id=None,
                    is_active=parse_bool(row[8]),
                    created_at=parse_datetime(row[9]),
                )
            )
    session.add_all(items)

    await session.flush()

    # После вставки обновляем manager_id, чтобы избежать FK violation
    for emp_id, manager_id in manager_links:
        if manager_id not in all_employee_ids:
            continue
        await session.execute(
            update(Employee).where(Employee.id == emp_id).values(manager_id=manager_id)
        )

    return len(items), manager_links


DOC_TYPE_MAP = {
    "strategy": DocumentType.strategy.value,
    "kpi_framework": DocumentType.kpi_framework.value,
    "policy": DocumentType.policy.value,
    "regulation": DocumentType.regulation.value,
    "instruction": DocumentType.regulation.value,
    "standard": DocumentType.regulation.value,
    "vnd": DocumentType.regulation.value,
}


async def import_documents(session, path: Path) -> int:
    items: list[Document] = []
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        for row in reader:
            if len(row) < 10:
                continue

            doc_type_raw = row[1].strip()
            mapped_type = DOC_TYPE_MAP.get(doc_type_raw, DocumentType.policy.value)

            idx = 7
            metadata_raw, idx = collect_braced_field(row, idx)
            keywords_raw, idx = collect_braced_field(row, idx)
            version = row[idx] if idx < len(row) else ""
            is_active = row[idx + 1] if idx + 1 < len(row) else ""
            created_at = row[idx + 2] if idx + 2 < len(row) else ""

            metadata_json = parse_loose_json(metadata_raw)
            keywords_list = parse_pg_array(keywords_raw)

            department_id = parse_int(row[6])
            if not department_id and isinstance(metadata_json, dict):
                department_ids = metadata_json.get("department_ids")
                if isinstance(department_ids, list) and department_ids:
                    department_id = department_ids[0]

            items.append(
                Document(
                    title=row[2].strip(),
                    doc_type=mapped_type,
                    department_id=department_id,
                    content=row[3].strip(),
                    keywords=keywords_list if keywords_list else None,
                    effective_date=parse_datetime(row[4]),
                    is_active=parse_bool(is_active),
                    created_at=parse_datetime(created_at),
                )
            )
    session.add_all(items)
    return len(items)


def load_kpi_catalog(path: Path) -> dict[str, tuple[str, str]]:
    mapping: dict[str, tuple[str, str]] = {}
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        for row in reader:
            if not row:
                continue
            code = row[0].strip()
            mapping[code] = (row[1].strip(), row[2].strip())
    return mapping


async def import_kpis(session, ts_path: Path, catalog: dict[str, tuple[str, str]]) -> int:
    # Use dict to deduplicate by (department_id, quarter, metric_name)
    seen: dict[tuple, dict] = {}
    with ts_path.open(encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        for row in reader:
            if not row or row[1] != "department":
                continue
            dept_id = parse_int(row[2])
            if not dept_id:
                continue
            metric_code = row[6].strip()
            quarter_label, year = quarter_from_date(row[7])
            metric_value = parse_float(row[8])
            unit = catalog.get(metric_code, ("", ""))[1] or None

            key = (dept_id, quarter_label, metric_code)
            seen[key] = dict(
                department_id=dept_id,
                quarter=quarter_label,
                year=year,
                metric_name=metric_code,
                metric_value=metric_value or 0.0,
                metric_unit=unit,
                created_at=parse_datetime(row[-1]),
            )

    items = [KpiTimeseries(**vals) for vals in seen.values()]
    session.add_all(items)
    return len(items)


GOAL_STATUS_MAP = {
    "draft": GoalStatus.draft.value,
    "submitted": GoalStatus.submitted.value,
    "approved": GoalStatus.approved.value,
    "in_progress": GoalStatus.under_review.value,
    "done": GoalStatus.closed.value,
    "cancelled": GoalStatus.rejected.value,
}


def build_goal_metadata(project_id: str | None, system_id: str | None) -> str | None:
    payload = {}
    if project_id:
        payload["project_id"] = project_id
    if system_id:
        payload["system_id"] = system_id
    if not payload:
        return None
    import json

    return json.dumps(payload, ensure_ascii=False)


async def import_goals(session, path: Path, catalog: dict[str, tuple[str, str]], limit: int | None) -> dict[str, int]:
    goal_map: dict[str, int] = {}
    items: list[Goal] = []
    next_id = 1

    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        for idx, row in enumerate(reader):
            if limit and idx >= limit:
                break
            goal_uuid = row[0]
            department_id = parse_int(row[1]) or 1
            employee_id = parse_int(row[2])
            if not employee_id:
                continue
            metric_code = row[11].strip() or None
            metric_name = None
            if metric_code:
                metric_name = catalog.get(metric_code, (metric_code, ""))[0]

            goal_id = next_id
            next_id += 1
            goal_map[goal_uuid] = goal_id

            items.append(
                Goal(
                    id=goal_id,
                    employee_id=employee_id,
                    reviewer_id=None,
                    goal_text=row[8].strip(),
                    metric=metric_name,
                    deadline=row[12].strip() or None,
                    weight=parse_float(row[13]),
                    quarter=compose_quarter(row[9], row[10]),
                    year=parse_int(row[9]) or 0,
                    status=GOAL_STATUS_MAP.get(row[14], GoalStatus.draft.value),
                    smart_index=parse_float(row[16]),
                    source_document=row[15].strip() or None,
                    source_quote=build_goal_metadata(row[6].strip() or None, row[7].strip() or None),
                    is_generated=False,
                    created_at=parse_datetime(row[17]),
                    updated_at=parse_datetime(row[18]),
                )
            )

    session.add_all(items)
    return goal_map


EVENT_TYPE_MAP = {
    "created": EventType.created.value,
    "submitted": EventType.submitted.value,
    "approved": EventType.approved.value,
    "edited": EventType.revised.value,
    "status_changed": EventType.review_requested.value,
}


async def import_goal_events(session, path: Path, goal_map: dict[str, int]) -> int:
    items: list[GoalEvent] = []
    next_id = 1
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        for row in reader:
            goal_uuid = row[1]
            goal_id = goal_map.get(goal_uuid)
            if not goal_id:
                continue

            payload_before = row[6].strip() or None
            payload_after = row[7].strip() or None
            comment = payload_after or payload_before
            meta_raw, _ = collect_braced_field(row, 8)
            metadata = parse_loose_json(meta_raw) or {}
            if not isinstance(metadata, dict):
                metadata = {"raw": metadata}
            if row[2] not in EVENT_TYPE_MAP:
                metadata["original_event_type"] = row[2]
            metadata["from_status"] = row[4] or None
            metadata["to_status"] = row[5] or None
            if payload_before and payload_after and payload_before != payload_after:
                metadata["payload_before"] = payload_before
                metadata["payload_after"] = payload_after

            items.append(
                GoalEvent(
                    id=next_id,
                    goal_id=goal_id,
                    event_type=EVENT_TYPE_MAP.get(row[2], EventType.review_requested.value),
                    actor_id=parse_int(row[3]),
                    comment=comment,
                    metadata_json=metadata or None,
                    created_at=parse_datetime(row[-1]),
                )
            )
            next_id += 1

    session.add_all(items)
    return len(items)


REVIEW_VERDICT_MAP = {
    "approve": ReviewVerdict.approved.value,
    "needs_changes": ReviewVerdict.needs_revision.value,
    "comment_only": ReviewVerdict.needs_revision.value,
}


async def import_goal_reviews(session, path: Path, goal_map: dict[str, int]) -> int:
    items: list[GoalReview] = []
    next_id = 1
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        for row in reader:
            goal_id = goal_map.get(row[1])
            reviewer_id = parse_int(row[2])
            if not goal_id or not reviewer_id:
                continue

            items.append(
                GoalReview(
                    id=next_id,
                    goal_id=goal_id,
                    reviewer_id=reviewer_id,
                    verdict=REVIEW_VERDICT_MAP.get(row[3], ReviewVerdict.needs_revision.value),
                    comment=row[4].strip() or None,
                    created_at=parse_datetime(row[5]),
                )
            )
            next_id += 1

    session.add_all(items)
    return len(items)


# ─── CLI ──────────────────────────────────────────────────────────────────────


@dataclass
class ImportResult:
    departments: int = 0
    employees: int = 0
    documents: int = 0
    kpis: int = 0
    goals: int = 0
    events: int = 0
    reviews: int = 0


async def run(data_dir: Path, skip_truncate: bool, limit_goals: int | None) -> ImportResult:
    data_dir = data_dir.resolve()
    if not data_dir.exists():
        raise FileNotFoundError(f"Каталог с данными не найден: {data_dir}")

    await create_tables()

    result = ImportResult()
    async with AsyncSessionLocal() as session:
        if not skip_truncate:
            log.info("Очищаем таблицы...")
            await purge_tables(session)

        positions = load_positions(data_dir / "positions.csv")
        catalog = load_kpi_catalog(data_dir / "kpi_catalog.csv")

        log.info("Импорт департаментов...")
        result.departments = await import_departments(session, data_dir / "departments.csv")

        log.info("Импорт сотрудников...")
        result.employees, _ = await import_employees(session, data_dir / "employees.csv", positions)

        log.info("Импорт документов...")
        result.documents = await import_documents(session, data_dir / "documents.csv")

        log.info("Импорт KPI timeseries...")
        result.kpis = await import_kpis(session, data_dir / "kpi_timeseries.csv", catalog)

        log.info("Импорт целей...")
        goal_map = await import_goals(session, data_dir / "goals.csv", catalog, limit_goals)
        result.goals = len(goal_map)

        log.info("Импорт событий целей...")
        result.events = await import_goal_events(session, data_dir / "goal_events.csv", goal_map)

        log.info("Импорт ревью целей...")
        result.reviews = await import_goal_reviews(session, data_dir / "goal_reviews.csv", goal_map)

        await session.commit()

    return result


async def import_data(
    data_dir: Path | str | None = None,
    skip_truncate: bool = False,
    limit_goals: int | None = None,
) -> ImportResult:
    target_dir = Path(data_dir) if data_dir else DEFAULT_DATA_ROOT
    return await run(target_dir, skip_truncate=skip_truncate, limit_goals=limit_goals)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Импорт данных hackathon_db в PostgreSQL")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_ROOT,
        help="Путь к каталогу с CSV (по умолчанию ../../hackathon_db)",
    )
    parser.add_argument("--skip-truncate", action="store_true", help="Не делать TRUNCATE таблиц перед импортом")
    parser.add_argument("--limit-goals", type=int, help="Ограничить количество импортируемых целей (для отладки)")
    return parser


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = build_parser()
    args = parser.parse_args()
    result = asyncio.run(
        import_data(
            data_dir=args.data_dir,
            skip_truncate=args.skip_truncate,
            limit_goals=args.limit_goals,
        )
    )
    log.info(
        "Готово. Департаментов=%s, сотрудников=%s, документов=%s, KPI=%s, целей=%s, событий=%s, ревью=%s",
        result.departments,
        result.employees,
        result.documents,
        result.kpis,
        result.goals,
        result.events,
        result.reviews,
    )


if __name__ == "__main__":
    main()
