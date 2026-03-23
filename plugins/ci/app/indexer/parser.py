"""AST parser using tree-sitter.

Supports multiple languages via the language registry.
Parses source files into tree-sitter AST trees.
"""

from __future__ import annotations

from pathlib import Path

from tree_sitter import Language, Parser

from app.indexer.languages import LangRules, get_lang_spec, get_supported_extensions


class CodeParser:
    def __init__(self):
        self._parsers: dict[int, Parser] = {}

    def _get_parser(self, language: Language) -> Parser:
        lang_id = id(language)
        if lang_id not in self._parsers:
            parser = Parser(language)
            self._parsers[lang_id] = parser
        return self._parsers[lang_id]

    def parse_file(self, file_path: str | Path) -> tuple | None:
        """Parse a file and return (tree, source_bytes, language, rules).

        Returns None if the file extension is not supported.
        """
        path = Path(file_path)
        spec = get_lang_spec(path.suffix)
        if spec is None:
            return None

        source = path.read_bytes()
        parser = self._get_parser(spec.language)
        tree = parser.parse(source)
        return tree, source, spec.language, spec.rules

    def parse_source(self, source: str, language: Language | None = None, rules: LangRules | None = None) -> tuple:
        """Parse source code string directly."""
        if language is None:
            spec = get_lang_spec(".py")
            if spec is None:
                raise RuntimeError("No Python grammar available")
            language = spec.language
            rules = spec.rules
        parser = self._get_parser(language)
        source_bytes = source.encode("utf-8")
        tree = parser.parse(source_bytes)
        return tree, source_bytes, language, rules

    @staticmethod
    def is_supported(file_path: str | Path) -> bool:
        return Path(file_path).suffix in get_supported_extensions()

    @staticmethod
    def supported_extensions() -> set[str]:
        return get_supported_extensions()
