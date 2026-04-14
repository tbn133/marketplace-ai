# Code Plugin Indexing Improvements

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix indexing performance bottlenecks, fix code-index.json not being written to target projects, fix FAISS meta 0-byte bug, and add document support (docx/xlsx/pdf) via markitdown.

**Architecture:** Improve the existing IndexingService with parallel file parsing (ThreadPoolExecutor), batch embedding+vector operations, FAISS IDMap2 for O(1) removal instead of full rebuild, atomic file writes, code-index.json marker file creation, and markitdown subprocess integration in doc_chunker for rich document conversion.

**Tech Stack:** Python 3.12+, FAISS (IDMap2), concurrent.futures, markitdown CLI (already installed), tree-sitter

---

## File Structure

**Modify:**
- `plugins/code/app/infrastructure/vector_store.py` — Switch to IDMap2, atomic writes, add `add_batch()`
- `plugins/code/app/domain/ports.py` — Add `add_batch()` to VectorStorePort
- `plugins/code/app/infrastructure/qdrant_vector_store.py` — Add `add_batch()` for production backend
- `plugins/code/app/indexer/doc_chunker.py` — Add markitdown integration for docx/xlsx/pdf
- `plugins/code/app/services/indexing_service.py` — Parallel parsing, batch operations, code-index.json write
- `plugins/code/app/infrastructure/embedding.py` — (no changes needed, `generate_batch` already exists)
- `plugins/code/requirements.txt` — Add markitdown dependency

**Create:**
- `plugins/code/tests/__init__.py`
- `plugins/code/tests/test_vector_store.py`
- `plugins/code/tests/test_doc_chunker.py`
- `plugins/code/tests/test_indexing_service.py`

---

### Task 1: Fix FAISS meta atomic write (bug fix)

The `faiss_*_meta.json` files can end up as 0 bytes when write fails mid-stream (observed: `faiss_aggregation-tabiyory_admin_api_meta.json` = 0 bytes while index = 31MB). Fix by writing to a temp file first, then atomic rename.

**Files:**
- Modify: `plugins/code/app/infrastructure/vector_store.py:39-43`
- Create: `plugins/code/tests/__init__.py`
- Create: `plugins/code/tests/test_vector_store.py`

- [ ] **Step 1: Create test directory and write failing test for atomic save**

Create `plugins/code/tests/__init__.py` (empty file).

Create `plugins/code/tests/test_vector_store.py`:

```python
"""Tests for FaissVectorStore."""

import json
import numpy as np
import pytest
from pathlib import Path

from app.infrastructure.vector_store import FaissVectorStore

DIMENSION = 8


@pytest.fixture
def store(tmp_path):
    return FaissVectorStore(data_dir=tmp_path, dimension=DIMENSION)


def _rand_vec():
    v = np.random.randn(DIMENSION).astype(np.float32)
    return v / np.linalg.norm(v)


class TestAtomicSave:
    def test_save_writes_valid_meta_json(self, store, tmp_path):
        """After save(), meta JSON must be valid and contain all entries."""
        store.add("proj", "n1", _rand_vec(), {"file": "a.py", "name": "foo"})
        store.add("proj", "n2", _rand_vec(), {"file": "b.py", "name": "bar"})
        store.save("proj")

        meta_path = tmp_path / "faiss_proj_meta.json"
        assert meta_path.exists()
        data = json.loads(meta_path.read_text())
        assert len(data) == 2
        assert data[0]["node_id"] == "n1"
        assert data[1]["node_id"] == "n2"

    def test_save_does_not_leave_partial_file_on_large_write(self, store, tmp_path):
        """Simulate large meta by adding many entries; verify atomicity."""
        for i in range(500):
            store.add("proj", f"n{i}", _rand_vec(), {"file": f"f{i}.py", "name": f"fn{i}"})
        store.save("proj")

        meta_path = tmp_path / "faiss_proj_meta.json"
        data = json.loads(meta_path.read_text())
        assert len(data) == 500

    def test_no_temp_files_left_after_save(self, store, tmp_path):
        """No .tmp files should remain after successful save."""
        store.add("proj", "n1", _rand_vec(), {"file": "a.py", "name": "foo"})
        store.save("proj")

        tmp_files = list(tmp_path.glob("*.tmp"))
        assert tmp_files == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd plugins/code && python -m pytest tests/test_vector_store.py::TestAtomicSave -v`

Expected: Tests pass with current implementation (baseline), but the temp file test establishes the contract.

- [ ] **Step 3: Implement atomic write in vector_store.py**

Replace the `save()` method in `plugins/code/app/infrastructure/vector_store.py:39-43`:

```python
def save(self, project_id: str) -> None:
    idx = self._get_index(project_id)
    index_path = self._index_path(project_id)
    meta_path = self._meta_path(project_id)

    # Atomic write for FAISS index
    tmp_index = index_path.with_suffix(".index.tmp")
    faiss.write_index(idx, str(tmp_index))
    tmp_index.rename(index_path)

    # Atomic write for meta JSON (prevents 0-byte files on crash/large writes)
    tmp_meta = meta_path.with_suffix(".json.tmp")
    content = json.dumps(self._metadata[project_id])
    tmp_meta.write_text(content)
    tmp_meta.rename(meta_path)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd plugins/code && python -m pytest tests/test_vector_store.py::TestAtomicSave -v`

Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/code/tests/__init__.py plugins/code/tests/test_vector_store.py plugins/code/app/infrastructure/vector_store.py
git commit -m "fix: atomic write for FAISS meta JSON to prevent 0-byte files"
```

---

### Task 2: FAISS IDMap2 for O(1) vector removal

Currently `remove_by_file()` rebuilds the entire FAISS index from scratch (O(N)) every time a single file's vectors are removed. With IDMap2, vectors have persistent integer IDs that can be removed directly.

**Files:**
- Modify: `plugins/code/app/infrastructure/vector_store.py` (full rewrite of index management)
- Modify: `plugins/code/app/domain/ports.py:32-36` (add `add_batch`)
- Test: `plugins/code/tests/test_vector_store.py`

- [ ] **Step 1: Write failing tests for IDMap removal and add_batch**

Append to `plugins/code/tests/test_vector_store.py`:

```python
class TestRemoveByFile:
    def test_remove_keeps_other_files(self, store):
        store.add("proj", "n1", _rand_vec(), {"file": "a.py", "name": "foo"})
        store.add("proj", "n2", _rand_vec(), {"file": "b.py", "name": "bar"})
        store.add("proj", "n3", _rand_vec(), {"file": "a.py", "name": "baz"})

        store.remove_by_file("proj", "a.py")

        results = store.search("proj", _rand_vec(), top_k=10)
        assert len(results) == 1
        assert results[0]["node_id"] == "n2"

    def test_remove_then_add_same_file(self, store):
        """Remove file vectors, then re-add — new vectors should be searchable."""
        store.add("proj", "n1", _rand_vec(), {"file": "a.py", "name": "foo"})
        store.remove_by_file("proj", "a.py")
        store.add("proj", "n1_new", _rand_vec(), {"file": "a.py", "name": "foo_v2"})

        results = store.search("proj", _rand_vec(), top_k=10)
        assert len(results) == 1
        assert results[0]["node_id"] == "n1_new"

    def test_remove_nonexistent_file_is_noop(self, store):
        store.add("proj", "n1", _rand_vec(), {"file": "a.py", "name": "foo"})
        store.remove_by_file("proj", "no_such_file.py")
        results = store.search("proj", _rand_vec(), top_k=10)
        assert len(results) == 1


class TestAddBatch:
    def test_add_batch_multiple_vectors(self, store):
        vecs = np.array([_rand_vec() for _ in range(3)])
        node_ids = ["n1", "n2", "n3"]
        metas = [
            {"file": "a.py", "name": "foo"},
            {"file": "a.py", "name": "bar"},
            {"file": "b.py", "name": "baz"},
        ]
        store.add_batch("proj", node_ids, vecs, metas)

        results = store.search("proj", _rand_vec(), top_k=10)
        assert len(results) == 3

    def test_add_batch_empty_is_noop(self, store):
        vecs = np.zeros((0, DIMENSION), dtype=np.float32)
        store.add_batch("proj", [], vecs, [])
        idx = store._get_index("proj")
        assert idx.ntotal == 0


class TestSaveAndReload:
    def test_save_reload_preserves_data(self, tmp_path):
        store = FaissVectorStore(data_dir=tmp_path, dimension=DIMENSION)
        vec = _rand_vec()
        store.add("proj", "n1", vec, {"file": "a.py", "name": "foo"})
        store.save("proj")

        store2 = FaissVectorStore(data_dir=tmp_path, dimension=DIMENSION)
        results = store2.search("proj", vec, top_k=1)
        assert len(results) == 1
        assert results[0]["node_id"] == "n1"
```

- [ ] **Step 2: Run tests to verify failures**

Run: `cd plugins/code && python -m pytest tests/test_vector_store.py -v`

Expected: `TestAddBatch` fails (method doesn't exist). `TestRemoveByFile` and `TestSaveAndReload` may pass with current implementation.

- [ ] **Step 3: Add add_batch to VectorStorePort**

In `plugins/code/app/domain/ports.py`, add to `VectorStorePort` class (after line 33):

```python
class VectorStorePort(Protocol):
    def add(self, project_id: str, node_id: str, embedding: np.ndarray, metadata: dict | None = None) -> None: ...
    def add_batch(self, project_id: str, node_ids: list[str], embeddings: np.ndarray, metadata_list: list[dict]) -> None: ...
    def search(self, project_id: str, query_embedding: np.ndarray, top_k: int = 10) -> list[dict]: ...
    def remove_by_file(self, project_id: str, file_path: str) -> None: ...
    def clear_project(self, project_id: str) -> None: ...
    def save(self, project_id: str) -> None: ...
```

- [ ] **Step 4: Rewrite FaissVectorStore with IDMap2 + add_batch**

Replace `plugins/code/app/infrastructure/vector_store.py` entirely:

```python
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
```

- [ ] **Step 5: Add add_batch to QdrantVectorStore (production backend)**

In `plugins/code/app/infrastructure/qdrant_vector_store.py`, add after the `add()` method (after line 56):

```python
def add_batch(self, project_id: str, node_ids: list[str], embeddings: np.ndarray, metadata_list: list[dict]) -> None:
    if len(node_ids) == 0:
        return
    self._ensure_collection(project_id)
    points = []
    for i, node_id in enumerate(node_ids):
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, node_id))
        payload = {"node_id": node_id, **(metadata_list[i] if i < len(metadata_list) else {})}
        points.append(PointStruct(
            id=point_id,
            vector=embeddings[i].tolist(),
            payload=payload,
        ))
    self._client.upsert(
        collection_name=self._collection_name(project_id),
        points=points,
    )
```

- [ ] **Step 6: Run all vector store tests**

Run: `cd plugins/code && python -m pytest tests/test_vector_store.py -v`

Expected: All tests PASS.

- [ ] **Step 7: Commit**

```bash
git add plugins/code/app/infrastructure/vector_store.py plugins/code/app/infrastructure/qdrant_vector_store.py plugins/code/app/domain/ports.py plugins/code/tests/test_vector_store.py
git commit -m "perf: switch FAISS to IDMap2 for O(1) vector removal + add_batch"
```

---

### Task 3: Fix code-index.json creation

After indexing, write `{project_root}/.claude/code-index.json` with project_id and path. This is needed by other Claude instances to identify the project.

**Files:**
- Modify: `plugins/code/app/services/indexing_service.py:390-395`
- Create: `plugins/code/tests/test_indexing_service.py`

- [ ] **Step 1: Write failing test**

Create `plugins/code/tests/test_indexing_service.py`:

```python
"""Tests for IndexingService — code-index.json creation."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from app.domain.models import ProjectRegistry
from app.services.indexing_service import IndexingService


@pytest.fixture
def mock_graph_store():
    store = MagicMock()
    store.get_all_functions.return_value = []
    return store


@pytest.fixture
def mock_vector_store():
    store = MagicMock()
    return store


@pytest.fixture
def mock_embedding():
    emb = MagicMock()
    emb.generate.return_value = np.zeros(8, dtype=np.float32)
    emb.generate_batch.return_value = np.zeros((1, 8), dtype=np.float32)
    return emb


@pytest.fixture
def service(tmp_path, mock_graph_store, mock_vector_store, mock_embedding):
    return IndexingService(
        graph_store=mock_graph_store,
        vector_store=mock_vector_store,
        embedding=mock_embedding,
        data_dir=tmp_path / "data",
    )


class TestCodeIndexJson:
    def test_index_creates_code_index_json(self, service, tmp_path):
        """After indexing, .claude/code-index.json must exist in target project."""
        project_dir = tmp_path / "my_project"
        project_dir.mkdir()
        (project_dir / "hello.py").write_text("def hello(): pass")

        service.index_directory(project_dir, project_id="test-my_project")

        code_index = project_dir / ".claude" / "code-index.json"
        assert code_index.exists()
        data = json.loads(code_index.read_text())
        assert data["project_id"] == "test-my_project"
        assert data["path"] == str(project_dir.resolve())

    def test_index_updates_existing_code_index_json(self, service, tmp_path):
        """Re-indexing with different project_id updates code-index.json."""
        project_dir = tmp_path / "my_project"
        project_dir.mkdir()
        (project_dir / "hello.py").write_text("def hello(): pass")
        claude_dir = project_dir / ".claude"
        claude_dir.mkdir()
        (claude_dir / "code-index.json").write_text(
            json.dumps({"project_id": "old-id", "path": "/old"})
        )

        service.index_directory(project_dir, project_id="new-my_project")

        data = json.loads((claude_dir / "code-index.json").read_text())
        assert data["project_id"] == "new-my_project"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd plugins/code && python -m pytest tests/test_indexing_service.py::TestCodeIndexJson -v`

Expected: FAIL — `code-index.json` not created.

- [ ] **Step 3: Add _write_code_index_json method to IndexingService**

Add this method to `IndexingService` in `plugins/code/app/services/indexing_service.py` (after `_register_project` method, around line 395):

```python
def _write_code_index_json(self, root: Path, project_id: str) -> None:
    """Write .claude/code-index.json in the target project directory."""
    claude_dir = root / ".claude"
    try:
        claude_dir.mkdir(parents=True, exist_ok=True)
        code_index_path = claude_dir / "code-index.json"
        data = {"project_id": project_id, "path": str(root)}
        tmp_path = code_index_path.with_suffix(".json.tmp")
        tmp_path.write_text(json.dumps(data, indent=2))
        tmp_path.rename(code_index_path)
    except OSError as e:
        logger.warning("Failed to write code-index.json in %s: %s", root, e)
```

Then call it in `index_directory()` at line 174, after `_register_project`:

```python
self._graph_store.save(project_id)
self._vector_store.save(project_id)
self._save_hashes(project_id)
self._register_project(project_id, str(root))
self._write_code_index_json(root, project_id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd plugins/code && python -m pytest tests/test_indexing_service.py::TestCodeIndexJson -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/code/app/services/indexing_service.py plugins/code/tests/test_indexing_service.py
git commit -m "feat: write code-index.json to target project .claude/ after indexing"
```

---

### Task 4: Parallel file parsing + batch embedding

The main indexing loop processes files sequentially. Use ThreadPoolExecutor for tree-sitter parsing (CPU-bound but releases GIL during C calls) and batch embedding operations.

**Files:**
- Modify: `plugins/code/app/services/indexing_service.py:51-184`

- [ ] **Step 1: Write failing test for parallel indexing**

Append to `plugins/code/tests/test_indexing_service.py`:

```python
class TestParallelIndexing:
    def test_index_multiple_files_produces_correct_count(self, service, tmp_path):
        """Indexing a directory with multiple files returns correct totals."""
        project_dir = tmp_path / "multi"
        project_dir.mkdir()
        for i in range(5):
            (project_dir / f"mod{i}.py").write_text(f"def func{i}(): pass\ndef func{i}b(): pass\n")

        info = service.index_directory(project_dir, project_id="test-multi")

        assert info.total_files == 5
        assert info.total_functions == 10

    def test_index_skips_unchanged_files(self, service, tmp_path):
        """Second indexing run skips files that haven't changed."""
        project_dir = tmp_path / "incr"
        project_dir.mkdir()
        (project_dir / "a.py").write_text("def a(): pass")
        (project_dir / "b.py").write_text("def b(): pass")

        info1 = service.index_directory(project_dir, project_id="test-incr")
        assert info1.total_files == 2

        info2 = service.index_directory(project_dir, project_id="test-incr")
        assert info2.total_files == 0
        assert info2.skipped_files == 2
```

- [ ] **Step 2: Run test to verify baseline**

Run: `cd plugins/code && python -m pytest tests/test_indexing_service.py::TestParallelIndexing -v`

Expected: Tests should pass with current sequential implementation (baseline behavior check).

- [ ] **Step 3: Refactor index_directory for parallel parsing + batch operations**

Replace the code file parsing loop in `plugins/code/app/services/indexing_service.py`. Add import at top:

```python
from concurrent.futures import ThreadPoolExecutor, as_completed
```

Replace `index_directory` method (lines 51-184) with:

```python
def index_directory(
    self,
    directory: str | Path,
    project_id: str,
    force: bool = False,
    on_progress: Callable[[str, str], None] | None = None,
) -> ProjectInfo:
    root = Path(directory).resolve()
    if not root.is_dir():
        raise ValueError(f"Not a directory: {root}")

    files = self._discover_files(root)
    total_functions = 0
    total_classes = 0
    indexed_files = 0
    skipped_files = 0
    error_files: list[tuple[str, str]] = []
    all_function_nodes: list[FunctionNode] = []

    # Phase 1: Filter changed files and compute hashes
    files_to_index: list[tuple[Path, str, str]] = []  # (path, rel_path, hash)
    for file_path in files:
        rel_path = str(file_path.relative_to(root))
        try:
            file_hash = self._compute_hash(file_path)
        except OSError as e:
            error_files.append((rel_path, str(e)))
            if on_progress:
                on_progress("error", rel_path)
            continue

        if not force and self._is_unchanged(project_id, rel_path, file_hash):
            skipped_files += 1
            if on_progress:
                on_progress("skip", rel_path)
            continue

        files_to_index.append((file_path, rel_path, file_hash))

    # Phase 2: Parse files in parallel
    def _parse_one(file_path: Path):
        return self._parser.parse_file(file_path)

    parse_results: dict[str, tuple] = {}
    with ThreadPoolExecutor() as pool:
        future_to_rel = {
            pool.submit(_parse_one, fp): (fp, rel, fh)
            for fp, rel, fh in files_to_index
        }
        for future in as_completed(future_to_rel):
            fp, rel, fh = future_to_rel[future]
            try:
                result = future.result()
                if result is not None:
                    parse_results[rel] = (fp, rel, fh, result)
            except Exception as e:
                error_files.append((rel, str(e)))
                logger.warning("Failed to parse %s: %s", rel, e)
                if on_progress:
                    on_progress("error", rel)

    # Phase 3: Build graph + collect embeddings (sequential — graph_store not thread-safe)
    batch_node_ids: list[str] = []
    batch_texts: list[str] = []
    batch_metas: list[dict] = []

    for rel in sorted(parse_results.keys()):
        fp, rel_path, file_hash, (tree, source, language, rules) = parse_results[rel]
        try:
            self._graph_store.remove_file_nodes(project_id, rel_path)
            self._vector_store.remove_by_file(project_id, rel_path)

            extraction = extract_symbols(tree, source, rules)
            func_nodes = build_graph(project_id, rel_path, extraction, self._graph_store)
            all_function_nodes.extend(func_nodes)

            for fn in func_nodes:
                batch_node_ids.append(fn.id)
                batch_texts.append(f"{fn.name} {fn.signature} {fn.file}")
                batch_metas.append({
                    "file": rel_path, "name": fn.name,
                    "signature": fn.signature, "type": "function",
                })

            total_functions += len(extraction.functions)
            total_classes += len(extraction.classes)
            indexed_files += 1
            self._update_hash(project_id, rel_path, file_hash)
            if on_progress:
                on_progress("index", rel_path)
        except Exception as e:
            error_files.append((rel_path, str(e)))
            logger.warning("Failed to index %s: %s", rel_path, e)
            if on_progress:
                on_progress("error", rel_path)

    # Phase 4: Batch embed + batch add to vector store
    if batch_texts:
        embeddings = self._embedding.generate_batch(batch_texts)
        self._vector_store.add_batch(project_id, batch_node_ids, embeddings, batch_metas)

    if all_function_nodes:
        resolve_calls(project_id, all_function_nodes, self._graph_store)

    # Phase 5: Index document files (.md, .txt, .docx, .xlsx, .pdf, ...)
    doc_files = self._discover_docs(root)
    total_docs = 0
    doc_batch_ids: list[str] = []
    doc_batch_texts: list[str] = []
    doc_batch_metas: list[dict] = []

    for doc_path in doc_files:
        rel_path = str(doc_path.relative_to(root))
        try:
            file_hash = self._compute_hash(doc_path)
        except OSError as e:
            error_files.append((rel_path, str(e)))
            continue

        if not force and self._is_unchanged(project_id, rel_path, file_hash):
            skipped_files += 1
            if on_progress:
                on_progress("skip", rel_path)
            continue

        try:
            self._vector_store.remove_by_file(project_id, rel_path)
            chunks = chunk_file(doc_path, rel_path)
            for i, chunk in enumerate(chunks):
                node_id = f"{project_id}::doc::{rel_path}::{i}"
                doc_batch_ids.append(node_id)
                doc_batch_texts.append(f"{chunk.name} {chunk.content}")
                doc_batch_metas.append({
                    "file": rel_path, "name": chunk.name,
                    "type": "document", "content": chunk.content,
                })
            total_docs += len(chunks)
            indexed_files += 1
            self._update_hash(project_id, rel_path, file_hash)
            if on_progress:
                on_progress("index", rel_path)
        except Exception as e:
            error_files.append((rel_path, str(e)))
            logger.warning("Failed to index doc %s: %s", rel_path, e)
            if on_progress:
                on_progress("error", rel_path)

    if doc_batch_texts:
        doc_embeddings = self._embedding.generate_batch(doc_batch_texts)
        self._vector_store.add_batch(project_id, doc_batch_ids, doc_embeddings, doc_batch_metas)

    # Phase 6: Persist
    self._graph_store.save(project_id)
    self._vector_store.save(project_id)
    self._save_hashes(project_id)
    self._register_project(project_id, str(root))
    self._write_code_index_json(root, project_id)

    return ProjectInfo(
        project_id=project_id,
        root_path=str(root),
        total_files=indexed_files,
        total_functions=total_functions,
        total_classes=total_classes,
        skipped_files=skipped_files,
        error_files=error_files,
    )
```

- [ ] **Step 4: Run all tests**

Run: `cd plugins/code && python -m pytest tests/ -v`

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/code/app/services/indexing_service.py plugins/code/tests/test_indexing_service.py
git commit -m "perf: parallel file parsing + batch embedding/vector operations"
```

---

### Task 5: Document pipeline with markitdown

Extend `doc_chunker.py` to support `.docx`, `.xlsx`, `.pdf`, `.pptx`, `.html`, `.csv` by calling `markitdown` CLI to convert them to markdown first, then chunking with existing markdown logic.

**Files:**
- Modify: `plugins/code/app/indexer/doc_chunker.py`
- Modify: `plugins/code/requirements.txt`
- Create: `plugins/code/tests/test_doc_chunker.py`

- [ ] **Step 1: Write failing tests**

Create `plugins/code/tests/test_doc_chunker.py`:

```python
"""Tests for doc_chunker — markdown, text, and rich document support."""

import pytest
from pathlib import Path

from app.indexer.doc_chunker import (
    chunk_file,
    is_supported_doc,
    SUPPORTED_DOC_EXTENSIONS,
    RICH_DOC_EXTENSIONS,
)


class TestSupportedExtensions:
    def test_md_is_supported(self):
        assert is_supported_doc("readme.md")

    def test_txt_is_supported(self):
        assert is_supported_doc("notes.txt")

    def test_docx_is_supported(self):
        assert is_supported_doc("spec.docx")

    def test_pdf_is_supported(self):
        assert is_supported_doc("report.pdf")

    def test_xlsx_is_supported(self):
        assert is_supported_doc("data.xlsx")

    def test_py_is_not_supported(self):
        assert not is_supported_doc("main.py")


class TestMarkdownChunking:
    def test_chunks_by_heading(self, tmp_path):
        md = tmp_path / "doc.md"
        md.write_text("# Title\nIntro text\n## Section\nBody text\n")
        chunks = chunk_file(md, "doc.md")
        assert len(chunks) >= 2
        assert any("Title" in c.name for c in chunks)

    def test_empty_file_returns_no_chunks(self, tmp_path):
        md = tmp_path / "empty.md"
        md.write_text("")
        chunks = chunk_file(md, "empty.md")
        assert chunks == []


class TestTextChunking:
    def test_text_splits_by_paragraphs(self, tmp_path):
        txt = tmp_path / "notes.txt"
        txt.write_text("First paragraph.\n\nSecond paragraph.\n\nThird paragraph.")
        chunks = chunk_file(txt, "notes.txt")
        assert len(chunks) >= 1


class TestRichDocConversion:
    """Tests for markitdown-based conversion. Skipped if markitdown not installed."""

    @pytest.fixture
    def has_markitdown(self):
        import shutil
        if shutil.which("markitdown") is None:
            pytest.skip("markitdown not installed")

    def test_html_converts_to_chunks(self, tmp_path, has_markitdown):
        html = tmp_path / "page.html"
        html.write_text("<html><body><h1>Title</h1><p>Content here.</p></body></html>")
        chunks = chunk_file(html, "page.html")
        assert len(chunks) >= 1
        assert any("Content" in c.content for c in chunks)

    def test_csv_converts_to_chunks(self, tmp_path, has_markitdown):
        csv_file = tmp_path / "data.csv"
        csv_file.write_text("name,age\nAlice,30\nBob,25\n")
        chunks = chunk_file(csv_file, "data.csv")
        assert len(chunks) >= 1
        assert any("Alice" in c.content for c in chunks)
```

- [ ] **Step 2: Run tests to verify failures**

Run: `cd plugins/code && python -m pytest tests/test_doc_chunker.py -v`

Expected: `TestSupportedExtensions::test_docx_is_supported`, `test_pdf_is_supported`, `test_xlsx_is_supported` FAIL. `TestRichDocConversion` tests FAIL (RICH_DOC_EXTENSIONS doesn't exist yet).

- [ ] **Step 3: Add markitdown to requirements.txt**

Append to `plugins/code/requirements.txt` after the `# Local storage` section:

```
# Document conversion
markitdown>=0.1.0
```

- [ ] **Step 4: Rewrite doc_chunker.py with markitdown integration**

Replace `plugins/code/app/indexer/doc_chunker.py`:

```python
"""Document chunker — splits documents into sections for vector indexing.

Supports:
- Markdown (.md): split by headings (h1-h6)
- Plain text (.txt): split by blank lines, merge short paragraphs
- Rich documents (.docx, .xlsx, .pdf, .pptx, .html, .csv, .json, .xml):
  converted to markdown via markitdown CLI, then chunked as markdown.

Max ~1000 chars per chunk.
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

MAX_CHUNK_CHARS = 1000
TXT_MERGE_TARGET = 500

# Native text-based formats (read directly)
SUPPORTED_DOC_EXTENSIONS = {".md", ".txt"}

# Rich formats converted via markitdown
RICH_DOC_EXTENSIONS = {
    ".docx", ".xlsx", ".pdf", ".pptx",
    ".html", ".htm", ".csv", ".json", ".xml",
}

ALL_DOC_EXTENSIONS = SUPPORTED_DOC_EXTENSIONS | RICH_DOC_EXTENSIONS

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)", re.MULTILINE)


@dataclass
class DocChunk:
    name: str
    content: str
    file: str


def is_supported_doc(file_path: str | Path) -> bool:
    return Path(file_path).suffix.lower() in ALL_DOC_EXTENSIONS


def chunk_file(file_path: Path, rel_path: str) -> list[DocChunk]:
    suffix = file_path.suffix.lower()

    if suffix == ".md":
        text = file_path.read_text(encoding="utf-8", errors="replace")
        if not text.strip():
            return []
        return _chunk_markdown(text, rel_path)

    if suffix == ".txt":
        text = file_path.read_text(encoding="utf-8", errors="replace")
        if not text.strip():
            return []
        return _chunk_text(text, rel_path)

    if suffix in RICH_DOC_EXTENSIONS:
        return _chunk_rich_doc(file_path, rel_path)

    return []


def _chunk_rich_doc(file_path: Path, rel_path: str) -> list[DocChunk]:
    """Convert rich document to markdown via markitdown, then chunk."""
    markitdown_bin = shutil.which("markitdown")
    if markitdown_bin is None:
        logger.warning("markitdown not installed, skipping %s", rel_path)
        return []

    try:
        result = subprocess.run(
            [markitdown_bin, str(file_path)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            logger.warning("markitdown failed for %s: %s", rel_path, result.stderr[:200])
            return []

        md_text = result.stdout
        if not md_text.strip():
            return []

        return _chunk_markdown(md_text, rel_path)
    except subprocess.TimeoutExpired:
        logger.warning("markitdown timed out for %s", rel_path)
        return []
    except Exception as e:
        logger.warning("markitdown error for %s: %s", rel_path, e)
        return []


def _chunk_markdown(text: str, rel_path: str) -> list[DocChunk]:
    sections: list[tuple[str, str]] = []
    last_pos = 0
    last_title = Path(rel_path).stem

    for match in _HEADING_RE.finditer(text):
        before = text[last_pos:match.start()].strip()
        if before:
            sections.append((last_title, before))

        last_title = match.group(2).strip()
        last_pos = match.end()

    remaining = text[last_pos:].strip()
    if remaining:
        sections.append((last_title, remaining))

    chunks: list[DocChunk] = []
    for title, content in sections:
        for piece in _split_long(content):
            chunks.append(DocChunk(name=title, content=piece, file=rel_path))
    return chunks


def _chunk_text(text: str, rel_path: str) -> list[DocChunk]:
    paragraphs = re.split(r"\n\s*\n", text)
    stem = Path(rel_path).stem

    merged: list[str] = []
    buf = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if buf and len(buf) + len(para) + 1 > TXT_MERGE_TARGET:
            merged.append(buf)
            buf = para
        else:
            buf = f"{buf}\n{para}" if buf else para

    if buf:
        merged.append(buf)

    chunks: list[DocChunk] = []
    for i, block in enumerate(merged):
        for piece in _split_long(block):
            name = f"{stem} (part {i + 1})" if len(merged) > 1 else stem
            chunks.append(DocChunk(name=name, content=piece, file=rel_path))
    return chunks


def _split_long(text: str) -> list[str]:
    if len(text) <= MAX_CHUNK_CHARS:
        return [text]

    pieces: list[str] = []
    while text:
        if len(text) <= MAX_CHUNK_CHARS:
            pieces.append(text)
            break

        cut = text.rfind("\n", 0, MAX_CHUNK_CHARS)
        if cut <= 0:
            cut = text.rfind(" ", 0, MAX_CHUNK_CHARS)
        if cut <= 0:
            cut = MAX_CHUNK_CHARS

        pieces.append(text[:cut].rstrip())
        text = text[cut:].lstrip()

    return pieces
```

- [ ] **Step 5: Run all doc_chunker tests**

Run: `cd plugins/code && python -m pytest tests/test_doc_chunker.py -v`

Expected: All tests PASS (rich doc tests skipped if markitdown not available, but it IS installed).

- [ ] **Step 6: Commit**

```bash
git add plugins/code/app/indexer/doc_chunker.py plugins/code/tests/test_doc_chunker.py plugins/code/requirements.txt
git commit -m "feat: add document support (docx/xlsx/pdf/html/csv) via markitdown"
```

---

### Task 6: Update hook to support document files

The `post_tool_reindex.py` hook only triggers re-indexing for code files. It should also trigger for supported document extensions.

**Files:**
- Modify: `plugins/code/hooks/post_tool_reindex.py:22-28`

- [ ] **Step 1: Update SUPPORTED_EXTENSIONS in hook**

In `plugins/code/hooks/post_tool_reindex.py`, replace the `SUPPORTED_EXTENSIONS` set (lines 22-28):

```python
# Extensions supported by CodeParser + doc_chunker
SUPPORTED_EXTENSIONS = {
    # Code
    ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".go", ".rs", ".java",
    ".c", ".h", ".cpp", ".cc", ".cxx", ".hpp", ".hxx",
    ".php",
    # Documents
    ".md", ".txt",
    ".docx", ".xlsx", ".pdf", ".pptx",
    ".html", ".htm", ".csv", ".json", ".xml",
}
```

- [ ] **Step 2: Commit**

```bash
git add plugins/code/hooks/post_tool_reindex.py
git commit -m "feat: hook triggers re-index for document files too"
```

---

### Task 7: Integration test — full round-trip

End-to-end test: index a directory with code + documents, search, verify results.

**Files:**
- Modify: `plugins/code/tests/test_indexing_service.py`

- [ ] **Step 1: Write integration test**

Append to `plugins/code/tests/test_indexing_service.py`:

```python
from app.container import create_container
from app.config import AppConfig, StorageConfig, EmbeddingConfig, ServerConfig, Neo4jConfig, QdrantConfig, PostgresConfig, RedisConfig


class TestIntegrationRoundTrip:
    def test_index_and_search_code(self, tmp_path):
        """Full round-trip: index Python files, search, get results."""
        data_dir = tmp_path / "data"
        config = AppConfig(
            storage=StorageConfig(backend="local", data_dir=data_dir),
            neo4j=Neo4jConfig(), qdrant=QdrantConfig(), postgres=PostgresConfig(),
            redis=RedisConfig(), embedding=EmbeddingConfig(dimension=128),
            server=ServerConfig(),
        )
        container = create_container(config)

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "auth.py").write_text(
            "def authenticate_user(username, password):\n    return True\n"
        )
        (project_dir / "README.md").write_text(
            "# My Project\nThis is the authentication service.\n"
        )

        info = container.indexing_service.index_directory(
            project_dir, project_id="test-project"
        )
        assert info.total_files >= 1
        assert info.total_functions >= 1

        # Search for code
        result = container.search_service.search(
            project_id="test-project", query="authenticate user", top_k=5,
        )
        assert len(result.functions) + len(result.documents) > 0

        # Verify code-index.json
        code_index = project_dir / ".claude" / "code-index.json"
        assert code_index.exists()

    def test_index_and_search_document(self, tmp_path):
        """Index markdown document, search returns document chunks."""
        data_dir = tmp_path / "data"
        config = AppConfig(
            storage=StorageConfig(backend="local", data_dir=data_dir),
            neo4j=Neo4jConfig(), qdrant=QdrantConfig(), postgres=PostgresConfig(),
            redis=RedisConfig(), embedding=EmbeddingConfig(dimension=128),
            server=ServerConfig(),
        )
        container = create_container(config)

        project_dir = tmp_path / "docs_project"
        project_dir.mkdir()
        (project_dir / "guide.md").write_text(
            "# Setup Guide\nInstall dependencies with pip install.\n\n"
            "## Configuration\nSet DATABASE_URL environment variable.\n"
        )

        info = container.indexing_service.index_directory(
            project_dir, project_id="test-docs"
        )
        assert info.total_files >= 1

        result = container.search_service.search(
            project_id="test-docs", query="database configuration", top_k=5,
        )
        assert len(result.documents) > 0
```

- [ ] **Step 2: Run integration tests**

Run: `cd plugins/code && python -m pytest tests/test_indexing_service.py::TestIntegrationRoundTrip -v`

Expected: All PASS.

- [ ] **Step 3: Run full test suite**

Run: `cd plugins/code && python -m pytest tests/ -v`

Expected: All tests PASS.

- [ ] **Step 4: Commit**

```bash
git add plugins/code/tests/test_indexing_service.py
git commit -m "test: integration tests for full index-search round-trip"
```

---

### Task 8: Update index skill description

Update the SKILL.md to document the new document support and performance improvements.

**Files:**
- Modify: `plugins/code/skills/index/SKILL.md`

- [ ] **Step 1: Update SKILL.md**

Replace lines 37-38 in `plugins/code/skills/index/SKILL.md`:

```markdown
## Notes

- Supported code: `.py`, `.ts`, `.tsx`, `.js`, `.jsx`, `.go`, `.rs`, `.java`, `.c`, `.h`, `.cpp`, `.cc`, `.php`
- Supported documents: `.md`, `.txt`, `.docx`, `.xlsx`, `.pdf`, `.pptx`, `.html`, `.csv`, `.json`, `.xml`
- Document conversion uses `markitdown` (auto-installed) — converts rich documents to markdown for chunking
- Incremental indexing: unchanged files (by SHA-256) are skipped unless `--force` is used
- Data is stored in the shared data directory (`~/.code-intelligence/data/`)
- After indexing, a `.claude/code-index.json` marker file is written to the target project directory
- For multi-repo projects, use the naming convention `{group}-{reponame}` so repos in the same group can search across each other with wildcard `{group}-*`
```

- [ ] **Step 2: Commit**

```bash
git add plugins/code/skills/index/SKILL.md
git commit -m "docs: update index skill with document support and code-index.json info"
```
