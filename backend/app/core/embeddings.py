import logging
from typing import List, Optional, Union
import numpy as np
from openai import AzureOpenAI
from app.config import settings

log = logging.getLogger(__name__)

class AzureEmbedder:
    """
    Класс-заглушка, мимикрирующий под SentenceTransformer для работы с Azure OpenAI.
    """
    def __init__(self):
        log.info(f"Инициализация Azure OpenAI Embedder (deployment: {settings.azure_embedding_deployment})")
        self.client = AzureOpenAI(
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
            azure_endpoint=settings.azure_openai_endpoint,
        )
        self.deployment = settings.azure_embedding_deployment

    def encode(
        self, 
        sentences: Union[str, List[str]], 
        normalize_embeddings: bool = True,
        batch_size: int = 32,
        show_progress_bar: bool = False,
        **kwargs
    ) -> np.ndarray:
        if isinstance(sentences, str):
            sentences = [sentences]

        all_embeddings = []
        # Azure OpenAI поддерживает батчи, но мы можем разбивать их сами для надежности
        for i in range(0, len(sentences), batch_size):
            batch = sentences[i : i + batch_size]
            response = self.client.embeddings.create(
                input=batch,
                model=self.deployment
            )
            batch_embeddings = [data.embedding for data in response.data]
            all_embeddings.extend(batch_embeddings)

        embeddings_np = np.array(all_embeddings, dtype=np.float32)
        
        if normalize_embeddings:
            norms = np.linalg.norm(embeddings_np, axis=1, keepdims=True)
            embeddings_np = embeddings_np / norms
            
        return embeddings_np

_embedder = None

def get_embedder():
    global _embedder
    if _embedder is None:
        from app.config import settings
        if settings.embedding_model == "azure":
            _embedder = AzureEmbedder()
        else:
            from sentence_transformers import SentenceTransformer
            log.info(f"Загружаем локальную модель {settings.embedding_model}...")
            _embedder = SentenceTransformer(settings.embedding_model)
    return _embedder
