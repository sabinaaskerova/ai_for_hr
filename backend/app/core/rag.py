"""RAG pipeline: embedding + ChromaDB search + context formatting."""
import logging
from typing import Optional

log = logging.getLogger(__name__)

_embedder = None


def get_embedder():
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer
        from app.config import settings
        _embedder = SentenceTransformer(settings.bge_model_name)
    return _embedder


async def retrieve_context(
    query: str,
    department_id: Optional[int] = None,
    doc_types: Optional[list[str]] = None,
    top_k: int = 5,
) -> list[dict]:
    """
    RAG retrieval:
    1. Embed query с BGE-M3
    2. ChromaDB cosine search
    3. Optional metadata filter по department + doc_type
    """
    try:
        from app.services.vector_store import get_vector_store

        embedder = get_embedder()
        embedding = embedder.encode([query], normalize_embeddings=True)[0].tolist()

        vs = await get_vector_store()

        if vs.count() == 0:
            log.warning("ChromaDB пуст — fallback на пустой контекст")
            return []

        # Строим metadata filter
        where_filter = None
        conditions = []
        if department_id:
            conditions.append({
                "$or": [
                    {"department_id": {"$eq": department_id}},
                    {"department_id": {"$eq": 0}},  # общие документы
                ]
            })
        if doc_types:
            conditions.append({"doc_type": {"$in": doc_types}})

        if len(conditions) == 1:
            where_filter = conditions[0]
        elif len(conditions) > 1:
            where_filter = {"$and": conditions}

        results = vs.search(embedding, top_k=top_k, where=where_filter)
        return results

    except Exception as e:
        log.error(f"RAG retrieval ошибка: {e}")
        return []


async def retrieve_for_evaluation(
    goal_text: str,
    department_id: Optional[int] = None,
) -> list[dict]:
    """RAG для оценки целей: приоритет на KPI-фреймворки и политики."""
    return await retrieve_context(
        query=goal_text,
        department_id=department_id,
        doc_types=["kpi_framework", "policy", "strategy", "regulation"],
        top_k=3,
    )


async def retrieve_for_generation(
    position: str,
    department: str,
    quarter: str,
    focus_priorities: Optional[str],
    department_id: Optional[int] = None,
) -> list[dict]:
    """RAG для генерации целей: полный контекст по должности и квартальным приоритетам."""
    query = f"{position} {department} {quarter}"
    if focus_priorities:
        query += f" {focus_priorities}"

    return await retrieve_context(
        query=query,
        department_id=department_id,
        doc_types=["strategy", "kpi_framework", "policy", "regulation"],
        top_k=5,
    )
