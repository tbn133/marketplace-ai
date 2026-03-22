"""Graph store implementation using NetworkX. Implements GraphStorePort."""

from __future__ import annotations

import os
import pickle
from pathlib import Path

import networkx as nx

from app.domain.models import ClassNode, FunctionNode, ImportNode


class NetworkXGraphStore:
    def __init__(self, data_dir: Path):
        self._data_dir = data_dir
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._graphs: dict[str, nx.DiGraph] = {}

    def _graph_path(self, project_id: str) -> Path:
        return self._data_dir / f"graph_{project_id}.pkl"

    def _get_graph(self, project_id: str) -> nx.DiGraph:
        if project_id not in self._graphs:
            path = self._graph_path(project_id)
            if path.exists():
                with open(path, "rb") as f:
                    self._graphs[project_id] = pickle.load(f)
            else:
                self._graphs[project_id] = nx.DiGraph()
        return self._graphs[project_id]

    def save(self, project_id: str) -> None:
        g = self._get_graph(project_id)
        with open(self._graph_path(project_id), "wb") as f:
            pickle.dump(g, f)

    def add_function(self, func: FunctionNode) -> None:
        g = self._get_graph(func.project_id)
        g.add_node(func.id, type="function", **func.__dict__)

    def add_class(self, cls: ClassNode) -> None:
        g = self._get_graph(cls.project_id)
        g.add_node(cls.id, type="class", **cls.__dict__)

    def add_import(self, imp: ImportNode) -> None:
        g = self._get_graph(imp.project_id)
        g.add_node(imp.id, type="import", **imp.__dict__)

    def add_call_edge(self, project_id: str, caller_id: str, callee_id: str) -> None:
        g = self._get_graph(project_id)
        g.add_edge(caller_id, callee_id, relation="CALLS")

    def get_function(self, project_id: str, function_id: str) -> dict | None:
        g = self._get_graph(project_id)
        if function_id in g.nodes:
            return dict(g.nodes[function_id])
        return None

    def get_callees(self, project_id: str, function_id: str) -> list[dict]:
        g = self._get_graph(project_id)
        return [
            dict(g.nodes[target])
            for _, target in g.out_edges(function_id)
            if target in g.nodes
        ]

    def get_callers(self, project_id: str, function_id: str) -> list[dict]:
        g = self._get_graph(project_id)
        return [
            dict(g.nodes[source])
            for source, _ in g.in_edges(function_id)
            if source in g.nodes
        ]

    def get_call_graph(self, project_id: str, function_id: str, depth: int = 2) -> dict:
        g = self._get_graph(project_id)
        if function_id not in g.nodes:
            return {"center": function_id, "nodes": [], "edges": []}

        visited: set[str] = set()
        seen_edges: set[tuple[str, str]] = set()
        nodes: list[dict] = []
        edges: list[dict] = []
        queue: list[tuple[str, int]] = [(function_id, 0)]

        while queue:
            node_id, d = queue.pop(0)
            if node_id in visited or d > depth:
                continue
            visited.add(node_id)
            if node_id in g.nodes:
                nodes.append(dict(g.nodes[node_id]))

            for _, target in g.out_edges(node_id):
                if (node_id, target) not in seen_edges:
                    seen_edges.add((node_id, target))
                    edges.append({"from": node_id, "to": target, "relation": "CALLS"})
                if target not in visited and d + 1 <= depth:
                    queue.append((target, d + 1))

            for source, _ in g.in_edges(node_id):
                if (source, node_id) not in seen_edges:
                    seen_edges.add((source, node_id))
                    edges.append({"from": source, "to": node_id, "relation": "CALLS"})
                if source not in visited and d + 1 <= depth:
                    queue.append((source, d + 1))

        return {"center": function_id, "nodes": nodes, "edges": edges}

    def get_all_functions(self, project_id: str) -> list[dict]:
        g = self._get_graph(project_id)
        return [
            dict(g.nodes[n])
            for n in g.nodes
            if g.nodes[n].get("type") == "function"
        ]

    def remove_file_nodes(self, project_id: str, file_path: str) -> None:
        g = self._get_graph(project_id)
        to_remove = [n for n in g.nodes if g.nodes[n].get("file") == file_path]
        g.remove_nodes_from(to_remove)

    def clear_project(self, project_id: str) -> None:
        self._graphs[project_id] = nx.DiGraph()
        path = self._graph_path(project_id)
        if path.exists():
            os.remove(path)
