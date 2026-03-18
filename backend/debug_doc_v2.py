import asyncio
from app.services.document_indexer import chunk_document
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models import Document, Department
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

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
        print(f"DEBUGGING doc 8: {doc.title} ({len(doc.content)} chars)...")
        content = doc.content
        print(f"Content starts with: {repr(content[:100])}")
        
        # Test section split explicitly
        import re
        patterns = [
            r"^#{1,3}\s+(.+)$",       # ## Заголовок
            r"^(\d+\.\s+[А-ЯA-Z].+)$",  # 1. Заголовок
        ]
        lines = content.split("\n")
        print(f"Total lines: {len(lines)}")
        for i, line in enumerate(lines):
            # print(f"Checking line {i}: {repr(line)}")
            for pattern in patterns:
                # We use re.match here as in original code
                # re.match checks only at the beginning of the string
                try:
                    m = re.match(pattern, line, re.MULTILINE)
                    if m:
                        print(f"Match found at line {i}: {m.group(1)}")
                except Exception as e:
                    print(f"Error matching line {i}: {e}")
        
        # If it reaches here, it didn't OOM during the match loop.
        print("Completed line-by-line regex test")

if __name__ == "__main__":
    asyncio.run(debug_doc_8())
