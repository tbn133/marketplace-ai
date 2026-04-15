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
