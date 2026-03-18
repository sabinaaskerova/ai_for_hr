"""
RAG pipeline: гибридный поиск dense + sparse + RRF + опциональный reranker.

Поток:
  query → embed → ChromaDB top-10 (dense)
         → BM25 top-10 (sparse)
         → RRF fusion → top-5
         → [опционально] bge-reranker-v2-m3 → top-5
"""
import logging
from typing import Optional

log = logging.getLogger(__name__)

# ─── Синглтоны ────────────────────────────────────────────────────────────────

_embedder = None
_reranker = None

# BM25 индекс
_bm25_index = None
_bm25_corpus: list[dict] = []  # [{id, text, metadata}, ...]


# ─── Embedder / Reranker ──────────────────────────────────────────────────────

from app.core.embeddings import get_embedder


def get_reranker():
    global _reranker
    from app.config import settings
    if not settings.use_reranker:
        return None
    if _reranker is None:
        from sentence_transformers import CrossEncoder
        log.info(f"Загружаем reranker {settings.reranker_model}...")
        _reranker = CrossEncoder(settings.reranker_model)
        log.info("Reranker загружен")
    return _reranker


# ─── BM25 индекс ─────────────────────────────────────────────────────────────

async def build_bm25_index() -> None:
    """Строим BM25 индекс из всех чанков ChromaDB. Вызывается при старте."""
    global _bm25_index, _bm25_corpus
    from rank_bm25 import BM25Okapi
    from app.services.vector_store import get_vector_store

    vs = await get_vector_store()
    if vs.count() == 0:
        log.warning("BM25: ChromaDB пуст, индекс не построен")
        return

    result = vs.collection.get(include=["documents", "metadatas"])
    ids = result["ids"]
    docs = result["documents"]
    metas = result["metadatas"]

    _bm25_corpus = [
        {"id": id_, "text": doc, "metadata": meta}
        for id_, doc, meta in zip(ids, docs, metas)
    ]
    tokenized = [doc.lower().split() for doc in docs]
    _bm25_index = BM25Okapi(tokenized)
    log.info(f"BM25 индекс построен: {len(_bm25_corpus)} чанков")


def _bm25_search(query: str, top_k: int = 10) -> list[dict]:
    """Sparse BM25 поиск по всему корпусу."""
    if _bm25_index is None or not _bm25_corpus:
        return []
    scores = _bm25_index.get_scores(query.lower().split())
    top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
    return [
        {
            "chunk_text": _bm25_corpus[i]["text"],
            "metadata": _bm25_corpus[i]["metadata"],
            "distance": 0.0,
            "relevance_score": float(scores[i]),
        }
        for i in top_indices
        if scores[i] > 0
    ]


def _apply_metadata_filter(
    results: list[dict],
    department_id: Optional[int],
    doc_types: Optional[list[str]],
) -> list[dict]:
    """Фильтрует BM25 результаты по department_id и doc_type."""
    filtered = []
    for r in results:
        meta = r.get("metadata", {})
        if department_id is not None:
            dept = meta.get("department_id", 0)
            if dept not in (department_id, 0):
                continue
        if doc_types:
            if meta.get("doc_type") not in doc_types:
                continue
        filtered.append(r)
    return filtered


# ─── RRF ─────────────────────────────────────────────────────────────────────

def _rrf_fusion(dense: list[dict], sparse: list[dict], k: int = 60) -> list[dict]:
    """Reciprocal Rank Fusion: score(d) = sum(1 / (k + rank(d)))"""
    scores: dict[str, float] = {}
    chunks: dict[str, dict] = {}

    for rank, r in enumerate(dense):
        key = r["chunk_text"]
        scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
        chunks[key] = r

    for rank, r in enumerate(sparse):
        key = r["chunk_text"]
        scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
        if key not in chunks:
            chunks[key] = r

    sorted_keys = sorted(scores, key=lambda x: scores[x], reverse=True)
    return [chunks[key] for key in sorted_keys]


# ─── Reranker ─────────────────────────────────────────────────────────────────

def _rerank(query: str, results: list[dict], top_k: int) -> list[dict]:
    """Cross-encoder reranker (включается через USE_RERANKER=true)."""
    reranker = get_reranker()
    if reranker is None or not results:
        return results[:top_k]
    pairs = [(query, r["chunk_text"]) for r in results]
    cross_scores = reranker.predict(pairs)
    reranked = sorted(zip(results, cross_scores), key=lambda x: x[1], reverse=True)
    log.debug(f"Reranker: {len(results)} → {top_k}")
    return [r for r, _ in reranked[:top_k]]


# ─── Основной pipeline ────────────────────────────────────────────────────────

async def retrieve_context(
    query: str,
    department_id: Optional[int] = None,
    doc_types: Optional[list[str]] = None,
    top_k: int = 5,
) -> list[dict]:
    """
    Гибридный RAG retrieval:
      1. Dense:  ChromaDB cosine top-10
      2. Sparse: BM25 top-10 (с metadata filter)
      3. RRF fusion
      4. [USE_RERANKER=true] bge-reranker-v2-m3 rerank
      → top_k результатов
    """
    try:
        from app.services.vector_store import get_vector_store

        embedder = get_embedder()
        embedding = embedder.encode([query], normalize_embeddings=True)[0].tolist()
        vs = await get_vector_store()

        if vs.count() == 0:
            log.warning("ChromaDB пуст — fallback на пустой контекст")
            return []

        # Metadata filter для dense поиска
        where_filter = None
        conditions = []
        if department_id:
            conditions.append({
                "$or": [
                    {"department_id": {"$eq": department_id}},
                    {"department_id": {"$eq": 0}},
                ]
            })
        if doc_types:
            conditions.append({"doc_type": {"$in": doc_types}})
        if len(conditions) == 1:
            where_filter = conditions[0]
        elif len(conditions) > 1:
            where_filter = {"$and": conditions}

        # 1. Dense search (top-10)
        dense_results = vs.search(embedding, top_k=10, where=where_filter)

        # 2. Sparse BM25 search (top-10) + metadata filter
        sparse_raw = _bm25_search(query, top_k=10)
        sparse_results = _apply_metadata_filter(sparse_raw, department_id, doc_types)

        # 3. RRF fusion
        fused = _rrf_fusion(dense_results, sparse_results)

        # 4. Optional rerank → top_k
        final = _rerank(query, fused, top_k)

        log.debug(
            f"RAG hybrid: dense={len(dense_results)}, sparse={len(sparse_results)}, "
            f"fused={len(fused)}, final={len(final)}"
        )
        return final

    except Exception as e:
        log.error(f"RAG retrieval ошибка: {e}")
        return []


# ─── Удобные обёртки ──────────────────────────────────────────────────────────

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
    """RAG для генерации целей: полный контекст по должности и приоритетам."""
    query = f"{position} {department} {quarter}"
    if focus_priorities:
        query += f" {focus_priorities}"
    return await retrieve_context(
        query=query,
        department_id=department_id,
        doc_types=["strategy", "kpi_framework", "policy", "regulation"],
        top_k=5,
    )
