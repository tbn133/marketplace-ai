"""MCP server — receives Container for dependency injection.

Supports two transports:
- stdio  (default, for single Claude instance)
- HTTP   (via streamable_http_app, for multi-repo shared server)
"""

from __future__ import annotations

import json
from dataclasses import asdict

from mcp.server import Server
from mcp.server.lowlevel.server import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import ServerCapabilities, TextContent, Tool

from app.container import Container, create_container


def create_mcp_server(container: Container | None = None) -> Server:
    c = container or create_container()
    mcp_server = Server("ci")

    @mcp_server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="search_code",
                description=(
                    "Search indexed code by semantic query. "
                    "Use wildcard project_id (e.g. 'myapp-*') to search across all repos in a group."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "project_id": {
                            "type": "string",
                            "description": "Project identifier. Use 'group-*' to search across all repos in the group.",
                        },
                        "query": {"type": "string", "description": "Search query"},
                        "top_k": {"type": "integer", "description": "Number of results", "default": 10},
                    },
                    "required": ["project_id", "query"],
                },
            ),
            Tool(
                name="get_call_graph",
                description="Get call graph for a function",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "project_id": {"type": "string"},
                        "function_id": {"type": "string"},
                        "depth": {"type": "integer", "default": 2},
                    },
                    "required": ["project_id", "function_id"],
                },
            ),
            Tool(
                name="search_memory",
                description=(
                    "Search persistent memory entries. "
                    "Use wildcard project_id (e.g. 'myapp-*') to search across all repos in a group."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "project_id": {
                            "type": "string",
                            "description": "Project identifier. Use 'group-*' to search across all repos in the group.",
                        },
                        "query": {"type": "string", "default": ""},
                        "type": {"type": "string", "default": ""},
                    },
                    "required": ["project_id"],
                },
            ),
            Tool(
                name="add_memory",
                description="Add a new memory entry (business rule, incident, note)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "project_id": {"type": "string"},
                        "type": {"type": "string", "description": "Memory type: business_rule, incident, note"},
                        "content": {"type": "string"},
                        "tags": {"type": "array", "items": {"type": "string"}, "default": []},
                    },
                    "required": ["project_id", "type", "content"],
                },
            ),
            Tool(
                name="list_projects",
                description=(
                    "List all indexed projects. Optionally filter by group prefix. "
                    "Use this to discover available projects before searching."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "group": {
                            "type": "string",
                            "description": "Group prefix to filter (e.g. 'myapp' returns myapp-backend, myapp-frontend, etc.)",
                        },
                    },
                },
            ),
        ]

    @mcp_server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        if name == "search_code":
            result = c.search_service.search(
                project_id=arguments["project_id"],
                query=arguments["query"],
                top_k=arguments.get("top_k", 10),
            )
            return [TextContent(type="text", text=json.dumps(asdict(result), indent=2))]

        elif name == "get_call_graph":
            result = c.search_service.get_call_graph(
                project_id=arguments["project_id"],
                function_id=arguments["function_id"],
                depth=arguments.get("depth", 2),
            )
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "search_memory":
            result = c.memory_service.search(
                project_id=arguments["project_id"],
                query=arguments.get("query", ""),
                type_filter=arguments.get("type", ""),
            )
            return [TextContent(type="text", text=json.dumps(asdict(result), indent=2))]

        elif name == "add_memory":
            memory = c.memory_service.add(
                project_id=arguments["project_id"],
                type=arguments["type"],
                content=arguments["content"],
                tags=arguments.get("tags", []),
            )
            return [TextContent(type="text", text=json.dumps(asdict(memory), indent=2))]

        elif name == "list_projects":
            group = arguments.get("group")
            projects = c.indexing_service.list_projects(group_prefix=group)
            data = [
                {
                    "project_id": p.project_id,
                    "root_path": p.root_path,
                    "registered_at": p.registered_at,
                }
                for p in projects
            ]
            return [TextContent(type="text", text=json.dumps(data, indent=2))]

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    return mcp_server


async def run_mcp_server(container: Container | None = None):
    server = create_mcp_server(container)
    init_options = InitializationOptions(
        server_name="ci",
        server_version="0.1.0",
        capabilities=ServerCapabilities(tools={}),
    )
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, init_options)
