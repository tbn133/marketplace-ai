"""AST parser using tree-sitter.

Parses Python source files into tree-sitter AST trees.
Extensible to support more languages.
"""

from __future__ import annotations

from pathlib import Path

import tree_sitter_python as tspython
from tree_sitter import Language, Parser

PY_LANGUAGE = Language(tspython.language())

SUPPORTED_EXTENSIONS = {
    ".py": PY_LANGUAGE,
}


class CodeParser:
    def __init__(self):
        self._parsers: dict[str, Parser] = {}

    def _get_parser(self, language: Language) -> Parser:
        lang_id = str(id(language))
        if lang_id not in self._parsers:
            parser = Parser(language)
            self._parsers[lang_id] = parser
        return self._parsers[lang_id]

    def parse_file(self, file_path: str | Path) -> tuple | None:
        """Parse a file and return (tree, source_bytes, language).

        Returns None if the file extension is not supported.
        """
        path = Path(file_path)
        ext = path.suffix
        if ext not in SUPPORTED_EXTENSIONS:
            return None

        language = SUPPORTED_EXTENSIONS[ext]
        source = path.read_bytes()
        parser = self._get_parser(language)
        tree = parser.parse(source)
        return tree, source, language

    def parse_source(self, source: str, language: Language | None = None) -> tuple:
        """Parse source code string directly."""
        lang = language or PY_LANGUAGE
        parser = self._get_parser(lang)
        source_bytes = source.encode("utf-8")
        tree = parser.parse(source_bytes)
        return tree, source_bytes, lang

    @staticmethod
    def is_supported(file_path: str | Path) -> bool:
        return Path(file_path).suffix in SUPPORTED_EXTENSIONS
