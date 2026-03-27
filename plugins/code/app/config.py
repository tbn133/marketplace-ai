"""Application configuration — all settings from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class StorageConfig:
    backend: str = "local"  # "local" or "production"
    data_dir: Path = field(default_factory=lambda: Path.home() / ".code-intelligence" / "data")


@dataclass(frozen=True)
class Neo4jConfig:
    uri: str = "bolt://localhost:7687"
    user: str = "neo4j"
    password: str = "password"


@dataclass(frozen=True)
class QdrantConfig:
    url: str = "http://localhost:6333"
    collection_prefix: str = "project_"


@dataclass(frozen=True)
class PostgresConfig:
    host: str = "localhost"
    port: int = 5432
    database: str = "code_intel"
    user: str = "postgres"
    password: str = "postgres"


@dataclass(frozen=True)
class RedisConfig:
    url: str = "redis://localhost:6379"
    default_ttl: int = 300  # seconds


@dataclass(frozen=True)
class EmbeddingConfig:
    dimension: int = 128


@dataclass(frozen=True)
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"


@dataclass(frozen=True)
class AppConfig:
    storage: StorageConfig
    neo4j: Neo4jConfig
    qdrant: QdrantConfig
    postgres: PostgresConfig
    redis: RedisConfig
    embedding: EmbeddingConfig
    server: ServerConfig


def load_config() -> AppConfig:
    """Load config from environment variables with sensible defaults."""
    return AppConfig(
        storage=StorageConfig(
            backend=os.getenv("STORAGE_BACKEND", "local"),
            data_dir=Path(os.getenv("DATA_DIR", str(Path.home() / ".code-intelligence" / "data"))),
        ),
        neo4j=Neo4jConfig(
            uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            user=os.getenv("NEO4J_USER", "neo4j"),
            password=os.getenv("NEO4J_PASS", "password"),
        ),
        qdrant=QdrantConfig(
            url=os.getenv("QDRANT_URL", "http://localhost:6333"),
            collection_prefix=os.getenv("QDRANT_PREFIX", "project_"),
        ),
        postgres=PostgresConfig(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            database=os.getenv("POSTGRES_DB", "code_intel"),
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASS", "postgres"),
        ),
        redis=RedisConfig(
            url=os.getenv("REDIS_URL", "redis://localhost:6379"),
            default_ttl=int(os.getenv("CACHE_TTL", "300")),
        ),
        embedding=EmbeddingConfig(
            dimension=int(os.getenv("EMBEDDING_DIM", "128")),
        ),
        server=ServerConfig(
            host=os.getenv("SERVER_HOST", "0.0.0.0"),
            port=int(os.getenv("SERVER_PORT", "8000")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        ),
    )
