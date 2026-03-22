# Code Intelligence System

A Claude Code plugin marketplace for code intelligence tools.

## Plugins

| Plugin | Description | Version |
| --- | --- | --- |
| [code-intelligence](plugins/code-intelligence/) | AST-based code indexing, call graphs, semantic search, persistent memory | 0.1.0 |

## Installation

### Add marketplace to Claude Code

```bash
claude plugin marketplace add github.com/tabi4/code-intelligence-system
```

### Install a plugin

```bash
# From marketplace
claude plugin install code-intelligence@code-intelligence-system --scope project

# From local path (development)
claude plugin install ./plugins/code-intelligence --scope project

# Uninstall
claude plugin uninstall code-intelligence --scope project
```

After installation, Claude Code gains **6 skills** and **4 MCP tools** — see details below.

## code-intelligence plugin

### What it does

```text
Source Code  ->  tree-sitter AST  ->  Call Graph  (NetworkX)
                                  ->  Embeddings  (FAISS)
                                  ->  Memory      (SQLite)
```

- **Index** Python codebases using tree-sitter (no LLM) — extracts functions, classes, imports, call relationships
- **Search** by semantic similarity with automatic call graph expansion
- **Trace** call graphs — who calls a function, what it calls, full dependency chain
- **Remember** business rules, incidents, architecture decisions — persisted across sessions
- **Multi-project isolation** — all data partitioned by `project_id`

### Requirements

- Python 3.12+
- No external services needed (local mode uses NetworkX + FAISS + SQLite)

### Quick Start

```bash
cd plugins/code-intelligence
pip install -r requirements.txt

# Index a codebase
python -m cmd.cli index ./my-project --project myapp

# Search code
python -m cmd.cli search --project myapp "authentication logic"

# Call graph
python -m cmd.cli graph --project myapp "myapp::auth/handler.py::verify_token"

# Save a business rule
python -m cmd.cli add-memory --project myapp --type business_rule "Orders over $500 require approval"

# Search memory
python -m cmd.cli search-memory --project myapp --query "approval"

# Validate plugin structure
python -m cmd.cli validate-plugin
```

### Skills

After installing the plugin, the following slash commands become available in Claude Code:

| Command | Auto-trigger | Description |
| --- | --- | --- |
| `/code-intelligence:code-index` | No | Index a Python codebase using tree-sitter AST |
| `/code-intelligence:code-search` | When asking about code | Semantic search + call graph expansion |
| `/code-intelligence:code-graph` | When analyzing functions | Call graph — callers/callees |
| `/code-intelligence:remember` | When saying "remember this" | Save business rule / incident / note |
| `/code-intelligence:recall` | When asking about past knowledge | Retrieve saved memories |
| `/code-intelligence:code-analyze` | When doing deep analysis | Combines search + graph + memory |

### MCP Tools

Automatically available after install. Claude calls them directly:

| Tool | Description |
| --- | --- |
| `search_code` | Vector similarity search + call graph expansion |
| `get_call_graph` | Callers/callees traversal, configurable depth |
| `search_memory` | Query persistent memory by text and type |
| `add_memory` | Store business rules, incidents, notes with tags |

### Typical Workflow

```text
1. /code-intelligence:code-index . --project myapp    <- one-time index
2. "Where is authentication handled?"                   <- auto search
3. "What calls verify_token?"                           <- auto graph
4. "Remember: JWT tokens expire after 1 hour"           <- auto remember
5. "What are the auth rules?"                           <- auto recall
```

### Architecture

Hexagonal (Ports & Adapters) with dual storage backend:

| Component | Local (default) | Production |
| --- | --- | --- |
| Graph | NetworkX | Neo4j |
| Vectors | FAISS | Qdrant |
| Memory | SQLite | PostgreSQL |
| Cache | In-memory dict | Redis |

```text
plugins/code-intelligence/
  app/
    domain/          # Models (FunctionNode, Memory...) + port interfaces
    services/        # IndexingService, SearchService, MemoryService
    indexer/         # tree-sitter parser, extractor, graph builder
    infrastructure/  # Port implementations (local + production)
    api/             # FastAPI REST server
    mcp/             # MCP server (stdio)
    config.py        # Env-based configuration
    container.py     # Dependency injection root
  cmd/cli.py         # Click CLI
  skills/            # 6 SKILL.md files
  data/              # Runtime data (gitignored)
```

### REST API

```bash
python -m cmd.cli serve
```

| Method | Path | Description |
| --- | --- | --- |
| GET | `/search?project_id=X&query=Y&top_k=10` | Semantic code search |
| GET | `/graph?project_id=X&function_id=Y&depth=2` | Call graph |
| GET | `/function/{id}?project_id=X` | Function details |
| POST | `/memory` | Add memory `{project_id, type, content, tags}` |
| GET | `/memory/search?project_id=X&query=Y` | Search memory |
| DELETE | `/memory/{id}` | Delete memory |
| GET | `/health` | Health check |

### Docker (Production)

```bash
cd plugins/code-intelligence
docker compose up -d
docker compose run --rm cli index /repos/myproject --project myproject
```

### Configuration

All via environment variables (defaults in `app/config.py`):

| Variable | Default | Description |
| --- | --- | --- |
| `STORAGE_BACKEND` | `local` | `local` or `production` |
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j connection |
| `QDRANT_URL` | `http://localhost:6333` | Qdrant connection |
| `POSTGRES_HOST` | `localhost` | PostgreSQL host |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection |
| `EMBEDDING_DIM` | `128` | Vector dimension |
| `LOG_LEVEL` | `INFO` | Logging level |

## Marketplace Structure

```text
code-intelligence-system/
├── .claude-plugin/
│   └── marketplace.json               <- Marketplace manifest
├── plugins/
│   └── code-intelligence/             <- Plugin 1
│       ├── .claude-plugin/plugin.json
│       ├── app/
│       ├── cmd/
│       ├── skills/
│       ├── mcp-servers.json
│       ├── requirements.txt
│       └── ...
├── README.md
├── CLAUDE.md
└── .gitignore
```

## Adding a New Plugin

1. Create `plugins/<plugin-name>/` with a `.claude-plugin/plugin.json`
1. Add skills, MCP servers, or agents as needed
1. Register in `.claude-plugin/marketplace.json`:

```json
{
  "plugins": [
    { "name": "code-intelligence", "source": "./plugins/code-intelligence" },
    { "name": "new-plugin", "source": "./plugins/new-plugin", "description": "..." }
  ]
}
```

1. Users update with: `claude plugin marketplace update`

## License

MIT
