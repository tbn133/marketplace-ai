"""Symbol extractor from tree-sitter AST.

Extracts functions, classes, imports, and call expressions from parsed AST.
Language-agnostic — uses LangRules to determine AST node types.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.indexer.languages import LangRules


@dataclass
class ExtractedFunction:
    name: str
    start_line: int
    end_line: int
    signature: str
    calls: list[str] = field(default_factory=list)
    parent_class: str | None = None


@dataclass
class ExtractedClass:
    name: str
    start_line: int
    end_line: int
    methods: list[str] = field(default_factory=list)


@dataclass
class ExtractedImport:
    module: str
    names: list[str] = field(default_factory=list)


@dataclass
class ExtractionResult:
    functions: list[ExtractedFunction] = field(default_factory=list)
    classes: list[ExtractedClass] = field(default_factory=list)
    imports: list[ExtractedImport] = field(default_factory=list)


def _node_text(node, source: bytes) -> str:
    return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def _extract_calls(node, source: bytes, rules: LangRules) -> list[str]:
    """Recursively extract all function call names from a node."""
    calls = []
    if node.type in rules.call_types:
        func_node = node.child_by_field_name("function")
        if func_node:
            text = _node_text(func_node, source)
            # Handle method calls: obj.method -> method, obj::method -> method
            for sep in (".", "::", "->"):
                if sep in text:
                    text = text.split(sep)[-1]
                    break
            calls.append(text)
        else:
            # Java method_invocation uses "name" field
            name_node = node.child_by_field_name("name")
            if name_node:
                calls.append(_node_text(name_node, source))
    for child in node.children:
        calls.extend(_extract_calls(child, source, rules))
    return calls


def _extract_func_name(node, source: bytes, rules: LangRules) -> str | None:
    """Extract function name from a function node. Handles C/C++ declarators."""
    name_node = node.child_by_field_name(rules.name_field)
    if name_node is None:
        return None
    text = _node_text(name_node, source)
    # C/C++ declarator may include parens: "func_name(params)" -> "func_name"
    if "(" in text:
        text = text.split("(")[0]
    # Strip pointer/reference decorators
    text = text.lstrip("*&")
    return text if text else None


def _extract_signature(node, source: bytes, rules: LangRules) -> str:
    """Extract function signature."""
    name = _extract_func_name(node, source, rules) or "?"
    params_node = node.child_by_field_name(rules.params_field)
    params = _node_text(params_node, source) if params_node else "()"

    ret = ""
    if rules.return_field:
        ret_node = node.child_by_field_name(rules.return_field)
        if ret_node:
            ret_text = _node_text(ret_node, source)
            if rules.func_keyword in ("def", "fn"):
                ret = f" -> {ret_text}"
            else:
                ret = f" {ret_text}"

    keyword = f"{rules.func_keyword} " if rules.func_keyword else ""
    return f"{keyword}{name}{params}{ret}"


def extract_symbols(tree, source: bytes, rules: LangRules | None = None) -> ExtractionResult:
    """Extract all symbols from a parsed AST tree."""
    if rules is None:
        from app.indexer.languages import PYTHON_RULES
        rules = PYTHON_RULES
    result = ExtractionResult()
    root = tree.root_node
    _walk(root, source, result, rules, parent_class=None)
    return result


def _walk(
    node,
    source: bytes,
    result: ExtractionResult,
    rules: LangRules,
    parent_class: str | None,
) -> None:
    # -- Functions --
    if node.type in rules.func_types:
        name = _extract_func_name(node, source, rules)
        if name:
            calls = _extract_calls(node, source, rules)
            calls = [c for c in calls if c != name]
            func = ExtractedFunction(
                name=name,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                signature=_extract_signature(node, source, rules),
                calls=calls,
                parent_class=parent_class,
            )
            result.functions.append(func)

            if parent_class:
                for cls in result.classes:
                    if cls.name == parent_class:
                        cls.methods.append(name)
                        break
        return  # Don't recurse into function body for nested funcs

    # -- Classes / Structs / Impls --
    if node.type in rules.class_types:
        name_node = node.child_by_field_name("name")
        if name_node:
            cls_name = _node_text(name_node, source)
            cls = ExtractedClass(
                name=cls_name,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
            )
            result.classes.append(cls)
            for child in node.children:
                _walk(child, source, result, rules, parent_class=cls_name)
        return

    # -- Imports --
    if node.type in rules.import_types:
        _extract_import(node, source, result, rules)
        return

    for child in node.children:
        _walk(child, source, result, rules, parent_class=parent_class)


def _extract_import(
    node,
    source: bytes,
    result: ExtractionResult,
    rules: LangRules,
) -> None:
    """Extract import information from an import node."""
    text = _node_text(node, source).strip()

    # Try to get module from the designated field
    module_node = node.child_by_field_name(rules.import_module_field) if rules.import_module_field else None

    if module_node:
        module = _node_text(module_node, source).strip().strip("\"'`")
    else:
        # Fallback: parse from full text
        module = _parse_import_text(text)

    # Extract imported names from child nodes
    names = []
    for child in node.children:
        if child.type in ("dotted_name", "identifier", "import_specifier", "scoped_identifier"):
            name_text = _node_text(child, source)
            if name_text != module and name_text not in ("import", "from", "use", "pub"):
                names.append(name_text)
        elif child.type == "aliased_import":
            name_child = child.child_by_field_name("name")
            if name_child:
                names.append(_node_text(name_child, source))
        elif child.type == "import_spec_list":
            for spec in child.children:
                if spec.type in ("import_spec", "import_specifier"):
                    spec_name = spec.child_by_field_name("name")
                    if spec_name:
                        names.append(_node_text(spec_name, source))

    result.imports.append(ExtractedImport(module=module, names=names))


def _parse_import_text(text: str) -> str:
    """Fallback: parse module name from raw import text."""
    # "import foo.bar" -> "foo.bar"
    # "from foo import bar" -> "foo"
    # "use std::collections::HashMap" -> "std::collections::HashMap"
    # "#include <stdio.h>" -> "stdio.h"
    # "import \"fmt\"" -> "fmt"
    text = text.strip()
    if text.startswith("#include"):
        return text.split("<")[-1].split(">")[0].split('"')[-2] if ('"' in text or '<' in text) else text
    for prefix in ("from ", "import ", "use ", "pub use "):
        if text.startswith(prefix):
            rest = text[len(prefix):].strip()
            # Stop at "import", "as", "{", ";"
            for stop in (" import ", " as ", "{", ";", "\n"):
                if stop in rest:
                    rest = rest[:rest.index(stop)]
            return rest.strip().strip("\"'`")
    return text
