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
