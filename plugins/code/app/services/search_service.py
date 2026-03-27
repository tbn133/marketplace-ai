"""Search service — vector search + graph expansion + caching.

Depends only on domain ports, never on concrete implementations.
"""

from __future__ import annotations

import json
from typing import Callable

from app.domain.models import SearchResult
from app.domain.ports import CachePort, EmbeddingPort, GraphStorePort, VectorStorePort


class SearchService:
    def __init__(
        self,
        graph_store: GraphStorePort,
        vector_store: VectorStorePort,
        embedding: EmbeddingPort,
        cache: CachePort | None = None,
        project_resolver: Callable[[str], list[str]] | None = None,
    ):
        self._graph_store = graph_store
        self._vector_store = vector_store
        self._embedding = embedding
        self._cache = cache
        self._project_resolver = project_resolver

    def _resolve_projects(self, project_id: str) -> list[str]:
        """Resolve wildcard project_id (e.g. 'myapp-*') to concrete IDs."""
        if self._project_resolver and project_id.endswith("-*"):
            return self._project_resolver(project_id)
        return [project_id]

    def _cache_key(self, project_id: str, query: str, top_k: int) -> str:
        return f"search:{project_id}:{query}:{top_k}"

    def search(self, project_id: str, query: str, top_k: int = 10) -> SearchResult:
        project_ids = self._resolve_projects(project_id)

        # Cross-project: search each, merge results
        if len(project_ids) > 1:
            return self._search_cross(project_ids, query, top_k, original_id=project_id)

        return self._search_single(project_id, query, top_k)

    def _search_single(self, project_id: str, query: str, top_k: int) -> SearchResult:
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

    def _search_cross(
        self, project_ids: list[str], query: str, top_k: int, original_id: str,
    ) -> SearchResult:
        """Search across multiple projects and merge results by score."""
        all_functions: list[dict] = []
        all_related: dict[str, dict] = {}

        for pid in project_ids:
            result = self._search_single(pid, query, top_k=top_k)
            all_functions.extend(result.functions)
            for r in result.related:
                rid = r.get("id")
                if rid and rid not in all_related:
                    all_related[rid] = r

        # Sort by score descending, take top_k
        all_functions.sort(key=lambda f: f.get("score", 0.0), reverse=True)
        functions = all_functions[:top_k]

        func_ids = {f.get("id") for f in functions}
        related = [r for r in all_related.values() if r.get("id") not in func_ids]

        return SearchResult(
            functions=functions,
            related=related,
            query=query,
            project_id=original_id,
        )

    def get_function(self, project_id: str, function_id: str) -> dict | None:
        return self._graph_store.get_function(project_id, function_id)

    def get_call_graph(self, project_id: str, function_id: str, depth: int = 2) -> dict:
        return self._graph_store.get_call_graph(project_id, function_id, depth=depth)
