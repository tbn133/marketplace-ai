"""Data migration service — transfers data between storage backends.

Reads all data from source stores and writes to target stores.
Supports migrating: graph nodes/edges, vector embeddings, memories.
"""

from __future__ import annotations

import json
import pickle
from pathlib import Path

import faiss
import numpy as np

from app.domain.models import ClassNode, FunctionNode, ImportNode, Memory
from app.domain.ports import GraphStorePort, MemoryStorePort, VectorStorePort
from app.infrastructure.logging import get_logger

logger = get_logger("migration")


class MigrationService:
    def __init__(
        self,
        source_graph: GraphStorePort,
        source_vector: VectorStorePort,
        source_memory: MemoryStorePort | None,
        target_graph: GraphStorePort,
        target_vector: VectorStorePort,
        target_memory: MemoryStorePort | None,
    ):
        self._sg = source_graph
        self._sv = source_vector
        self._sm = source_memory
        self._tg = target_graph
        self._tv = target_vector
        self._tm = target_memory

    def migrate_project(self, project_id: str, dry_run: bool = False) -> dict:
        """Migrate all data for a project from source to target."""
        stats = {"graph_nodes": 0, "graph_edges": 0, "vectors": 0, "memories": 0}

        logger.info("Migrating project '%s' (dry_run=%s)", project_id, dry_run)

        # 1. Graph
        g_stats = self._migrate_graph(project_id, dry_run)
        stats["graph_nodes"] = g_stats["nodes"]
        stats["graph_edges"] = g_stats["edges"]

        # 2. Vectors
        stats["vectors"] = self._migrate_vectors(project_id, dry_run)

        # 3. Memories
        if self._sm and self._tm:
            stats["memories"] = self._migrate_memories(project_id, dry_run)

        if not dry_run:
            self._tg.save(project_id)
            self._tv.save(project_id)

        logger.info("Migration complete: %s", stats)
        return stats

    def _migrate_graph(self, project_id: str, dry_run: bool) -> dict:
        """Migrate graph nodes and edges."""
        all_funcs = self._sg.get_all_functions(project_id)
        nodes = 0
        edges = 0

        for func_data in all_funcs:
            if func_data.get("type") != "function":
                continue

            fn = FunctionNode(
                id=func_data["id"],
                project_id=func_data.get("project_id", project_id),
                name=func_data.get("name", ""),
                file=func_data.get("file", ""),
                start_line=func_data.get("start_line", 0),
                end_line=func_data.get("end_line", 0),
                signature=func_data.get("signature", ""),
                summary=func_data.get("summary", ""),
                calls=func_data.get("calls", []),
            )
            if not dry_run:
                self._tg.add_function(fn)
            nodes += 1

            # Migrate outgoing edges
            callees = self._sg.get_callees(project_id, fn.id)
            for callee in callees:
                callee_id = callee.get("id")
                if callee_id:
                    if not dry_run:
                        self._tg.add_call_edge(project_id, fn.id, callee_id)
                    edges += 1

        logger.info("  Graph: %d nodes, %d edges", nodes, edges)
        return {"nodes": nodes, "edges": edges}

    def _migrate_vectors(self, project_id: str, dry_run: bool) -> int:
        """Migrate vector embeddings by reading raw FAISS data."""
        count = self._migrate_vectors_via_source(project_id, dry_run)
        logger.info("  Vectors: %d", count)
        return count

    def _migrate_vectors_via_source(self, project_id: str, dry_run: bool) -> int:
        """Read vectors from source and write to target."""
        # Access internal FAISS data if source is FaissVectorStore
        sv = self._sv
        if not hasattr(sv, "_indices") or not hasattr(sv, "_metadata"):
            logger.warning("  Source vector store does not expose raw data — skipping vectors")
            return 0

        # Force load
        if hasattr(sv, "_get_index"):
            sv._get_index(project_id)

        if project_id not in sv._indices:
            return 0

        idx = sv._indices[project_id]
        meta = sv._metadata.get(project_id, [])

        if idx.ntotal == 0 or not meta:
            return 0

        dim = idx.d
        raw = faiss.rev_swig_ptr(idx.get_xb(), idx.ntotal * dim)
        all_vecs = np.array(raw, dtype=np.float32).reshape(idx.ntotal, dim)

        count = 0
        for i, m in enumerate(meta):
            if i >= idx.ntotal:
                break
            if not dry_run:
                self._tv.add(
                    project_id=project_id,
                    node_id=m.get("node_id", ""),
                    embedding=all_vecs[i],
                    metadata={k: v for k, v in m.items() if k != "node_id"},
                )
            count += 1

        return count

    def _migrate_memories(self, project_id: str, dry_run: bool) -> int:
        """Migrate all memory entries."""
        memories = self._sm.search(project_id=project_id, limit=10000)
        count = 0
        for mem in memories:
            if not dry_run:
                self._tm.add(mem)
            count += 1

        logger.info("  Memories: %d", count)
        return count


def discover_local_projects(data_dir: Path) -> list[str]:
    """Discover project IDs from local data directory by scanning file names."""
    projects = set()

    for f in data_dir.glob("graph_*.pkl"):
        pid = f.stem.replace("graph_", "")
        projects.add(pid)

    for f in data_dir.glob("faiss_*.index"):
        pid = f.stem.replace("faiss_", "")
        projects.add(pid)

    return sorted(projects)
