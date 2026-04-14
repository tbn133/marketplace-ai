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
