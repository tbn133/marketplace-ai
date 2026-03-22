"""Composition root — wires all dependencies based on config.

STORAGE_BACKEND=local       → NetworkX + FAISS + SQLite + MemoryCache
STORAGE_BACKEND=production  → Neo4j + Qdrant + PostgreSQL + Redis
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config import AppConfig, load_config
from app.domain.ports import (
    CachePort,
    EmbeddingPort,
    GraphStorePort,
    MemoryStorePort,
    VectorStorePort,
)
from app.infrastructure.logging import get_logger, setup_logging
from app.services.indexing_service import IndexingService
from app.services.memory_service import MemoryService
from app.services.search_service import SearchService

logger = get_logger("container")


@dataclass
class Container:
    """Holds all application dependencies. Created once, shared everywhere."""

    config: AppConfig

    # Ports
    embedding: EmbeddingPort
    graph_store: GraphStorePort
    vector_store: VectorStorePort
    memory_store: MemoryStorePort
    cache: CachePort

    # Services
    indexing_service: IndexingService
    search_service: SearchService
    memory_service: MemoryService


def _create_local(config: AppConfig) -> tuple[GraphStorePort, VectorStorePort, MemoryStorePort, CachePort, EmbeddingPort]:
    """Wire local/dev dependencies (zero external services)."""
    from app.infrastructure.embedding import HashEmbeddingService
    from app.infrastructure.graph_store import NetworkXGraphStore
    from app.infrastructure.memory_cache import MemoryCache
    from app.infrastructure.memory_store import SqliteMemoryStore
    from app.infrastructure.vector_store import FaissVectorStore

    data_dir = config.storage.data_dir
    data_dir.mkdir(parents=True, exist_ok=True)

    embedding = HashEmbeddingService(dimension=config.embedding.dimension)
    graph_store = NetworkXGraphStore(data_dir=data_dir)
    vector_store = FaissVectorStore(data_dir=data_dir, dimension=embedding.dimension)
    memory_store = SqliteMemoryStore(db_path=data_dir / "db.sqlite")
    cache = MemoryCache(default_ttl=config.redis.default_ttl)

    logger.info("Wired LOCAL backend (NetworkX + FAISS + SQLite + MemoryCache)")
    return graph_store, vector_store, memory_store, cache, embedding


def _create_production(config: AppConfig) -> tuple[GraphStorePort, VectorStorePort, MemoryStorePort, CachePort, EmbeddingPort]:
    """Wire production dependencies (Neo4j + Qdrant + PostgreSQL + Redis)."""
    from app.infrastructure.embedding import HashEmbeddingService
    from app.infrastructure.neo4j_graph_store import Neo4jGraphStore
    from app.infrastructure.postgres_memory_store import PostgresMemoryStore
    from app.infrastructure.qdrant_vector_store import QdrantVectorStore
    from app.infrastructure.redis_cache import RedisCache

    embedding = HashEmbeddingService(dimension=config.embedding.dimension)

    graph_store = Neo4jGraphStore(
        uri=config.neo4j.uri,
        user=config.neo4j.user,
        password=config.neo4j.password,
    )
    vector_store = QdrantVectorStore(
        url=config.qdrant.url,
        dimension=embedding.dimension,
        collection_prefix=config.qdrant.collection_prefix,
    )
    memory_store = PostgresMemoryStore(
        host=config.postgres.host,
        port=config.postgres.port,
        database=config.postgres.database,
        user=config.postgres.user,
        password=config.postgres.password,
    )
    cache = RedisCache(url=config.redis.url, default_ttl=config.redis.default_ttl)

    logger.info("Wired PRODUCTION backend (Neo4j + Qdrant + PostgreSQL + Redis)")
    return graph_store, vector_store, memory_store, cache, embedding


def create_container(config: AppConfig | None = None) -> Container:
    """Factory that wires all dependencies based on config."""
    config = config or load_config()
    setup_logging(level=config.server.log_level)

    backend = config.storage.backend.lower()
    if backend == "production":
        graph_store, vector_store, memory_store, cache, embedding = _create_production(config)
    else:
        graph_store, vector_store, memory_store, cache, embedding = _create_local(config)

    # Services
    indexing_service = IndexingService(
        graph_store=graph_store,
        vector_store=vector_store,
        embedding=embedding,
        data_dir=config.storage.data_dir,
    )
    search_service = SearchService(
        graph_store=graph_store,
        vector_store=vector_store,
        embedding=embedding,
        cache=cache,
    )
    memory_service = MemoryService(memory_store=memory_store)

    return Container(
        config=config,
        embedding=embedding,
        graph_store=graph_store,
        vector_store=vector_store,
        memory_store=memory_store,
        cache=cache,
        indexing_service=indexing_service,
        search_service=search_service,
        memory_service=memory_service,
    )
