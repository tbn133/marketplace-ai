"""Tests for IndexingService — code-index.json creation."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

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
    emb.generate_batch.side_effect = lambda texts: np.zeros((len(texts), 8), dtype=np.float32)
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

        service.index_directory(project_dir, project_id="new-my_project", force=True)

        data = json.loads((claude_dir / "code-index.json").read_text())
        assert data["project_id"] == "new-my_project"


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
