"""Vector store implementation using FAISS IDMap2. Implements VectorStorePort.

Uses IDMap2(IndexFlatIP) so each vector has a persistent integer ID.
Removal is O(k) where k = vectors to remove, not O(N) full rebuild.
"""

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
        self._indices: dict[str, faiss.IndexIDMap2] = {}
        self._metadata: dict[str, list[dict]] = {}
        self._next_id: dict[str, int] = {}

    def _index_path(self, project_id: str) -> Path:
        return self._data_dir / f"faiss_{project_id}.index"

    def _meta_path(self, project_id: str) -> Path:
        return self._data_dir / f"faiss_{project_id}_meta.json"

    def _get_index(self, project_id: str) -> faiss.IndexIDMap2:
        if project_id not in self._indices:
            path = self._index_path(project_id)
            if path.exists():
                raw_index = faiss.read_index(str(path))
                # Handle legacy IndexFlatIP: wrap in IDMap2
                if not isinstance(raw_index, faiss.IndexIDMap2):
                    old_meta = []
                    meta_path = self._meta_path(project_id)
                    if meta_path.exists():
                        text = meta_path.read_text()
                        if text.strip():
                            old_meta = json.loads(text)

                    new_index = faiss.IndexIDMap2(faiss.IndexFlatIP(self._dimension))
                    if raw_index.ntotal > 0 and old_meta:
                        vecs = faiss.rev_swig_ptr(
                            raw_index.get_xb(), raw_index.ntotal * self._dimension
                        )
                        vecs = np.array(vecs, dtype=np.float32).reshape(
                            raw_index.ntotal, self._dimension
                        )
                        ids = np.arange(len(old_meta), dtype=np.int64)
                        new_index.add_with_ids(vecs, ids)
                    self._indices[project_id] = new_index
                    self._metadata[project_id] = old_meta
                    self._next_id[project_id] = len(old_meta)
                else:
                    self._indices[project_id] = raw_index
                    meta_path = self._meta_path(project_id)
                    if meta_path.exists():
                        text = meta_path.read_text()
                        self._metadata[project_id] = json.loads(text) if text.strip() else []
                    else:
                        self._metadata[project_id] = []
                    self._next_id[project_id] = max(
                        (m.get("_vid", -1) for m in self._metadata[project_id]),
                        default=-1,
                    ) + 1
            else:
                self._indices[project_id] = faiss.IndexIDMap2(faiss.IndexFlatIP(self._dimension))
                self._metadata[project_id] = []
                self._next_id[project_id] = 0
        return self._indices[project_id]

    def save(self, project_id: str) -> None:
        idx = self._get_index(project_id)
        index_path = self._index_path(project_id)
        meta_path = self._meta_path(project_id)

        # Atomic write for FAISS index
        tmp_index = index_path.with_suffix(".index.tmp")
        faiss.write_index(idx, str(tmp_index))
        tmp_index.rename(index_path)

        # Atomic write for meta JSON
        tmp_meta = meta_path.with_suffix(".json.tmp")
        content = json.dumps(self._metadata[project_id])
        tmp_meta.write_text(content)
        tmp_meta.rename(meta_path)

    def add(self, project_id: str, node_id: str, embedding: np.ndarray, metadata: dict | None = None) -> None:
        idx = self._get_index(project_id)
        vec = embedding.reshape(1, -1).astype(np.float32)
        vid = self._next_id.get(project_id, 0)
        self._next_id[project_id] = vid + 1
        idx.add_with_ids(vec, np.array([vid], dtype=np.int64))
        meta = {"node_id": node_id, "_vid": vid, **(metadata or {})}
        self._metadata[project_id].append(meta)

    def add_batch(self, project_id: str, node_ids: list[str], embeddings: np.ndarray, metadata_list: list[dict]) -> None:
        if len(node_ids) == 0:
            return
        idx = self._get_index(project_id)
        vecs = embeddings.astype(np.float32)
        start_vid = self._next_id.get(project_id, 0)
        ids = np.arange(start_vid, start_vid + len(node_ids), dtype=np.int64)
        self._next_id[project_id] = start_vid + len(node_ids)
        idx.add_with_ids(vecs, ids)
        for i, (node_id, vid) in enumerate(zip(node_ids, ids)):
            meta = {"node_id": node_id, "_vid": int(vid), **(metadata_list[i] if i < len(metadata_list) else {})}
            self._metadata[project_id].append(meta)

    def search(self, project_id: str, query_embedding: np.ndarray, top_k: int = 10) -> list[dict]:
        idx = self._get_index(project_id)
        if idx.ntotal == 0:
            return []

        vec = query_embedding.reshape(1, -1).astype(np.float32)
        k = min(top_k, idx.ntotal)
        scores, ids = idx.search(vec, k)

        # Build vid -> meta lookup
        vid_to_meta = {m["_vid"]: m for m in self._metadata[project_id] if "_vid" in m}

        results = []
        for score, vid in zip(scores[0], ids[0]):
            if vid < 0:
                continue
            meta = vid_to_meta.get(int(vid))
            if meta is None:
                continue
            # Return meta without internal _vid field
            out = {k: v for k, v in meta.items() if k != "_vid"}
            out["score"] = float(score)
            results.append(out)
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

        # Collect vector IDs to remove
        remove_vids = []
        keep_meta = []
        for m in old_meta:
            if m.get("file") == file_path:
                if "_vid" in m:
                    remove_vids.append(m["_vid"])
            else:
                keep_meta.append(m)

        if remove_vids:
            idx.remove_ids(np.array(remove_vids, dtype=np.int64))
            self._metadata[project_id] = keep_meta

    def clear_project(self, project_id: str) -> None:
        self._indices[project_id] = faiss.IndexIDMap2(faiss.IndexFlatIP(self._dimension))
        self._metadata[project_id] = []
        self._next_id[project_id] = 0
        for p in [self._index_path(project_id), self._meta_path(project_id)]:
            if p.exists():
                os.remove(p)
