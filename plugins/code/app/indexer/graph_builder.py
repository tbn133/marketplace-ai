"""Builds call graph relationships from extracted symbols.

Resolves function calls to known function nodes and creates edges.
Depends on GraphStorePort — no concrete infrastructure imports.
"""

from __future__ import annotations

from app.domain.models import ClassNode, FunctionNode, ImportNode
from app.domain.ports import GraphStorePort
from app.indexer.extractor import ExtractionResult


def build_graph(
    project_id: str,
    file_path: str,
    extraction: ExtractionResult,
    graph_store: GraphStorePort,
) -> list[FunctionNode]:
    """Build graph nodes and edges from extraction result."""
    function_nodes: list[FunctionNode] = []

    for func in extraction.functions:
        prefix = f"{func.parent_class}." if func.parent_class else ""
        func_id = f"{project_id}::{file_path}::{prefix}{func.name}"
        node = FunctionNode(
            id=func_id,
            project_id=project_id,
            name=func.name,
            file=file_path,
            start_line=func.start_line,
            end_line=func.end_line,
            signature=func.signature,
            calls=func.calls,
        )
        graph_store.add_function(node)
        function_nodes.append(node)

    for cls in extraction.classes:
        cls_id = f"{project_id}::{file_path}::{cls.name}"
        class_node = ClassNode(
            id=cls_id,
            project_id=project_id,
            name=cls.name,
            file=file_path,
            start_line=cls.start_line,
            end_line=cls.end_line,
            methods=cls.methods,
        )
        graph_store.add_class(class_node)

    for imp in extraction.imports:
        imp_id = f"{project_id}::{file_path}::import::{imp.module}"
        import_node = ImportNode(
            id=imp_id,
            project_id=project_id,
            file=file_path,
            module=imp.module,
            names=imp.names,
        )
        graph_store.add_import(import_node)

    return function_nodes


def resolve_calls(
    project_id: str,
    function_nodes: list[FunctionNode],
    graph_store: GraphStorePort,
) -> int:
    """Resolve function calls to known function IDs and create CALLS edges."""
    all_functions = graph_store.get_all_functions(project_id)
    name_to_ids: dict[str, list[str]] = {}
    for fn in all_functions:
        name = fn.get("name", "")
        if name not in name_to_ids:
            name_to_ids[name] = []
        name_to_ids[name].append(fn["id"])

    edge_count = 0
    for fn_node in function_nodes:
        for call_name in fn_node.calls:
            target_ids = name_to_ids.get(call_name, [])
            for target_id in target_ids:
                if target_id != fn_node.id:
                    graph_store.add_call_edge(project_id, fn_node.id, target_id)
                    edge_count += 1

    return edge_count
