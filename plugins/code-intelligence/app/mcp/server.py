"""MCP server — receives Container for dependency injection."""

from __future__ import annotations

import json
from dataclasses import asdict

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from app.container import Container, create_container


def create_mcp_server(container: Container | None = None) -> Server:
    c = container or create_container()
    mcp_server = Server("code-intelligence")

    @mcp_server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="search_code",
                description="Search indexed code by semantic query",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "project_id": {"type": "string", "description": "Project identifier"},
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
                description="Search persistent memory entries",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "project_id": {"type": "string"},
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

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    return mcp_server


async def run_mcp_server(container: Container | None = None):
    server = create_mcp_server(container)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream)
