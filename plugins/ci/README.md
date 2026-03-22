# ci

AST-based code indexing, call graph analysis, semantic search, and persistent business memory for Python projects. Works standalone (CLI, REST API) or as a Claude Code plugin.

## Quick Start

```bash
pip install -r requirements.txt

# Index a codebase
python -m cmd.cli index ./my-project --project myapp

# Search code
python -m cmd.cli search --project myapp "authentication logic"

# Call graph
python -m cmd.cli graph --project myapp "myapp::auth/handler.py::verify_token"

# Memory
python -m cmd.cli add-memory --project myapp --type business_rule "Orders over $500 require approval"
python -m cmd.cli search-memory --project myapp --query "approval"
```

## Claude Code Skills

| Command | Description |
| --- | --- |
| `/ci:init` | Index a Python codebase (tree-sitter AST) |
| `/ci:search` | Semantic code search with graph expansion |
| `/ci:graph` | Call graph analysis for functions |
| `/ci:remember` | Save persistent business memory |
| `/ci:recall` | Retrieve saved memories |
| `/ci:analyze` | Deep analysis combining all tools |

## MCP Tools

- `search_code` — vector similarity search + call graph expansion
- `get_call_graph` — callers/callees traversal with configurable depth
- `search_memory` — query persistent memory by text and type
- `add_memory` — store business rules, incidents, notes with tags

## Architecture

Hexagonal (Ports & Adapters) with dual storage backend:

| | Local (default) | Production |
| --- | --- | --- |
| Graph | NetworkX | Neo4j |
| Vectors | FAISS | Qdrant |
| Memory | SQLite | PostgreSQL |
| Cache | In-memory dict | Redis |

```
app/
  domain/          # Models + port interfaces
  services/        # IndexingService, SearchService, MemoryService
  indexer/         # tree-sitter parser, extractor, graph builder
  infrastructure/  # Port implementations (local + production)
  api/             # FastAPI REST server
  mcp/             # MCP server (stdio)
cmd/               # Click CLI
skills/            # 6 Claude Code skills
```

## REST API

```bash
python -m cmd.cli serve
```

| Method | Path | Description |
| --- | --- | --- |
| GET | `/search?project_id=X&query=Y&top_k=10` | Semantic code search |
| GET | `/graph?project_id=X&function_id=Y&depth=2` | Call graph |
| GET | `/function/{id}?project_id=X` | Function details |
| POST | `/memory` | Add memory |
| GET | `/memory/search?project_id=X&query=Y` | Search memory |
| DELETE | `/memory/{id}` | Delete memory |
| GET | `/health` | Health check |

## Docker (Production)

```bash
docker compose up -d
docker compose run --rm cli index /repos/myproject --project myproject
```

## Configuration

All via env vars (defaults in `app/config.py`). See `.env.local` and `.env.production`.
