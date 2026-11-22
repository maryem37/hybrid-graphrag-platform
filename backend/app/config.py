from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    # LLM provider: "azure" | "openai" | "groq"
    llm_provider: str = "azure"
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_api_version: str = "2024-10-21"
    azure_openai_chat_deployment: str = "gpt-4o-mini"
    azure_openai_embedding_deployment: str = "text-embedding-3-small"
    openai_api_key: str = ""
    openai_chat_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    groq_api_key: str = ""
    groq_chat_model: str = "openai/gpt-oss-120b"
    # Groq chat has no public embedding model on this key; FastEmbed runs locally.
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dim: int = 384

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "change_me_please"

    # Pipeline
    data_dir: str = "../data"
    chunk_size: int = 1000
    chunk_overlap: int = 200
    ingest_workers: int = 4
    max_hub_degree: int = 40  # do not traverse *through* entities with more links than this
    cors_origins: str = "*"


@lru_cache
def get_settings() -> Settings:
    return Settings()
