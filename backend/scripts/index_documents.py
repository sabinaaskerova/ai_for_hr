"""
Скрипт индексации ВНД в ChromaDB.
Запуск: python -m scripts.index_documents [--force]
"""
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

async def main():
    clear = "--clear" in sys.argv
    limit = None
    offset = 0
    for arg in sys.argv:
        if arg.startswith("--limit="):
            limit = int(arg.split("=")[1])
        if arg.startswith("--offset="):
            offset = int(arg.split("=")[1])

    from app.services.vector_store import get_vector_store
    vs = await get_vector_store()
    if clear:
        print("Очищаем коллекцию...")
        vs.clear_collection()
        print("Коллекция очищена.")

    from app.services.document_indexer import index_all_documents
    await index_all_documents(limit=limit, offset=offset)


if __name__ == "__main__":
    asyncio.run(main())
