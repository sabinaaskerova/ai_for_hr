"""Pydantic-модели для всех API-ответов."""
from typing import Optional
from pydantic import BaseModel, Field


# ─── SMART Evaluation ─────────────────────────────────────────────────────────

class SmartCriterionResult(BaseModel):
    score: float = Field(..., ge=0.0, le=1.0, description="Оценка критерия 0.0-1.0")
    reasoning: str = Field(..., description="Обоснование оценки")
    recommendation: str = Field(..., description="Конкретная рекомендация по улучшению")


class SmartScores(BaseModel):
    """Плоская модель SMART-оценок в формате ТЗ организаторов (0.0-1.0)."""
    specific: float = Field(..., ge=0.0, le=1.0)
    measurable: float = Field(..., ge=0.0, le=1.0)
    achievable: float = Field(..., ge=0.0, le=1.0)
    relevant: float = Field(..., ge=0.0, le=1.0)
    time_bound: float = Field(..., ge=0.0, le=1.0)


class SmartEvaluationResult(BaseModel):
    """Детальный результат SMART-оценки (для внутреннего использования и фронтенда)."""
    S: SmartCriterionResult
    M: SmartCriterionResult
    A: SmartCriterionResult
    R: SmartCriterionResult
    T: SmartCriterionResult
    smart_index: float = Field(..., ge=0.0, le=1.0, description="Средний SMART-индекс 0.0-1.0")
    goal_type: str = Field(..., description="activity-based / output-based / impact-based")
    goal_type_reasoning: str = Field(..., description="Обоснование типа цели")
    reformulation_suggested: bool = Field(..., description="Рекомендуется переформулировка")
    reformulation_hint: Optional[str] = Field(None, description="Подсказка для переформулировки")


class StrategicLinkResult(BaseModel):
    link_level: str = Field(..., description="стратегическая / функциональная / операционная / нет связки")
    source_type: str = Field(..., description="Тип источника: ВНД / цель руководителя / KPI / нет")
    source_name: Optional[str] = Field(None, description="Название источника связки")
    source_quote: Optional[str] = Field(None, description="Цитата из источника")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Уверенность в оценке связки")
    reasoning: str = Field(..., description="Обоснование")


class EvaluateRequest(BaseModel):
    goal_text: str = Field(..., min_length=5, description="Текст цели")
    position: str = Field(..., description="Должность сотрудника")
    department: str = Field(..., description="Департамент")
    employee_id: Optional[int] = None
    goal_id: Optional[int] = None
    quarter: Optional[str] = Field(None, description="Квартал, напр. '2025-Q1'")


class EvaluateResponse(BaseModel):
    """Ответ оценки в формате ТЗ организаторов + расширенные поля для фронтенда."""
    # ТЗ-формат (обязательные поля)
    goal_id: Optional[int] = None
    goal_text: str
    smart_scores: SmartScores           # плоские оценки 0.0-1.0
    smart_index: float                  # 0.0-1.0
    recommendations: list[str]          # собранные рекомендации по всем критериям
    improved_goal: Optional[str] = None # переформулировка если слабая цель
    achievability_warning: Optional[str] = None  # F-20: предупреждение на основе истории
    # Расширенные поля для фронтенда
    smart_detail: SmartEvaluationResult
    strategic_link: StrategicLinkResult
    cached: bool = False


class BatchGoalInput(BaseModel):
    goal_text: str
    weight: float = Field(..., ge=0, le=100)
    goal_id: Optional[int] = None


class BatchEvaluateRequest(BaseModel):
    employee_id: int
    quarter: str
    goals: list[BatchGoalInput]
    position: str
    department: str


class BatchGoalResult(BaseModel):
    goal_id: Optional[int] = None
    goal_text: str
    weight: float
    smart_scores: SmartScores
    smart_index: float
    recommendations: list[str]
    improved_goal: Optional[str] = None
    smart_detail: SmartEvaluationResult
    strategic_link: StrategicLinkResult


class BatchWarning(BaseModel):
    type: str
    message: str


class BatchEvaluateResponse(BaseModel):
    goals: list[BatchGoalResult]
    warnings: list[BatchWarning]
    overall_smart_index: float
    total_weight: float
    type_distribution: dict[str, int]


# ─── Reformulation ────────────────────────────────────────────────────────────

class ReformulateRequest(BaseModel):
    goal_text: str
    position: str
    department: str
    context: Optional[str] = None


class ReformulateResponse(BaseModel):
    original_goal: str
    reformulated_goal: str
    original_smart_scores: SmartScores
    original_smart_index: float
    reformulated_smart_scores: SmartScores
    reformulated_smart_index: float
    original_smart_detail: SmartEvaluationResult
    reformulated_smart_detail: SmartEvaluationResult
    improvements: list[str]


# ─── Generator ────────────────────────────────────────────────────────────────

class CascadeSource(BaseModel):
    manager_name: str
    manager_goal: str  # текст цели руководителя, от которой каскадирована


class GeneratedGoal(BaseModel):
    goal_text: str
    metric: str
    deadline: str
    weight: int
    source_document: str
    source_quote: str
    goal_type: str
    strategic_link: str
    reasoning: str
    smart_scores: Optional[SmartScores] = None
    smart_index: Optional[float] = None
    requires_review: bool = False
    cascade_from: Optional[CascadeSource] = None  # F-14: источник каскадирования


class GenerateRequest(BaseModel):
    employee_id: int
    quarter: str
    focus_priorities: Optional[str] = Field(None, description="Фокус-приоритеты от пользователя")
    n_goals: int = Field(default=4, ge=3, le=5)


class GenerateResponse(BaseModel):
    employee_id: int
    quarter: str
    goals: list[GeneratedGoal]
    total_weight: int
    warnings: list[str]


# ─── Analytics ────────────────────────────────────────────────────────────────

class DepartmentMetrics(BaseModel):
    department_id: int
    department_name: str
    avg_smart_index: float
    avg_s: float
    avg_m: float
    avg_a: float
    avg_r: float
    avg_t: float
    strategic_link_ratio: float
    impact_goal_ratio: float
    activity_goal_ratio: float
    maturity_index: float
    total_goals: int
    goals_approved: int
    goals_rejected: int


class DashboardResponse(BaseModel):
    overall_smart_index: float
    strategic_link_ratio: float
    impact_goal_ratio: float
    maturity_index: float
    departments: list[DepartmentMetrics]
    weakest_criterion: str
    top_department: str
    bottom_department: str


class TrendPoint(BaseModel):
    quarter: str
    avg_smart_index: float
    strategic_link_ratio: float
    impact_goal_ratio: float


class TrendsResponse(BaseModel):
    department_id: Optional[int]
    trends: list[TrendPoint]


# ─── Documents ────────────────────────────────────────────────────────────────

class DocumentSearchRequest(BaseModel):
    query: str = Field(..., min_length=3)
    department_id: Optional[int] = None
    doc_type: Optional[str] = None
    top_k: int = Field(default=5, ge=1, le=20)


class DocumentChunk(BaseModel):
    doc_id: int
    title: str
    doc_type: str
    department_name: Optional[str]
    chunk_text: str
    relevance_score: float


class DocumentSearchResponse(BaseModel):
    query: str
    results: list[DocumentChunk]
    total_found: int


# ─── Employees ────────────────────────────────────────────────────────────────

class EmployeeShort(BaseModel):
    id: int
    full_name: str
    position: str
    grade: str
    department_id: int
    department_name: str
    manager_id: Optional[int]
    manager_name: Optional[str]

    class Config:
        from_attributes = True


class GoalShort(BaseModel):
    id: int
    goal_text: str
    weight: Optional[float]
    quarter: str
    status: str
    smart_index: Optional[float]
    goal_type: Optional[str]

    class Config:
        from_attributes = True


class EmployeeDetail(EmployeeShort):
    goals: list[GoalShort] = []


class EmployeeListResponse(BaseModel):
    employees: list[EmployeeShort]
    total: int
