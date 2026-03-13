from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Document, Department
from app.core.schemas import DocumentSearchRequest, DocumentSearchResponse, DocumentChunk

router = APIRouter()


@router.post("/documents/search", response_model=DocumentSearchResponse)
async def search_documents(
    request: DocumentSearchRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        from app.services.vector_store import get_vector_store
        from app.services.document_indexer import get_embedder

        embedder = get_embedder()
        embedding = embedder.encode([request.query], normalize_embeddings=True)[0].tolist()

        vs = await get_vector_store()

        where_filter = None
        if request.department_id or request.doc_type:
            conditions = []
            if request.department_id:
                conditions.append({"department_id": {"$eq": request.department_id}})
            if request.doc_type:
                conditions.append({"doc_type": {"$eq": request.doc_type}})
            where_filter = {"$and": conditions} if len(conditions) > 1 else conditions[0]

        results = vs.search(embedding, top_k=request.top_k, where=where_filter)

        # Подтягиваем метаданные из БД
        doc_ids = list({r["metadata"]["doc_id"] for r in results})
        docs_res = await db.execute(
            select(Document, Department)
            .outerjoin(Department, Document.department_id == Department.id)
            .where(Document.id.in_(doc_ids))
        )
        docs_map = {doc.id: (doc, dept) for doc, dept in docs_res.all()}

        chunks = []
        for r in results:
            doc_id = r["metadata"]["doc_id"]
            if doc_id in docs_map:
                doc, dept = docs_map[doc_id]
                chunks.append(DocumentChunk(
                    doc_id=doc_id,
                    title=doc.title,
                    doc_type=doc.doc_type,
                    department_name=dept.name if dept else None,
                    chunk_text=r["chunk_text"],
                    relevance_score=r["relevance_score"],
                ))

        return DocumentSearchResponse(
            query=request.query,
            results=chunks,
            total_found=len(chunks),
        )

    except Exception as e:
        # Fallback: полнотекстовый поиск в БД
        query = select(Document, Department).outerjoin(Department, Document.department_id == Department.id)
        if request.department_id:
            query = query.where(Document.department_id == request.department_id)
        if request.doc_type:
            query = query.where(Document.doc_type == request.doc_type)
        query = query.where(Document.content.ilike(f"%{request.query}%")).limit(request.top_k)

        result = await db.execute(query)
        chunks = []
        for doc, dept in result.all():
            # Находим релевантный фрагмент
            content = doc.content
            idx = content.lower().find(request.query.lower())
            if idx >= 0:
                start = max(0, idx - 100)
                end = min(len(content), idx + 300)
                snippet = content[start:end]
            else:
                snippet = content[:400]

            chunks.append(DocumentChunk(
                doc_id=doc.id,
                title=doc.title,
                doc_type=doc.doc_type,
                department_name=dept.name if dept else None,
                chunk_text=snippet,
                relevance_score=0.5,
            ))

        return DocumentSearchResponse(query=request.query, results=chunks, total_found=len(chunks))


@router.get("/documents/{doc_id}")
async def get_document(doc_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Document, Department)
        .outerjoin(Department, Document.department_id == Department.id)
        .where(Document.id == doc_id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Документ не найден")
    doc, dept = row
    return {
        "id": doc.id,
        "title": doc.title,
        "doc_type": doc.doc_type,
        "department_name": dept.name if dept else None,
        "content": doc.content,
        "keywords": doc.keywords,
        "is_active": doc.is_active,
        "effective_date": doc.effective_date.isoformat() if doc.effective_date else None,
        "created_at": doc.created_at.isoformat(),
    }
