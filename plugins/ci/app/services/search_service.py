"""Search service — vector search + graph expansion + caching.

Depends only on domain ports, never on concrete implementations.
"""

from __future__ import annotations

import json

from app.domain.models import SearchResult
from app.domain.ports import CachePort, EmbeddingPort, GraphStorePort, VectorStorePort


class SearchService:
    def __init__(
        self,
        graph_store: GraphStorePort,
        vector_store: VectorStorePort,
        embedding: EmbeddingPort,
        cache: CachePort | None = None,
    ):
        self._graph_store = graph_store
        self._vector_store = vector_store
        self._embedding = embedding
        self._cache = cache

    def _cache_key(self, project_id: str, query: str, top_k: int) -> str:
        return f"search:{project_id}:{query}:{top_k}"

    def search(self, project_id: str, query: str, top_k: int = 10) -> SearchResult:
        # Check cache
        if self._cache:
            key = self._cache_key(project_id, query, top_k)
            cached = self._cache.get(key)
            if cached:
                data = json.loads(cached)
                return SearchResult(**data)

        # Vector search
        query_vec = self._embedding.generate(query)
        vector_results = self._vector_store.search(project_id, query_vec, top_k=top_k)

        # Graph expansion
        functions: list[dict] = []
        related_set: dict[str, dict] = {}

        for vr in vector_results:
            node_id = vr["node_id"]
            func = self._graph_store.get_function(project_id, node_id)
            if func:
                func["score"] = vr.get("score", 0.0)
                functions.append(func)

                for callee in self._graph_store.get_callees(project_id, node_id):
                    cid = callee.get("id")
                    if cid and cid not in related_set:
                        related_set[cid] = callee

                for caller in self._graph_store.get_callers(project_id, node_id):
                    cid = caller.get("id")
                    if cid and cid not in related_set:
                        related_set[cid] = caller

        func_ids = {f.get("id") for f in functions}
        related = [r for r in related_set.values() if r.get("id") not in func_ids]

        result = SearchResult(
            functions=functions,
            related=related,
            query=query,
            project_id=project_id,
        )

        # Store in cache
        if self._cache:
            from dataclasses import asdict
            self._cache.set(key, json.dumps(asdict(result)))

        return result

    def get_function(self, project_id: str, function_id: str) -> dict | None:
        return self._graph_store.get_function(project_id, function_id)

    def get_call_graph(self, project_id: str, function_id: str, depth: int = 2) -> dict:
        return self._graph_store.get_call_graph(project_id, function_id, depth=depth)
