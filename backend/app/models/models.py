from datetime import datetime
from typing import Optional
import enum

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ─── Enums ────────────────────────────────────────────────────────────────────

class GoalStatus(str, enum.Enum):
    draft = "draft"
    submitted = "submitted"
    under_review = "under_review"
    approved = "approved"
    rejected = "rejected"
    revision_requested = "revision_requested"
    closed = "closed"


class GoalType(str, enum.Enum):
    activity_based = "activity-based"
    output_based = "output-based"
    impact_based = "impact-based"


class StrategicLink(str, enum.Enum):
    strategic = "стратегическая"
    functional = "функциональная"
    operational = "операционная"
    none = "нет связки"


class EventType(str, enum.Enum):
    created = "created"
    submitted = "submitted"
    approved = "approved"
    rejected = "rejected"
    revised = "revised"
    review_requested = "review_requested"
    closed = "closed"


class ReviewVerdict(str, enum.Enum):
    approved = "approved"
    needs_revision = "needs_revision"
    rejected = "rejected"


class DocumentType(str, enum.Enum):
    strategy = "strategy"
    kpi_framework = "kpi_framework"
    policy = "policy"
    regulation = "regulation"


class EmployeeGrade(str, enum.Enum):
    junior = "junior"
    middle = "middle"
    senior = "senior"
    lead = "lead"
    manager = "manager"
    director = "director"


# ─── Models ───────────────────────────────────────────────────────────────────

class Department(Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    employees: Mapped[list["Employee"]] = relationship("Employee", back_populates="department")
    documents: Mapped[list["Document"]] = relationship("Document", back_populates="department")
    kpi_timeseries: Mapped[list["KpiTimeseries"]] = relationship("KpiTimeseries", back_populates="department")


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(300), nullable=False)
    position: Mapped[str] = mapped_column(String(300), nullable=False)
    grade: Mapped[str] = mapped_column(
        Enum(EmployeeGrade, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=EmployeeGrade.middle.value,
    )
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), nullable=False)
    manager_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id"), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(300), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    department: Mapped["Department"] = relationship("Department", back_populates="employees")
    manager: Mapped[Optional["Employee"]] = relationship("Employee", remote_side="Employee.id", foreign_keys=[manager_id])
    subordinates: Mapped[list["Employee"]] = relationship("Employee", foreign_keys=[manager_id], back_populates="manager")
    goals: Mapped[list["Goal"]] = relationship("Goal", back_populates="employee", foreign_keys="Goal.employee_id")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    doc_type: Mapped[str] = mapped_column(
        Enum(DocumentType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    department_id: Mapped[Optional[int]] = mapped_column(ForeignKey("departments.id"), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    keywords: Mapped[Optional[list]] = mapped_column(JSON)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    effective_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    department: Mapped[Optional["Department"]] = relationship("Department", back_populates="documents")


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    reviewer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id"), nullable=True)

    goal_text: Mapped[str] = mapped_column(Text, nullable=False)
    metric: Mapped[Optional[str]] = mapped_column(Text)
    deadline: Mapped[Optional[str]] = mapped_column(String(50))
    weight: Mapped[Optional[float]] = mapped_column(Float)

    quarter: Mapped[str] = mapped_column(String(10), nullable=False)  # e.g. "2025-Q1"
    year: Mapped[int] = mapped_column(Integer, nullable=False)

    status: Mapped[str] = mapped_column(
        Enum(GoalStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=GoalStatus.draft.value,
    )
    goal_type: Mapped[Optional[str]] = mapped_column(
        Enum(GoalType, values_callable=lambda x: [e.value for e in x]),
    )
    strategic_link: Mapped[Optional[str]] = mapped_column(
        Enum(StrategicLink, values_callable=lambda x: [e.value for e in x]),
    )

    # SMART scores (1-5 integer each, float aggregate)
    smart_s: Mapped[Optional[float]] = mapped_column(Float)
    smart_m: Mapped[Optional[float]] = mapped_column(Float)
    smart_a: Mapped[Optional[float]] = mapped_column(Float)
    smart_r: Mapped[Optional[float]] = mapped_column(Float)
    smart_t: Mapped[Optional[float]] = mapped_column(Float)
    smart_index: Mapped[Optional[float]] = mapped_column(Float)  # weighted average

    source_document: Mapped[Optional[str]] = mapped_column(String(500))
    source_quote: Mapped[Optional[str]] = mapped_column(Text)

    # Embedding stored in ChromaDB — reference id here
    chroma_id: Mapped[Optional[str]] = mapped_column(String(100))

    is_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    employee: Mapped["Employee"] = relationship("Employee", back_populates="goals", foreign_keys=[employee_id])
    events: Mapped[list["GoalEvent"]] = relationship("GoalEvent", back_populates="goal", cascade="all, delete-orphan")
    reviews: Mapped[list["GoalReview"]] = relationship("GoalReview", back_populates="goal", cascade="all, delete-orphan")


class GoalEvent(Base):
    __tablename__ = "goal_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("goals.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[str] = mapped_column(
        Enum(EventType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    actor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id"), nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(Text)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    goal: Mapped["Goal"] = relationship("Goal", back_populates="events")


class GoalReview(Base):
    __tablename__ = "goal_reviews"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("goals.id", ondelete="CASCADE"), nullable=False)
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    verdict: Mapped[str] = mapped_column(
        Enum(ReviewVerdict, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    comment: Mapped[Optional[str]] = mapped_column(Text)
    smart_feedback: Mapped[Optional[dict]] = mapped_column(JSON)  # per-criterion feedback
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    goal: Mapped["Goal"] = relationship("Goal", back_populates="reviews")


class KpiTimeseries(Base):
    __tablename__ = "kpi_timeseries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), nullable=False)
    quarter: Mapped[str] = mapped_column(String(10), nullable=False)  # e.g. "2025-Q1"
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    metric_name: Mapped[str] = mapped_column(String(300), nullable=False)
    metric_value: Mapped[float] = mapped_column(Float, nullable=False)
    metric_unit: Mapped[Optional[str]] = mapped_column(String(50))
    target_value: Mapped[Optional[float]] = mapped_column(Float)
    baseline_value: Mapped[Optional[float]] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("department_id", "quarter", "metric_name", name="uq_kpi_dept_quarter_metric"),
    )

    department: Mapped["Department"] = relationship("Department", back_populates="kpi_timeseries")
