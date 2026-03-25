"""Watcher service — monitors filesystem changes and triggers incremental re-index.

Uses watchdog for cross-platform file watching with debounce to batch rapid edits.
Depends only on IndexingService for re-indexing logic.
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Callable

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from app.indexer.parser import CodeParser
from app.services.indexing_service import IGNORE_DIRS, IndexingService

logger = logging.getLogger(__name__)


class _DebouncedHandler(FileSystemEventHandler):
    """Collects file change events and dispatches them after a debounce window."""

    def __init__(
        self,
        project_id: str,
        root: Path,
        indexing_service: IndexingService,
        debounce_seconds: float = 2.0,
        on_reindex: Callable[[str, int, int], None] | None = None,
    ):
        super().__init__()
        self._project_id = project_id
        self._root = root
        self._indexing_service = indexing_service
        self._debounce = debounce_seconds
        self._on_reindex = on_reindex

        self._changed: set[Path] = set()
        self._deleted: set[str] = set()
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None

    def _should_ignore(self, path: str) -> bool:
        p = Path(path)
        if any(part in IGNORE_DIRS for part in p.parts):
            return True
        if not CodeParser.is_supported(p):
            return True
        return False

    def on_created(self, event: FileSystemEvent) -> None:
        if event.is_directory or self._should_ignore(event.src_path):
            return
        self._schedule(changed=Path(event.src_path))

    def on_modified(self, event: FileSystemEvent) -> None:
        if event.is_directory or self._should_ignore(event.src_path):
            return
        self._schedule(changed=Path(event.src_path))

    def on_deleted(self, event: FileSystemEvent) -> None:
        if event.is_directory or self._should_ignore(event.src_path):
            return
        try:
            rel = str(Path(event.src_path).relative_to(self._root))
        except ValueError:
            return
        self._schedule(deleted=rel)

    def on_moved(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        # Treat move as delete old + create new
        if not self._should_ignore(event.src_path):
            try:
                rel = str(Path(event.src_path).relative_to(self._root))
                self._schedule(deleted=rel)
            except ValueError:
                pass
        if hasattr(event, "dest_path") and not self._should_ignore(event.dest_path):
            self._schedule(changed=Path(event.dest_path))

    def _schedule(
        self,
        changed: Path | None = None,
        deleted: str | None = None,
    ) -> None:
        with self._lock:
            if changed is not None:
                self._changed.add(changed)
            if deleted is not None:
                self._deleted.add(deleted)

            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self._debounce, self._flush)
            self._timer.daemon = True
            self._timer.start()

    def _flush(self) -> None:
        with self._lock:
            changed = list(self._changed)
            deleted = list(self._deleted)
            self._changed.clear()
            self._deleted.clear()

        if not changed and not deleted:
            return

        # Handle deletions
        for rel_path in deleted:
            try:
                self._indexing_service.remove_deleted_file(self._project_id, rel_path)
                logger.info("Removed: %s", rel_path)
            except Exception as e:
                logger.warning("Failed to remove %s: %s", rel_path, e)

        # Handle changed/new files
        if changed:
            # Filter out files that no longer exist (rapid create+delete)
            existing = [p for p in changed if p.exists()]
            if existing:
                try:
                    info = self._indexing_service.index_files(
                        existing, self._project_id, self._root,
                    )
                    if info.total_files > 0:
                        logger.info(
                            "Re-indexed %d files (%d functions, %d classes)",
                            info.total_files, info.total_functions, info.total_classes,
                        )
                    if self._on_reindex:
                        self._on_reindex(self._project_id, info.total_files, len(deleted))
                except Exception as e:
                    logger.error("Re-index failed: %s", e)
        elif deleted and self._on_reindex:
            self._on_reindex(self._project_id, 0, len(deleted))


class WatcherService:
    """Watches a project directory for file changes and triggers incremental re-index."""

    def __init__(self, indexing_service: IndexingService):
        self._indexing_service = indexing_service

    def watch(
        self,
        project_id: str,
        root: Path | None = None,
        debounce_seconds: float = 2.0,
        on_reindex: Callable[[str, int, int], None] | None = None,
    ) -> None:
        """Start watching a project directory. Blocks until interrupted.

        Args:
            project_id: Project to watch.
            root: Directory to watch. If None, looks up from project registry.
            debounce_seconds: Seconds to wait before batching changes.
            on_reindex: Callback(project_id, indexed_count, deleted_count) after each re-index.
        """
        if root is None:
            root = self._indexing_service.get_project_root(project_id)
            if root is None:
                raise ValueError(
                    f"Project '{project_id}' has no registered root path. "
                    f"Run 'index' first to register it."
                )

        root = root.resolve()
        if not root.is_dir():
            raise ValueError(f"Not a directory: {root}")

        handler = _DebouncedHandler(
            project_id=project_id,
            root=root,
            indexing_service=self._indexing_service,
            debounce_seconds=debounce_seconds,
            on_reindex=on_reindex,
        )

        observer = Observer()
        observer.schedule(handler, str(root), recursive=True)
        observer.start()
        logger.info("Watching '%s' for project '%s' (debounce=%ss)", root, project_id, debounce_seconds)

        try:
            while observer.is_alive():
                observer.join(timeout=1)
        except KeyboardInterrupt:
            pass
        finally:
            observer.stop()
            observer.join()
            logger.info("Watcher stopped for project '%s'", project_id)
