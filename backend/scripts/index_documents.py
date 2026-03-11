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
    force = "--force" in sys.argv

    from app.services.vector_store import get_vector_store
    vs = await get_vector_store()

    if vs.count() > 0 and not force:
        print(f"ChromaDB уже содержит {vs.count()} чанков. Используйте --force для переиндексации.")
        return

    if force and vs.count() > 0:
        print("Очищаем коллекцию...")
        from app.services.vector_store import _vector_store
        import chromadb
        from app.config import settings
        client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
        client.delete_collection("vnd_documents")
        print("Коллекция удалена.")

    from app.services.document_indexer import index_all_documents
    await index_all_documents()


if __name__ == "__main__":
    asyncio.run(main())
