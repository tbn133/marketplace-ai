"""Memory service — CRUD for persistent business memory.

Depends only on domain ports, never on concrete implementations.
"""

from __future__ import annotations

from app.domain.models import Memory, MemorySearchResult
from app.domain.ports import MemoryStorePort


class MemoryService:
    def __init__(self, memory_store: MemoryStorePort):
        self._memory_store = memory_store

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
        memories = self._memory_store.search(
            project_id=project_id,
            query=query,
            type_filter=type_filter,
            limit=limit,
        )
        return MemorySearchResult(memories=memories, total=len(memories))

    def delete(self, memory_id: str) -> bool:
        return self._memory_store.delete(memory_id)
