"""Symbol extractor from tree-sitter AST.

Extracts functions, classes, imports, and call expressions from parsed AST.
"""

from __future__ import annotations

from dataclasses import dataclass, field


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


def _extract_calls(node, source: bytes) -> list[str]:
    """Recursively extract all function call names from a node."""
    calls = []
    if node.type == "call":
        func_node = node.child_by_field_name("function")
        if func_node:
            text = _node_text(func_node, source)
            # Handle method calls: obj.method -> method
            if "." in text:
                calls.append(text.split(".")[-1])
            else:
                calls.append(text)
    for child in node.children:
        calls.extend(_extract_calls(child, source))
    return calls


def _extract_signature(node, source: bytes) -> str:
    """Extract function signature (def name(params) -> return_type)."""
    name_node = node.child_by_field_name("name")
    params_node = node.child_by_field_name("parameters")
    ret_node = node.child_by_field_name("return_type")

    name = _node_text(name_node, source) if name_node else "?"
    params = _node_text(params_node, source) if params_node else "()"
    ret = f" -> {_node_text(ret_node, source)}" if ret_node else ""
    return f"def {name}{params}{ret}"


def extract_symbols(tree, source: bytes) -> ExtractionResult:
    """Extract all symbols from a parsed AST tree."""
    result = ExtractionResult()
    root = tree.root_node
    _walk(root, source, result, parent_class=None)
    return result


def _walk(node, source: bytes, result: ExtractionResult, parent_class: str | None) -> None:
    if node.type == "function_definition":
        name_node = node.child_by_field_name("name")
        if name_node:
            name = _node_text(name_node, source)
            calls = _extract_calls(node, source)
            # Don't count recursive self-calls
            calls = [c for c in calls if c != name]
            func = ExtractedFunction(
                name=name,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                signature=_extract_signature(node, source),
                calls=calls,
                parent_class=parent_class,
            )
            result.functions.append(func)

            if parent_class:
                for cls in result.classes:
                    if cls.name == parent_class:
                        cls.methods.append(name)
                        break
        return  # Don't recurse deeper into function body for nested funcs

    if node.type == "class_definition":
        name_node = node.child_by_field_name("name")
        if name_node:
            cls_name = _node_text(name_node, source)
            cls = ExtractedClass(
                name=cls_name,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
            )
            result.classes.append(cls)
            # Recurse into class body with class context
            for child in node.children:
                _walk(child, source, result, parent_class=cls_name)
        return

    if node.type == "import_statement":
        text = _node_text(node, source)
        # "import foo, bar" -> module="foo", names=["foo","bar"]
        parts = text.replace("import ", "").split(",")
        module = parts[0].strip().split(" as ")[0].strip()
        names = [p.strip().split(" as ")[0].strip() for p in parts]
        result.imports.append(ExtractedImport(module=module, names=names))
        return

    if node.type == "import_from_statement":
        module_node = node.child_by_field_name("module_name")
        module = _node_text(module_node, source) if module_node else ""
        names = []
        for child in node.children:
            if child.type == "dotted_name" and child != module_node:
                names.append(_node_text(child, source))
            elif child.type == "aliased_import":
                name_child = child.child_by_field_name("name")
                if name_child:
                    names.append(_node_text(name_child, source))
        result.imports.append(ExtractedImport(module=module, names=names))
        return

    for child in node.children:
        _walk(child, source, result, parent_class=parent_class)
