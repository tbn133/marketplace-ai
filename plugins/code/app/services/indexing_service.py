"""Indexing service — orchestrates the index pipeline.

Depends only on domain ports for storage and embedding.
Uses indexer/ modules for pure parsing logic.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from app.domain.models import FileRecord, FunctionNode, ProjectInfo, ProjectRegistry
from app.domain.ports import EmbeddingPort, GraphStorePort, VectorStorePort
from app.indexer.doc_chunker import chunk_file, is_supported_doc
from app.indexer.extractor import extract_symbols
from app.indexer.graph_builder import build_graph, resolve_calls
from app.indexer.parser import CodeParser

logger = logging.getLogger(__name__)

IGNORE_DIRS = {
    ".git", ".claude", "__pycache__", "node_modules",
    ".venv", "venv", "env",
    ".tox", ".nox", ".mypy_cache", ".ruff_cache", ".pytest_cache", ".pytype",
    "build", "dist", ".eggs", "site-packages",
    ".idea", ".vscode",
}


class IndexingService:
    def __init__(
        self,
        graph_store: GraphStorePort,
        vector_store: VectorStorePort,
        embedding: EmbeddingPort,
        data_dir: Path | None = None,
    ):
        self._graph_store = graph_store
        self._vector_store = vector_store
        self._embedding = embedding
        self._parser = CodeParser()
        self._data_dir = data_dir
        self._file_hashes: dict[str, dict[str, FileRecord]] = {}
        self._registry: dict[str, ProjectRegistry] = {}
        self._load_registry()

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

            try:
                self._graph_store.remove_file_nodes(project_id, rel_path)
                self._vector_store.remove_by_file(project_id, rel_path)

                result = self._parser.parse_file(file_path)
                if result is None:
                    continue
                tree, source, language, rules = result

                extraction = extract_symbols(tree, source, rules)
                func_nodes = build_graph(project_id, rel_path, extraction, self._graph_store)
                all_function_nodes.extend(func_nodes)

                for fn in func_nodes:
                    text = f"{fn.name} {fn.signature} {fn.file}"
                    vec = self._embedding.generate(text)
                    self._vector_store.add(
                        project_id=project_id,
                        node_id=fn.id,
                        embedding=vec,
                        metadata={"file": rel_path, "name": fn.name, "signature": fn.signature, "type": "function"},
                    )

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

        if all_function_nodes:
            resolve_calls(project_id, all_function_nodes, self._graph_store)

        # Index document files (.md, .txt)
        doc_files = self._discover_docs(root)
        total_docs = 0
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
                    text = f"{chunk.name} {chunk.content}"
                    vec = self._embedding.generate(text)
                    self._vector_store.add(
                        project_id=project_id,
                        node_id=node_id,
                        embedding=vec,
                        metadata={
                            "file": rel_path,
                            "name": chunk.name,
                            "type": "document",
                            "content": chunk.content,
                        },
                    )
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

    def get_project_status(self, project_id: str) -> dict:
        self._load_hashes(project_id)
        hashes = self._file_hashes.get(project_id, {})
        functions = self._graph_store.get_all_functions(project_id)
        unique_files = {f["file"] for f in functions}
        return {
            "project_id": project_id,
            "indexed_files": len(hashes),
            "total_functions": len(functions),
            "files": sorted(unique_files),
            "has_data": len(hashes) > 0,
        }

    def _discover_files(self, root: Path) -> list[Path]:
        files = []
        for path in root.rglob("*"):
            if path.is_file() and CodeParser.is_supported(path):
                if not any(part in IGNORE_DIRS for part in path.parts):
                    files.append(path)
        return sorted(files)

    def _discover_docs(self, root: Path) -> list[Path]:
        docs = []
        for path in root.rglob("*"):
            if path.is_file() and is_supported_doc(path):
                if not any(part in IGNORE_DIRS for part in path.parts):
                    docs.append(path)
        return sorted(docs)

    @staticmethod
    def _compute_hash(file_path: Path) -> str:
        return hashlib.sha256(file_path.read_bytes()).hexdigest()

    def _hashes_path(self, project_id: str) -> Path | None:
        if self._data_dir is None:
            return None
        return self._data_dir / f"hashes_{project_id}.json"

    def _load_hashes(self, project_id: str) -> None:
        if project_id in self._file_hashes:
            return
        path = self._hashes_path(project_id)
        if path is not None and path.exists():
            raw = json.loads(path.read_text())
            self._file_hashes[project_id] = {
                k: FileRecord(**v) for k, v in raw.items()
            }
        else:
            self._file_hashes[project_id] = {}

    def _save_hashes(self, project_id: str) -> None:
        path = self._hashes_path(project_id)
        if path is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        records = self._file_hashes.get(project_id, {})
        raw = {k: v.__dict__ for k, v in records.items()}
        path.write_text(json.dumps(raw, indent=2))

    def _is_unchanged(self, project_id: str, rel_path: str, file_hash: str) -> bool:
        self._load_hashes(project_id)
        records = self._file_hashes.get(project_id, {})
        existing = records.get(rel_path)
        return existing is not None and existing.file_hash == file_hash

    def _update_hash(self, project_id: str, rel_path: str, file_hash: str) -> None:
        if project_id not in self._file_hashes:
            self._file_hashes[project_id] = {}
        self._file_hashes[project_id][rel_path] = FileRecord(
            path=rel_path,
            project_id=project_id,
            file_hash=file_hash,
            indexed_at=datetime.now(timezone.utc).isoformat(),
        )

    # ── Incremental file-level operations ──────────────────────────

    def index_files(
        self,
        file_paths: list[Path],
        project_id: str,
        root: Path,
    ) -> ProjectInfo:
        """Re-index specific files (incremental). Used by watcher."""
        total_functions = 0
        total_classes = 0
        indexed_files = 0
        error_files: list[tuple[str, str]] = []
        all_function_nodes: list[FunctionNode] = []

        for file_path in file_paths:
            rel_path = str(file_path.relative_to(root))
            try:
                file_hash = self._compute_hash(file_path)
                if self._is_unchanged(project_id, rel_path, file_hash):
                    continue

                # Document files
                if is_supported_doc(file_path):
                    self._vector_store.remove_by_file(project_id, rel_path)
                    chunks = chunk_file(file_path, rel_path)
                    for i, chunk in enumerate(chunks):
                        node_id = f"{project_id}::doc::{rel_path}::{i}"
                        text = f"{chunk.name} {chunk.content}"
                        vec = self._embedding.generate(text)
                        self._vector_store.add(
                            project_id=project_id,
                            node_id=node_id,
                            embedding=vec,
                            metadata={
                                "file": rel_path,
                                "name": chunk.name,
                                "type": "document",
                                "content": chunk.content,
                            },
                        )
                    indexed_files += 1
                    self._update_hash(project_id, rel_path, file_hash)
                    continue

                # Code files
                self._graph_store.remove_file_nodes(project_id, rel_path)
                self._vector_store.remove_by_file(project_id, rel_path)

                result = self._parser.parse_file(file_path)
                if result is None:
                    continue
                tree, source, language, rules = result

                extraction = extract_symbols(tree, source, rules)
                func_nodes = build_graph(project_id, rel_path, extraction, self._graph_store)
                all_function_nodes.extend(func_nodes)

                for fn in func_nodes:
                    text = f"{fn.name} {fn.signature} {fn.file}"
                    vec = self._embedding.generate(text)
                    self._vector_store.add(
                        project_id=project_id,
                        node_id=fn.id,
                        embedding=vec,
                        metadata={"file": rel_path, "name": fn.name, "signature": fn.signature, "type": "function"},
                    )

                total_functions += len(extraction.functions)
                total_classes += len(extraction.classes)
                indexed_files += 1
                self._update_hash(project_id, rel_path, file_hash)
            except Exception as e:
                error_files.append((rel_path, str(e)))
                logger.warning("Failed to index %s: %s", rel_path, e)

        if all_function_nodes:
            resolve_calls(project_id, all_function_nodes, self._graph_store)

        self._graph_store.save(project_id)
        self._vector_store.save(project_id)
        self._save_hashes(project_id)

        return ProjectInfo(
            project_id=project_id,
            root_path=str(root),
            total_files=indexed_files,
            total_functions=total_functions,
            total_classes=total_classes,
            error_files=error_files,
        )

    def remove_deleted_file(self, project_id: str, rel_path: str) -> None:
        """Remove a deleted file's data from stores."""
        self._graph_store.remove_file_nodes(project_id, rel_path)
        self._vector_store.remove_by_file(project_id, rel_path)

        self._load_hashes(project_id)
        hashes = self._file_hashes.get(project_id, {})
        hashes.pop(rel_path, None)

        self._graph_store.save(project_id)
        self._vector_store.save(project_id)
        self._save_hashes(project_id)
        logger.info("Removed deleted file from index: %s", rel_path)

    # ── Project registry ───────────────────────────────────────────

    def _registry_path(self) -> Path | None:
        if self._data_dir is None:
            return None
        return self._data_dir / "registry.json"

    def _load_registry(self) -> None:
        path = self._registry_path()
        if path is not None and path.exists():
            raw = json.loads(path.read_text())
            self._registry = {
                k: ProjectRegistry(**v) for k, v in raw.items()
            }
        else:
            self._registry = {}

    def _save_registry(self) -> None:
        path = self._registry_path()
        if path is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = {k: v.__dict__ for k, v in self._registry.items()}
        path.write_text(json.dumps(raw, indent=2))

    def _register_project(self, project_id: str, root_path: str) -> None:
        self._registry[project_id] = ProjectRegistry(
            project_id=project_id,
            root_path=root_path,
        )
        self._save_registry()

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

    def get_project_root(self, project_id: str) -> Path | None:
        """Get the registered root path for a project."""
        reg = self._registry.get(project_id)
        if reg is None:
            return None
        root = Path(reg.root_path)
        return root if root.is_dir() else None

    def list_projects(self, group_prefix: str | None = None) -> list[ProjectRegistry]:
        """List all registered projects, optionally filtered by group prefix.

        If group_prefix is given, returns only projects whose ID starts with
        "{group_prefix}-".  E.g. group_prefix="myapp" matches "myapp-backend",
        "myapp-frontend", etc.
        """
        self._load_registry()
        if group_prefix is None:
            return list(self._registry.values())
        prefix = f"{group_prefix}-"
        return [r for r in self._registry.values() if r.project_id.startswith(prefix)]

    def resolve_project_ids(self, project_id: str) -> list[str]:
        """Resolve a project_id that may contain a wildcard.

        - "myapp-backend"  → ["myapp-backend"]  (exact match)
        - "myapp-*"        → ["myapp-backend", "myapp-frontend", ...]  (prefix match)
        """
        if not project_id.endswith("-*"):
            return [project_id]
        prefix = project_id[:-1]  # "myapp-*" → "myapp-"
        self._load_registry()
        return sorted(pid for pid in self._registry if pid.startswith(prefix))
