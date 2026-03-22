"""Neo4j graph store implementation. Implements GraphStorePort."""

from __future__ import annotations

from neo4j import GraphDatabase

from app.domain.models import ClassNode, FunctionNode, ImportNode
from app.infrastructure.logging import get_logger

logger = get_logger("store.neo4j")


class Neo4jGraphStore:
    def __init__(self, uri: str, user: str, password: str):
        self._driver = GraphDatabase.driver(uri, auth=(user, password))
        logger.info("Neo4j connected: %s", uri)
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        with self._driver.session() as session:
            session.run(
                "CREATE INDEX IF NOT EXISTS FOR (f:Function) ON (f.id)"
            )
            session.run(
                "CREATE INDEX IF NOT EXISTS FOR (f:Function) ON (f.project_id)"
            )
            session.run(
                "CREATE INDEX IF NOT EXISTS FOR (c:Class) ON (c.id)"
            )
            session.run(
                "CREATE INDEX IF NOT EXISTS FOR (i:Import) ON (i.id)"
            )

    def close(self) -> None:
        self._driver.close()

    def save(self, project_id: str) -> None:
        # Neo4j persists automatically — no-op
        pass

    def add_function(self, func: FunctionNode) -> None:
        with self._driver.session() as session:
            session.run(
                """
                MERGE (f:Function {id: $id})
                SET f.project_id = $project_id,
                    f.name = $name,
                    f.file = $file,
                    f.start_line = $start_line,
                    f.end_line = $end_line,
                    f.signature = $signature,
                    f.summary = $summary,
                    f.calls = $calls,
                    f.type = 'function'
                """,
                **func.__dict__,
            )

    def add_class(self, cls: ClassNode) -> None:
        with self._driver.session() as session:
            session.run(
                """
                MERGE (c:Class {id: $id})
                SET c.project_id = $project_id,
                    c.name = $name,
                    c.file = $file,
                    c.start_line = $start_line,
                    c.end_line = $end_line,
                    c.methods = $methods,
                    c.type = 'class'
                """,
                **cls.__dict__,
            )

    def add_import(self, imp: ImportNode) -> None:
        with self._driver.session() as session:
            session.run(
                """
                MERGE (i:Import {id: $id})
                SET i.project_id = $project_id,
                    i.file = $file,
                    i.module = $module,
                    i.names = $names,
                    i.type = 'import'
                """,
                **imp.__dict__,
            )

    def add_call_edge(self, project_id: str, caller_id: str, callee_id: str) -> None:
        with self._driver.session() as session:
            session.run(
                """
                MATCH (a:Function {id: $caller_id, project_id: $project_id})
                MATCH (b:Function {id: $callee_id, project_id: $project_id})
                MERGE (a)-[:CALLS]->(b)
                """,
                caller_id=caller_id,
                callee_id=callee_id,
                project_id=project_id,
            )

    def get_function(self, project_id: str, function_id: str) -> dict | None:
        with self._driver.session() as session:
            result = session.run(
                "MATCH (f:Function {id: $id, project_id: $pid}) RETURN properties(f) AS props",
                id=function_id,
                pid=project_id,
            ).single()
            if result:
                return dict(result["props"])
            return None

    def get_callees(self, project_id: str, function_id: str) -> list[dict]:
        with self._driver.session() as session:
            results = session.run(
                """
                MATCH (f:Function {id: $id, project_id: $pid})-[:CALLS]->(callee)
                RETURN properties(callee) AS props
                """,
                id=function_id,
                pid=project_id,
            )
            return [dict(r["props"]) for r in results]

    def get_callers(self, project_id: str, function_id: str) -> list[dict]:
        with self._driver.session() as session:
            results = session.run(
                """
                MATCH (caller)-[:CALLS]->(f:Function {id: $id, project_id: $pid})
                RETURN properties(caller) AS props
                """,
                id=function_id,
                pid=project_id,
            )
            return [dict(r["props"]) for r in results]

    def get_call_graph(self, project_id: str, function_id: str, depth: int = 2) -> dict:
        with self._driver.session() as session:
            # Get nodes within depth via variable-length path
            node_results = session.run(
                """
                MATCH (f:Function {id: $id, project_id: $pid})
                CALL {
                    WITH f
                    MATCH path = (f)-[:CALLS*0..$depth]-(related)
                    RETURN DISTINCT related
                }
                RETURN properties(related) AS props
                """,
                id=function_id,
                pid=project_id,
                depth=depth,
            )
            nodes = [dict(r["props"]) for r in node_results]

            # Get edges between these nodes
            node_ids = [n.get("id") for n in nodes if n.get("id")]
            edge_results = session.run(
                """
                MATCH (a)-[:CALLS]->(b)
                WHERE a.id IN $ids AND b.id IN $ids
                RETURN a.id AS from_id, b.id AS to_id
                """,
                ids=node_ids,
            )
            edges = [
                {"from": r["from_id"], "to": r["to_id"], "relation": "CALLS"}
                for r in edge_results
            ]

        return {"center": function_id, "nodes": nodes, "edges": edges}

    def get_all_functions(self, project_id: str) -> list[dict]:
        with self._driver.session() as session:
            results = session.run(
                "MATCH (f:Function {project_id: $pid}) RETURN properties(f) AS props",
                pid=project_id,
            )
            return [dict(r["props"]) for r in results]

    def remove_file_nodes(self, project_id: str, file_path: str) -> None:
        with self._driver.session() as session:
            session.run(
                """
                MATCH (n {project_id: $pid, file: $file})
                DETACH DELETE n
                """,
                pid=project_id,
                file=file_path,
            )

    def clear_project(self, project_id: str) -> None:
        with self._driver.session() as session:
            session.run(
                "MATCH (n {project_id: $pid}) DETACH DELETE n",
                pid=project_id,
            )
