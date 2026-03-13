import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import create_tables

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
log = logging.getLogger(__name__)

app = FastAPI(
    title="HR Goals AI",
    description="AI-модуль оценки и генерации целей сотрудников (КМГ-Кумколь)",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    log.info("Создание таблиц БД...")
    await create_tables()

    # Seed data if employees table is empty
    try:
        import sys
        import os
        _scripts_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
        if _scripts_dir not in sys.path:
            sys.path.insert(0, _scripts_dir)

        from app.database import AsyncSessionLocal
        from app.models import Employee
        from sqlalchemy import select, func
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(func.count()).select_from(Employee))
            emp_count = result.scalar()
            if not emp_count:
                log.info("Таблица employees пуста. Запускаем seed...")
                from seed_database import seed_all
                await seed_all(session)
            else:
                log.info(f"БД: {emp_count} сотрудников, seed не нужен")
    except Exception as e:
        log.error(f"Ошибка при seed: {e}")

    # Init ChromaDB — пропускаем если коллекция уже синхронизирована с PostgreSQL
    try:
        from app.database import AsyncSessionLocal
        from app.models import Document
        from sqlalchemy import select, func
        from app.services.vector_store import get_vector_store
        from app.services.document_indexer import index_all_documents

        vs = await get_vector_store()
        chroma_count = vs.count()

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(func.count()).select_from(Document).where(Document.is_active == True)
            )
            pg_doc_count = result.scalar()

        if chroma_count == 0:
            log.info(f"Коллекция '{vs.collection_name}' пуста. Индексируем {pg_doc_count} документов...")
            await index_all_documents()
        else:
            if chroma_count < pg_doc_count:
                log.warning(
                    f"ChromaDB '{vs.collection_name}': {chroma_count} чанков < {pg_doc_count} документов в PG. "
                    f"Возможна неполная индексация. Запустите: python -m app.scripts.index_documents"
                )
            else:
                log.info(f"ChromaDB '{vs.collection_name}': {chroma_count} чанков, PG: {pg_doc_count} документов — OK")

        # BM25 индекс строим после ChromaDB (всегда, независимо от состояния)
        from app.core.rag import build_bm25_index
        await build_bm25_index()
    except Exception as e:
        log.warning(f"ChromaDB не инициализирован: {e}")


# ─── Роутеры ──────────────────────────────────────────────────────────────────

from app.api.v1 import evaluator, generator, analytics, documents, goals, employees

app.include_router(evaluator.router, prefix="/api/v1", tags=["Evaluator"])
app.include_router(generator.router, prefix="/api/v1", tags=["Generator"])
app.include_router(analytics.router, prefix="/api/v1", tags=["Analytics"])
app.include_router(documents.router, prefix="/api/v1", tags=["Documents"])
app.include_router(goals.router, prefix="/api/v1", tags=["Goals"])
app.include_router(employees.router, prefix="/api/v1", tags=["Employees"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "hr-goals-ai"}
