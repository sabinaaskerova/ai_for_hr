"""Chunking + embedding ВНД → ChromaDB."""
import logging
import re
import uuid
from typing import Optional

log = logging.getLogger(__name__)

_embedder = None


from app.core.embeddings import get_embedder


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
    if not content:
        return []
    if len(content) <= max_size:
        return [("", content.strip())]

    chunks = []
    start = 0
    while start < len(content):
        end = min(start + max_size, len(content))
        if end < len(content):
            boundary = content.rfind("\n\n", start, end)
            if boundary > start + overlap:
                end = boundary
        
        chunk_text = content[start:end].strip()
        if chunk_text:
            chunks.append(("", chunk_text))
            
        if end >= len(content):
            break
            
        start = end - overlap
        # Prevent infinite loop if start doesn't progress
        if start <= 0 and end > 0:
            # Should not happen with valid max_size/overlap but be safe
            break
    return chunks


async def index_all_documents(limit: Optional[int] = None, offset: Optional[int] = 0):
    """Индексируем все документы из БД в ChromaDB с поддержкой лимита."""
    from app.database import AsyncSessionLocal
    from app.models import Document, Department
    from sqlalchemy import select
    from app.services.vector_store import get_vector_store

    vs = await get_vector_store()
    # Skip existence check here to allow partial indexing with offset/limit

    embedder = get_embedder()

    async with AsyncSessionLocal() as session:
        # Load all IDs first to avoid keeping a large stream open
        query = (
            select(Document.id)
            .where(Document.is_active == True)
            .order_by(Document.id)
        )
        if limit:
            query = query.limit(limit)
        if offset:
            query = query.offset(offset)
            
        result = await session.execute(query)
        doc_ids = [r[0] for r in result.all()]

    log.info(f"Найдено {len(doc_ids)} документов для индексации...")
    
    total_chunks = 0
    import gc
    for doc_id in doc_ids:
        try:
            # Fresh connection for each document to really clear memory
            async with AsyncSessionLocal() as session:
                res = await session.execute(
                    select(Document, Department)
                    .outerjoin(Department, Document.department_id == Department.id)
                    .where(Document.id == doc_id)
                )
                row = res.one_or_none()
                if not row:
                    continue
                doc, dept = row
                
                log.info(f"Документ ID={doc.id}: '{doc.title[:50]}...'")
                chunks = chunk_document(
                    content=doc.content,
                    title=doc.title,
                    doc_id=doc.id,
                    doc_type=doc.doc_type,
                    department_id=doc.department_id,
                    department_name=dept.name if dept else None,
                )
                
                if not chunks:
                    log.info(f"  Чанков нет, пропускаем.")
                    continue
                
                log.info(f"  Разбито на {len(chunks)} чанков. Индексируем...")
                    
                BATCH = 20 
                for i in range(0, len(chunks), BATCH):
                    batch = chunks[i:i + BATCH]
                    texts = [c["text"] for c in batch]
                    embeddings = embedder.encode(
                        texts, 
                        normalize_embeddings=True,
                        batch_size=BATCH,
                        show_progress_bar=False
                    )
                    for chunk, emb in zip(batch, embeddings):
                        chunk["embedding"] = emb.tolist()
                    vs.add_chunks(batch)
                    
                total_chunks += len(chunks)
                log.info(f"  Готово (ID={doc_id})")
        except Exception as e:
            log.error(f"Ошибка при обработке документа {doc_id}: {e}")
            
        gc.collect()

    log.info(f"Индексация завершена. Всего чанков: {vs.count()}")


async def index_one_document(doc_id: int) -> None:
    """Инкрементальное обновление: пересчитывает эмбеддинги только для одного документа."""
    from app.database import AsyncSessionLocal
    from app.models import Document, Department
    from sqlalchemy import select
    from app.services.vector_store import get_vector_store

    vs = await get_vector_store()
    vs.delete_chunks_by_doc_id(doc_id)

    embedder = get_embedder()

    async with AsyncSessionLocal() as session:
        res = await session.execute(
            select(Document, Department)
            .outerjoin(Department, Document.department_id == Department.id)
            .where(Document.id == doc_id)
        )
        row = res.one_or_none()

    if not row:
        log.info(f"index_one_document: документ id={doc_id} не найден, чанки удалены")
        return

    doc, dept = row
    if not doc.is_active:
        log.info(f"index_one_document: документ id={doc_id} неактивен, пропускаем")
        return

    chunks = chunk_document(
        content=doc.content,
        title=doc.title,
        doc_id=doc.id,
        doc_type=doc.doc_type,
        department_id=doc.department_id,
        department_name=dept.name if dept else None,
    )

    if not chunks:
        log.info(f"index_one_document: нет чанков для doc_id={doc_id}")
        return

    BATCH = 20
    for i in range(0, len(chunks), BATCH):
        batch = chunks[i:i + BATCH]
        texts = [c["text"] for c in batch]
        embeddings = embedder.encode(texts, normalize_embeddings=True, batch_size=BATCH, show_progress_bar=False)
        for chunk, emb in zip(batch, embeddings):
            chunk["embedding"] = emb.tolist()
        vs.add_chunks(batch)

    log.info(f"index_one_document: doc_id={doc_id} проиндексирован ({len(chunks)} чанков)")
