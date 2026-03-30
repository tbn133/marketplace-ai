"""Document chunker — splits .md and .txt files into sections for vector indexing.

Markdown: split by headings (h1–h6), each section becomes a chunk with its title.
Plain text: split by blank lines, merge short paragraphs up to ~500 chars.
Max ~1000 chars per chunk.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

MAX_CHUNK_CHARS = 1000
TXT_MERGE_TARGET = 500

SUPPORTED_DOC_EXTENSIONS = {".md", ".txt"}

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)", re.MULTILINE)


@dataclass
class DocChunk:
    name: str
    content: str
    file: str


def is_supported_doc(file_path: str | Path) -> bool:
    return Path(file_path).suffix.lower() in SUPPORTED_DOC_EXTENSIONS


def chunk_file(file_path: Path, rel_path: str) -> list[DocChunk]:
    suffix = file_path.suffix.lower()
    text = file_path.read_text(encoding="utf-8", errors="replace")
    if not text.strip():
        return []

    if suffix == ".md":
        return _chunk_markdown(text, rel_path)
    if suffix == ".txt":
        return _chunk_text(text, rel_path)
    return []


def _chunk_markdown(text: str, rel_path: str) -> list[DocChunk]:
    sections: list[tuple[str, str]] = []
    last_pos = 0
    last_title = Path(rel_path).stem

    for match in _HEADING_RE.finditer(text):
        # Flush previous section
        before = text[last_pos:match.start()].strip()
        if before:
            sections.append((last_title, before))

        last_title = match.group(2).strip()
        last_pos = match.end()

    # Flush remaining
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

        # Try to split at last newline within limit
        cut = text.rfind("\n", 0, MAX_CHUNK_CHARS)
        if cut <= 0:
            # Fall back to space
            cut = text.rfind(" ", 0, MAX_CHUNK_CHARS)
        if cut <= 0:
            cut = MAX_CHUNK_CHARS

        pieces.append(text[:cut].rstrip())
        text = text[cut:].lstrip()

    return pieces
