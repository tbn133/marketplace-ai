# Code Intelligence System

Claude Code plugin marketplace cho code intelligence tools.

## Plugins

| Plugin | Description | Version |
| --- | --- | --- |
| [code-intelligence](plugins/code-intelligence/) | Index code bằng AST, call graph, semantic search, persistent memory | 0.1.0 |

## Cài đặt

### Thêm marketplace vào Claude Code

```bash
claude plugin marketplace add github.com/tabi4/code-intelligence-system
```

### Install plugin

```bash
# Từ marketplace
claude plugin install code-intelligence@code-intelligence-system --scope project

# Hoặc từ local path (khi develop)
claude plugin install ./plugins/code-intelligence --scope project

# Gỡ bỏ
claude plugin uninstall code-intelligence --scope project
```

Sau khi install, Claude Code có thêm **6 skills** và **4 MCP tools** — xem chi tiết bên dưới.

## code-intelligence plugin

### Nó làm gì

```text
Source Code  →  tree-sitter AST  →  Call Graph  (NetworkX)
                                 →  Embeddings  (FAISS)
                                 →  Memory      (SQLite)
```

- **Index** Python codebases bằng tree-sitter (không dùng LLM) — trích xuất functions, classes, imports, call relationships
- **Search** bằng semantic similarity + tự động mở rộng call graph
- **Trace** call graphs — ai gọi function này, nó gọi gì, full dependency chain
- **Remember** business rules, incidents, architecture decisions — persist xuyên sessions
- **Multi-project isolation** — mọi data phân tách theo `project_id`

### Requirements

- Python 3.12+
- Không cần external services (local mode dùng NetworkX + FAISS + SQLite)

### Quick Start

```bash
cd plugins/code-intelligence
pip install -r requirements.txt

# Index codebase
python -m cmd.cli index ./my-project --project myapp

# Search code
python -m cmd.cli search --project myapp "authentication logic"

# Call graph
python -m cmd.cli graph --project myapp "myapp::auth/handler.py::verify_token"

# Lưu business rule
python -m cmd.cli add-memory --project myapp --type business_rule "Orders over $500 cần approval"

# Tìm memory
python -m cmd.cli search-memory --project myapp --query "approval"

# Validate plugin structure
python -m cmd.cli validate-plugin
```

### Skills

Sau khi install plugin, Claude Code có các slash commands:

| Command | Auto-trigger | Mô tả |
| --- | --- | --- |
| `/code-intelligence:code-index` | Không | Index Python codebase bằng tree-sitter AST |
| `/code-intelligence:code-search` | Khi hỏi về code | Semantic search + call graph expansion |
| `/code-intelligence:code-graph` | Khi phân tích function | Call graph — callers/callees |
| `/code-intelligence:remember` | Khi nói "nhớ điều này" | Lưu business rule / incident / note |
| `/code-intelligence:recall` | Khi hỏi kiến thức cũ | Tìm memory đã lưu |
| `/code-intelligence:code-analyze` | Khi phân tích sâu | Kết hợp search + graph + memory |

### MCP Tools

Tự động available sau khi install, Claude gọi trực tiếp:

| Tool | Mô tả |
| --- | --- |
| `search_code` | Vector similarity search + call graph expansion |
| `get_call_graph` | Callers/callees traversal, configurable depth |
| `search_memory` | Query persistent memory theo text và type |
| `add_memory` | Lưu business rules, incidents, notes với tags |

### Workflow điển hình

```text
1. /code-intelligence:code-index . --project myapp    ← index 1 lần
2. "Where is authentication handled?"                   ← auto search
3. "What calls verify_token?"                           ← auto graph
4. "Remember: JWT tokens expire after 1 hour"           ← auto remember
5. "What are the auth rules?"                           ← auto recall
```

### Architecture

Hexagonal (Ports & Adapters) với dual storage backend:

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

| Method | Path | Mô tả |
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

Tất cả qua env vars (defaults trong `app/config.py`):

| Variable | Default | Mô tả |
| --- | --- | --- |
| `STORAGE_BACKEND` | `local` | `local` hoặc `production` |
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
│   └── marketplace.json               ← Marketplace manifest
├── plugins/
│   └── code-intelligence/             ← Plugin 1
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

## Thêm plugin mới

1. Tạo `plugins/<tên-plugin>/` với `.claude-plugin/plugin.json`
1. Thêm skills, MCP servers, agents tùy nhu cầu
1. Đăng ký trong `.claude-plugin/marketplace.json`:

```json
{
  "plugins": [
    { "name": "code-intelligence", "source": "./plugins/code-intelligence" },
    { "name": "new-plugin", "source": "./plugins/new-plugin", "description": "..." }
  ]
}
```

1. Users cập nhật: `claude plugin marketplace update`

## License

MIT
