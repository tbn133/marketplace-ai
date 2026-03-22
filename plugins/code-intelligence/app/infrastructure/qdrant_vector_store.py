"""Qdrant vector store implementation. Implements VectorStorePort."""

from __future__ import annotations

import uuid

import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from app.infrastructure.logging import get_logger

logger = get_logger("store.qdrant")


class QdrantVectorStore:
    def __init__(self, url: str, dimension: int, collection_prefix: str = "project_"):
        self._client = QdrantClient(url=url)
        self._dimension = dimension
        self._prefix = collection_prefix
        logger.info("Qdrant connected: %s", url)

    def _collection_name(self, project_id: str) -> str:
        return f"{self._prefix}{project_id}"

    def _ensure_collection(self, project_id: str) -> None:
        name = self._collection_name(project_id)
        collections = [c.name for c in self._client.get_collections().collections]
        if name not in collections:
            self._client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(
                    size=self._dimension,
                    distance=Distance.COSINE,
                ),
            )
            logger.info("Created Qdrant collection: %s", name)

    def save(self, project_id: str) -> None:
        # Qdrant persists automatically — no-op
        pass

    def add(self, project_id: str, node_id: str, embedding: np.ndarray, metadata: dict | None = None) -> None:
        self._ensure_collection(project_id)
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, node_id))
        payload = {"node_id": node_id, **(metadata or {})}
        self._client.upsert(
            collection_name=self._collection_name(project_id),
            points=[
                PointStruct(
                    id=point_id,
                    vector=embedding.tolist(),
                    payload=payload,
                )
            ],
        )

    def search(self, project_id: str, query_embedding: np.ndarray, top_k: int = 10) -> list[dict]:
        self._ensure_collection(project_id)
        response = self._client.query_points(
            collection_name=self._collection_name(project_id),
            query=query_embedding.tolist(),
            limit=top_k,
            with_payload=True,
        )
        return [
            {**hit.payload, "score": hit.score}
            for hit in response.points
        ]

    def remove_by_file(self, project_id: str, file_path: str) -> None:
        self._ensure_collection(project_id)
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        self._client.delete(
            collection_name=self._collection_name(project_id),
            points_selector=Filter(
                must=[
                    FieldCondition(key="file", match=MatchValue(value=file_path))
                ]
            ),
        )

    def clear_project(self, project_id: str) -> None:
        name = self._collection_name(project_id)
        try:
            self._client.delete_collection(collection_name=name)
            logger.info("Deleted Qdrant collection: %s", name)
        except Exception:
            pass
