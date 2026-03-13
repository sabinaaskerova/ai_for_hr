"""
Ручная переиндексация ВНД в ChromaDB.

Использование:
    python -m app.scripts.index_documents              # полная переиндексация
    python -m app.scripts.index_documents --force      # принудительно, даже если коллекция не пуста
    python -m app.scripts.index_documents --status     # только показать статус, без индексации
"""
import asyncio
import argparse
import logging
import sys
from pathlib import Path

# Добавляем backend/ в путь чтобы импорты app.* работали
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)


async def main(force: bool = False, status_only: bool = False):
    from sqlalchemy import select, func
    from app.database import AsyncSessionLocal, create_tables
    from app.models import Document
    from app.services.vector_store import get_vector_store
    from app.services.document_indexer import index_all_documents
    from app.config import settings

    await create_tables()

    vs = await get_vector_store()
    chroma_count = vs.count()

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(func.count()).select_from(Document).where(Document.is_active == True)
        )
        pg_doc_count = result.scalar()

    log.info(f"Модель:  {settings.embedding_model}")
    log.info(f"Коллекция: {vs.collection_name}")
    log.info(f"ChromaDB: {chroma_count} чанков")
    log.info(f"PostgreSQL: {pg_doc_count} активных документов")

    if status_only:
        return

    if chroma_count > 0 and not force:
        log.info("Коллекция не пуста. Используйте --force для принудительной переиндексации.")
        return

    if force and chroma_count > 0:
        log.info("--force: очищаем коллекцию и переиндексируем...")
        vs.clear_collection()

    log.info("Запускаем индексацию...")
    await index_all_documents()
    log.info(f"Готово. Итого чанков: {vs.count()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Переиндексация ВНД в ChromaDB")
    parser.add_argument("--force", action="store_true", help="Очистить коллекцию и переиндексировать заново")
    parser.add_argument("--status", action="store_true", help="Показать статус без индексации")
    args = parser.parse_args()

    asyncio.run(main(force=args.force, status_only=args.status))
