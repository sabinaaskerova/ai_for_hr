"""ChromaDB wrapper для поиска по ВНД."""
import logging
from typing import Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.config import settings

log = logging.getLogger(__name__)

_vector_store: Optional["VectorStore"] = None


class VectorStore:
    COLLECTION_NAME = "vnd_documents"

    def __init__(self):
        self.client = chromadb.PersistentClient(
            path=settings.chroma_persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        log.info(f"ChromaDB: коллекция '{self.COLLECTION_NAME}', документов: {self.collection.count()}")

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        where: Optional[dict] = None,
    ) -> list[dict]:
        kwargs = dict(
            query_embeddings=[query_embedding],
            n_results=min(top_k, max(1, self.collection.count())),
            include=["documents", "metadatas", "distances"],
        )
        if where:
            kwargs["where"] = where

        results = self.collection.query(**kwargs)
        output = []
        for i, (doc, meta, dist) in enumerate(zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        )):
            output.append({
                "chunk_text": doc,
                "metadata": meta,
                "distance": dist,
                "relevance_score": round(1 - dist, 3),
            })
        return output

    def add_chunks(self, chunks: list[dict]) -> None:
        """chunks: list of {id, text, embedding, metadata}"""
        if not chunks:
            return
        self.collection.upsert(
            ids=[c["id"] for c in chunks],
            documents=[c["text"] for c in chunks],
            embeddings=[c["embedding"] for c in chunks],
            metadatas=[c["metadata"] for c in chunks],
        )
        log.info(f"Добавлено {len(chunks)} чанков в ChromaDB")

    def count(self) -> int:
        return self.collection.count()


async def get_vector_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store
