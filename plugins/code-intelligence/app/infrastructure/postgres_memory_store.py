"""PostgreSQL memory store implementation. Implements MemoryStorePort."""

from __future__ import annotations

import uuid
from datetime import datetime

import psycopg2
import psycopg2.extras

from app.domain.models import Memory
from app.infrastructure.logging import get_logger

logger = get_logger("store.postgres")


class PostgresMemoryStore:
    def __init__(self, host: str, port: int, database: str, user: str, password: str):
        self._conn = psycopg2.connect(
            host=host,
            port=port,
            dbname=database,
            user=user,
            password=password,
        )
        self._conn.autocommit = False
        logger.info("PostgreSQL connected: %s:%d/%s", host, port, database)
        self._init_db()

    def _init_db(self) -> None:
        with self._conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tags TEXT DEFAULT '',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_memories_project
                ON memories(project_id)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_memories_content_trgm
                ON memories USING gin(content gin_trgm_ops)
            """)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def add(self, memory: Memory) -> Memory:
        if not memory.id:
            memory.id = str(uuid.uuid4())
        if not memory.created_at:
            memory.created_at = datetime.utcnow().isoformat()

        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO memories (id, project_id, type, content, tags, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE
                SET content = EXCLUDED.content, tags = EXCLUDED.tags
                """,
                (
                    memory.id,
                    memory.project_id,
                    memory.type,
                    memory.content,
                    ",".join(memory.tags),
                    memory.created_at,
                ),
            )
        self._conn.commit()
        return memory

    def get(self, memory_id: str) -> Memory | None:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT id, project_id, type, content, tags, created_at FROM memories WHERE id = %s",
                (memory_id,),
            )
            row = cur.fetchone()
        if not row:
            return None
        return self._row_to_memory(row)

    def search(self, project_id: str, query: str = "", type_filter: str = "", limit: int = 20) -> list[Memory]:
        sql = "SELECT id, project_id, type, content, tags, created_at FROM memories WHERE project_id = %s"
        params: list = [project_id]

        if query:
            sql += " AND content ILIKE %s"
            params.append(f"%{query}%")

        if type_filter:
            sql += " AND type = %s"
            params.append(type_filter)

        sql += " ORDER BY created_at DESC LIMIT %s"
        params.append(limit)

        with self._conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        return [self._row_to_memory(r) for r in rows]

    def delete(self, memory_id: str) -> bool:
        with self._conn.cursor() as cur:
            cur.execute("DELETE FROM memories WHERE id = %s", (memory_id,))
            deleted = cur.rowcount > 0
        self._conn.commit()
        return deleted

    @staticmethod
    def _row_to_memory(row: tuple) -> Memory:
        tags_str = row[4] or ""
        tags = [t for t in tags_str.split(",") if t]
        created = row[5]
        if hasattr(created, "isoformat"):
            created = created.isoformat()
        return Memory(
            id=row[0],
            project_id=row[1],
            type=row[2],
            content=row[3],
            tags=tags,
            created_at=str(created),
        )
