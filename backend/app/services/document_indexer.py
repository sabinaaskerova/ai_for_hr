"""Chunking + embedding ВНД → ChromaDB."""
import logging
import re
import uuid
from typing import Optional

log = logging.getLogger(__name__)

_embedder = None


def get_embedder():
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer
        from app.config import settings
        log.info(f"Загружаем модель {settings.embedding_model}...")
        _embedder = SentenceTransformer(settings.embedding_model)
        log.info("Модель загружена")
    return _embedder


def chunk_document(
    content: str,
    title: str,
    doc_id: int,
    doc_type: str,
    department_id: Optional[int],
    department_name: Optional[str],
    max_chunk_size: int = 800,
    overlap: int = 200,
) -> list[dict]:
    """
    Чанкование документа:
    1. Попытка разбить по секциям (## или нумерованные пункты)
    2. Fallback: рекурсивный сплиттер по символам
    Каждый чанк имеет prefix: заголовок документа + заголовок раздела
    """
    chunks = _section_split(content, title)

    if not chunks:
        chunks = _recursive_split(content, max_chunk_size, overlap)

    result = []
    for i, (section_title, chunk_text) in enumerate(chunks):
        prefix = f"{title}"
        if section_title and section_title != title:
            prefix += f" | {section_title}"
        full_text = f"{prefix}\n\n{chunk_text}"

        result.append({
            "id": f"doc_{doc_id}_chunk_{i}",
            "text": full_text,
            "metadata": {
                "doc_id": doc_id,
                "title": title,
                "section_title": section_title or "",
                "doc_type": doc_type,
                "department_id": department_id or 0,
                "department_name": department_name or "Общий",
            },
        })
    return result


def _section_split(content: str, doc_title: str) -> list[tuple[str, str]]:
    """Разбивает по маркдаун-заголовкам ## или нумерованным пунктам."""
    # Паттерны для разделителей секций
    patterns = [
        r"^#{1,3}\s+(.+)$",       # ## Заголовок
        r"^(\d+\.\s+[А-ЯA-Z].+)$",  # 1. Заголовок
    ]

    lines = content.split("\n")
    sections = []
    current_title = doc_title
    current_lines = []

    for line in lines:
        is_header = False
        for pattern in patterns:
            m = re.match(pattern, line, re.MULTILINE)
            if m:
                if current_lines:
                    text = "\n".join(current_lines).strip()
                    if len(text) > 50:
                        sections.append((current_title, text))
                current_title = m.group(1).strip().lstrip("#").strip()
                current_lines = []
                is_header = True
                break
        if not is_header:
            current_lines.append(line)

    if current_lines:
        text = "\n".join(current_lines).strip()
        if len(text) > 50:
            sections.append((current_title, text))

    return sections if len(sections) > 1 else []


def _recursive_split(content: str, max_size: int, overlap: int) -> list[tuple[str, str]]:
    """Простой рекурсивный сплиттер."""
    chunks = []
    start = 0
    while start < len(content):
        end = min(start + max_size, len(content))
        # Ищем ближайший разрыв абзаца
        if end < len(content):
            boundary = content.rfind("\n\n", start, end)
            if boundary > start + overlap:
                end = boundary
        chunks.append(("", content[start:end].strip()))
        start = end - overlap
        if start >= len(content):
            break
    return chunks


async def index_all_documents(db=None):
    """Индексируем все документы из БД в ChromaDB."""
    from app.database import AsyncSessionLocal
    from app.models import Document, Department
    from sqlalchemy import select
    from app.services.vector_store import get_vector_store

    vs = await get_vector_store()
    if vs.count() > 0:
        log.info(f"ChromaDB уже содержит {vs.count()} чанков. Пропускаем индексацию.")
        return

    embedder = get_embedder()

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Document, Department)
            .outerjoin(Department, Document.department_id == Department.id)
            .where(Document.is_active == True)
        )
        rows = result.all()

    log.info(f"Индексируем {len(rows)} документов...")
    all_chunks = []

    for doc, dept in rows:
        chunks = chunk_document(
            content=doc.content,
            title=doc.title,
            doc_id=doc.id,
            doc_type=doc.doc_type,
            department_id=doc.department_id,
            department_name=dept.name if dept else None,
        )
        for chunk in chunks:
            all_chunks.append(chunk)

    # Batch embedding
    BATCH = 32
    for i in range(0, len(all_chunks), BATCH):
        batch = all_chunks[i:i + BATCH]
        texts = [c["text"] for c in batch]
        embeddings = embedder.encode(texts, normalize_embeddings=True).tolist()
        for chunk, emb in zip(batch, embeddings):
            chunk["embedding"] = emb
        vs.add_chunks(batch)
        log.info(f"  Проиндексировано {min(i + BATCH, len(all_chunks))}/{len(all_chunks)} чанков")

    log.info(f"Индексация завершена. Всего чанков: {vs.count()}")
