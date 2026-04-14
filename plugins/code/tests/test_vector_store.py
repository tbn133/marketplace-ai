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
