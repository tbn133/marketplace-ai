"""Domain models — pure data, no framework dependencies."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class FunctionNode:
    id: str
    project_id: str
    name: str
    file: str
    start_line: int
    end_line: int
    signature: str = ""
    summary: str = ""
    calls: list[str] = field(default_factory=list)


@dataclass
class ClassNode:
    id: str
    project_id: str
    name: str
    file: str
    start_line: int
    end_line: int
    methods: list[str] = field(default_factory=list)


@dataclass
class ImportNode:
    id: str
    project_id: str
    file: str
    module: str
    names: list[str] = field(default_factory=list)


@dataclass
class Memory:
    project_id: str
    type: str
    content: str
    id: str | None = None
    tags: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class FileRecord:
    path: str
    project_id: str
    file_hash: str
    indexed_at: str


@dataclass
class ProjectInfo:
    project_id: str
    root_path: str
    total_files: int = 0
    total_functions: int = 0
    total_classes: int = 0


@dataclass
class SearchResult:
    functions: list[dict] = field(default_factory=list)
    related: list[dict] = field(default_factory=list)
    query: str = ""
    project_id: str = ""


@dataclass
class MemorySearchResult:
    memories: list[Memory] = field(default_factory=list)
    total: int = 0
