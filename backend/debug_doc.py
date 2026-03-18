import asyncio
from app.services.document_indexer import chunk_document
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models import Document, Department

async def debug_doc_8():
    async with AsyncSessionLocal() as session:
        res = await session.execute(
            select(Document, Department)
            .outerjoin(Department, Document.department_id == Department.id)
            .where(Document.id == 8)
        )
        row = res.one_or_none()
        if not row:
            print("Doc 8 not found")
            return
        doc, dept = row
        print(f"Chunking doc 8: {doc.title} ({len(doc.content)} chars)...")
        chunks = chunk_document(
            content=doc.content,
            title=doc.title,
            doc_id=doc.id,
            doc_type=doc.doc_type,
            department_id=doc.department_id,
            department_name=dept.name if dept else None,
        )
        print(f"Successfully chunked into {len(chunks)} chunks")

if __name__ == "__main__":
    asyncio.run(debug_doc_8())
