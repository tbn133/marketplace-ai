"""Memory store implementation using SQLite. Implements MemoryStorePort."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

from app.domain.models import Memory


class SqliteMemoryStore:
    def __init__(self, db_path: Path):
        self._db_path = str(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tags TEXT DEFAULT '',
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_memories_project
                ON memories(project_id)
            """)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def add(self, memory: Memory) -> Memory:
        if not memory.id:
            memory.id = str(uuid.uuid4())
        if not memory.created_at:
            memory.created_at = datetime.utcnow().isoformat()

        with self._connect() as conn:
            conn.execute(
                "INSERT INTO memories (id, project_id, type, content, tags, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    memory.id,
                    memory.project_id,
                    memory.type,
                    memory.content,
                    ",".join(memory.tags),
                    memory.created_at,
                ),
            )
        return memory

    def get(self, memory_id: str) -> Memory | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, project_id, type, content, tags, created_at FROM memories WHERE id = ?",
                (memory_id,),
            ).fetchone()
        if not row:
            return None
        return self._row_to_memory(row)

    def search(self, project_id: str, query: str = "", type_filter: str = "", limit: int = 20) -> list[Memory]:
        sql = "SELECT id, project_id, type, content, tags, created_at FROM memories WHERE project_id = ?"
        params: list = [project_id]

        if query:
            sql += " AND content LIKE ?"
            params.append(f"%{query}%")

        if type_filter:
            sql += " AND type = ?"
            params.append(type_filter)

        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_memory(r) for r in rows]

    def delete(self, memory_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            return cursor.rowcount > 0

    @staticmethod
    def _row_to_memory(row: tuple) -> Memory:
        tags = [t for t in row[4].split(",") if t] if row[4] else []
        return Memory(
            id=row[0],
            project_id=row[1],
            type=row[2],
            content=row[3],
            tags=tags,
            created_at=row[5],
        )
