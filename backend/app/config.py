from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/hr_goals"

    # Anthropic
    anthropic_api_key: str = ""
    llm_model: str = "claude-sonnet-4-20250514"
    llm_temperature_eval: float = 0.0
    llm_temperature_gen: float = 0.3
    llm_provider: str = "anthropic"  # anthropic | azure_openai

    # ChromaDB
    chroma_persist_dir: str = "./chroma_data"

    # Embedding model (изменение вызывает переиндексацию ChromaDB)
    embedding_model: str = "intfloat/multilingual-e5-small"

    # Reranker (опционально, включается через USE_RERANKER=true)
    use_reranker: bool = False
    reranker_model: str = "BAAI/bge-reranker-v2-m3"

    # HuggingFace token (опционально, для приватных/gated моделей)
    hf_token: str = ""

    # Azure OpenAI (опционально)
    azure_openai_api_key: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_api_version: str = "2024-02-01"
    azure_openai_deployment: str = ""
    azure_embedding_deployment: str = "text-embedding-3-large"

    # App
    log_level: str = "INFO"
    cors_origins: list[str] = ["http://localhost:5174", "http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
