"""Memory service — CRUD for persistent business memory.

Depends only on domain ports, never on concrete implementations.
"""

from __future__ import annotations

from typing import Callable

from app.domain.models import Memory, MemorySearchResult
from app.domain.ports import MemoryStorePort


class MemoryService:
    def __init__(
        self,
        memory_store: MemoryStorePort,
        project_resolver: Callable[[str], list[str]] | None = None,
    ):
        self._memory_store = memory_store
        self._project_resolver = project_resolver

    def _resolve_projects(self, project_id: str) -> list[str]:
        if self._project_resolver and project_id.endswith("-*"):
            return self._project_resolver(project_id)
        return [project_id]

    def add(self, project_id: str, type: str, content: str, tags: list[str] | None = None) -> Memory:
        memory = Memory(
            project_id=project_id,
            type=type,
            content=content,
            tags=tags or [],
        )
        return self._memory_store.add(memory)

    def get(self, memory_id: str) -> Memory | None:
        return self._memory_store.get(memory_id)

    def search(
        self,
        project_id: str,
        query: str = "",
        type_filter: str = "",
        limit: int = 20,
    ) -> MemorySearchResult:
        project_ids = self._resolve_projects(project_id)

        if len(project_ids) > 1:
            return self._search_cross(project_ids, query, type_filter, limit)

        memories = self._memory_store.search(
            project_id=project_id,
            query=query,
            type_filter=type_filter,
            limit=limit,
        )
        return MemorySearchResult(memories=memories, total=len(memories))

    def _search_cross(
        self, project_ids: list[str], query: str, type_filter: str, limit: int,
    ) -> MemorySearchResult:
        all_memories: list[Memory] = []
        for pid in project_ids:
            memories = self._memory_store.search(
                project_id=pid, query=query, type_filter=type_filter, limit=limit,
            )
            all_memories.extend(memories)
        # Sort by newest first, take limit
        all_memories.sort(key=lambda m: m.created_at, reverse=True)
        trimmed = all_memories[:limit]
        return MemorySearchResult(memories=trimmed, total=len(trimmed))

    def delete(self, memory_id: str) -> bool:
        return self._memory_store.delete(memory_id)
