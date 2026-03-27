"""Vector store implementation using FAISS. Implements VectorStorePort."""

from __future__ import annotations

import json
import os
from pathlib import Path

import faiss
import numpy as np


class FaissVectorStore:
    def __init__(self, data_dir: Path, dimension: int):
        self._data_dir = data_dir
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._dimension = dimension
        self._indices: dict[str, faiss.IndexFlatIP] = {}
        self._metadata: dict[str, list[dict]] = {}

    def _index_path(self, project_id: str) -> Path:
        return self._data_dir / f"faiss_{project_id}.index"

    def _meta_path(self, project_id: str) -> Path:
        return self._data_dir / f"faiss_{project_id}_meta.json"

    def _get_index(self, project_id: str) -> faiss.IndexFlatIP:
        if project_id not in self._indices:
            path = self._index_path(project_id)
            if path.exists():
                self._indices[project_id] = faiss.read_index(str(path))
                with open(self._meta_path(project_id), "r") as f:
                    self._metadata[project_id] = json.load(f)
            else:
                self._indices[project_id] = faiss.IndexFlatIP(self._dimension)
                self._metadata[project_id] = []
        return self._indices[project_id]

    def save(self, project_id: str) -> None:
        idx = self._get_index(project_id)
        faiss.write_index(idx, str(self._index_path(project_id)))
        with open(self._meta_path(project_id), "w") as f:
            json.dump(self._metadata[project_id], f)

    def add(self, project_id: str, node_id: str, embedding: np.ndarray, metadata: dict | None = None) -> None:
        idx = self._get_index(project_id)
        vec = embedding.reshape(1, -1).astype(np.float32)
        idx.add(vec)
        meta = {"node_id": node_id, **(metadata or {})}
        self._metadata[project_id].append(meta)

    def search(self, project_id: str, query_embedding: np.ndarray, top_k: int = 10) -> list[dict]:
        idx = self._get_index(project_id)
        if idx.ntotal == 0:
            return []

        vec = query_embedding.reshape(1, -1).astype(np.float32)
        k = min(top_k, idx.ntotal)
        scores, indices = idx.search(vec, k)

        results = []
        for score, i in zip(scores[0], indices[0]):
            if i < 0 or i >= len(self._metadata[project_id]):
                continue
            meta = self._metadata[project_id][i]
            results.append({**meta, "score": float(score)})
        return results

    def remove_by_file(self, project_id: str, file_path: str) -> None:
        if project_id not in self._metadata:
            self._get_index(project_id)

        old_meta = self._metadata.get(project_id, [])
        if not old_meta:
            return

        idx = self._indices[project_id]
        if idx.ntotal == 0:
            return

        all_vecs = faiss.rev_swig_ptr(idx.get_xb(), idx.ntotal * self._dimension)
        all_vecs = np.array(all_vecs, dtype=np.float32).reshape(idx.ntotal, self._dimension)

        new_meta = []
        new_vecs = []
        for i, meta in enumerate(old_meta):
            if meta.get("file") != file_path:
                new_meta.append(meta)
                new_vecs.append(all_vecs[i])

        new_index = faiss.IndexFlatIP(self._dimension)
        if new_vecs:
            new_index.add(np.array(new_vecs, dtype=np.float32))

        self._indices[project_id] = new_index
        self._metadata[project_id] = new_meta

    def clear_project(self, project_id: str) -> None:
        self._indices[project_id] = faiss.IndexFlatIP(self._dimension)
        self._metadata[project_id] = []
        for p in [self._index_path(project_id), self._meta_path(project_id)]:
            if p.exists():
                os.remove(p)
