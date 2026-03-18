import asyncio
from app.core.embeddings import get_embedder
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models import Document, Department

async def test_azure_only():
    embedder = get_embedder()
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
        print(f"Embedding doc 8: {doc.title}...")
        texts = [doc.content]
        embeddings = embedder.encode(texts)
        print(f"Successfully embedded. Shape: {len(embeddings[0])}")

if __name__ == "__main__":
    asyncio.run(test_azure_only())
