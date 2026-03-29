"""ChromaDB wrapper для поиска по ВНД."""
import logging
from typing import Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.config import settings

log = logging.getLogger(__name__)

_vector_store: Optional["VectorStore"] = None


def _collection_name_for_model(model: str) -> str:
    """documents_BAAI_bge-m3, documents_intfloat_multilingual-e5-large, etc."""
    return "documents_" + model.replace("/", "_")


class VectorStore:
    def __init__(self):
        self.collection_name = _collection_name_for_model(settings.embedding_model)
        self.client = chromadb.PersistentClient(
            path=settings.chroma_persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        log.info(f"ChromaDB: коллекция '{self.collection_name}', документов: {self.collection.count()}")

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

    def delete_chunks_by_doc_id(self, doc_id: int) -> None:
        """Удаляет все чанки документа из ChromaDB по doc_id."""
        results = self.collection.get(where={"doc_id": {"$eq": doc_id}}, include=[])
        ids = results.get("ids", [])
        if ids:
            self.collection.delete(ids=ids)
            log.info(f"Удалено {len(ids)} чанков для doc_id={doc_id}")

    def clear_collection(self) -> None:
        """Удаляет и пересоздаёт коллекцию (для ручной переиндексации через --force)."""
        self.client.delete_collection(self.collection_name)
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        log.info(f"ChromaDB: коллекция '{self.collection_name}' очищена")


async def get_vector_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store
