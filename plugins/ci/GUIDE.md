# Code Intelligence Plugin — Hướng dẫn sử dụng

## Mục lục

- [Tổng quan](#tổng-quan)
- [Cài đặt](#cài-đặt)
- [Multi-module project](#multi-module-project)
- [Index codebase](#index-codebase)
- [Tự động cập nhật (Auto-Capture)](#tự-động-cập-nhật-auto-capture)
- [Watch mode](#watch-mode)
- [Skills (Slash Commands)](#skills-slash-commands)
- [MCP Tools](#mcp-tools)
- [Kiến trúc hệ thống](#kiến-trúc-hệ-thống)
- [Cấu trúc dữ liệu](#cấu-trúc-dữ-liệu)
- [Cấu hình](#cấu-hình)
- [Xử lý sự cố](#xử-lý-sự-cố)

---

## Tổng quan

CI Plugin là hệ thống code intelligence cho Claude Code, cung cấp:

- **AST Indexing**: Parse codebase bằng tree-sitter, trích xuất functions, classes, imports, call relationships
- **Semantic Search**: Tìm kiếm code theo ngữ nghĩa qua vector embeddings (FAISS)
- **Call Graph**: Phân tích quan hệ gọi hàm (ai gọi ai, ai bị gọi bởi ai)
- **Business Memory**: Lưu trữ business rules, incidents, notes qua các session
- **Auto-Capture**: Tự động re-index khi Claude Code edit/write file
- **Watch Mode**: Theo dõi filesystem changes từ bên ngoài (IDE, git pull)

**Ngôn ngữ hỗ trợ**: Python, TypeScript, JavaScript, Go, Rust, Java, C, C++, PHP

---

## Cài đặt

### Từ marketplace (sau khi publish)

```bash
# Thêm marketplace
claude plugin marketplace add github.com/tabi4/code-intelligence-system

# Cài plugin
claude plugin install ci@code-intelligence-system --scope project
```

### Từ local path (development)

```bash
claude plugin install ./plugins/ci --scope project
```

### Cài đặt thủ công (CLI trực tiếp)

```bash
cd plugins/ci
pip install -r requirements.txt
```

### Kiểm tra cài đặt

```bash
cd plugins/ci
python -m cmd.cli --help
```

Khi plugin được cài qua Claude Code, **SessionStart hook** tự động:
1. Tạo virtual environment trong `CLAUDE_PLUGIN_DATA`
2. Cài tất cả dependencies từ `requirements.txt`
3. Chỉ cài lại khi `requirements.txt` thay đổi

---

## Multi-module project

### Ý tưởng chính

Toàn bộ workspace được index thành **1 project duy nhất**. Mỗi subfolder (repo/service) trở thành **module** trong cùng domain, chia sẻ chung graph, vectors, và memory.

Mỗi module là **git repository riêng** với **`.claude/` config riêng** (CLAUDE.md, settings, memory). Khi Claude Code mở từng module, nó đọc `.claude/` của module đó. Khi plugin index toàn workspace, nó nhìn tất cả modules như một thể thống nhất.

```
/workspace/                              ← root = 1 project_id
├── backend-api/                         ← module (Python)
│   ├── .git/                            ← git repo riêng
│   ├── .claude/                         ← Claude Code config riêng
│   │   ├── CLAUDE.md                    ← rules cho module này
│   │   └── settings.local.json
│   ├── app/auth/handler.py
│   └── app/models/user.py
├── frontend-app/                        ← module (TypeScript)
│   ├── .git/
│   ├── .claude/
│   │   └── CLAUDE.md
│   ├── src/hooks/useAuth.ts
│   └── src/pages/checkout.tsx
└── payment-service/                     ← module (Go)
    ├── .git/
    ├── .claude/
    │   └── CLAUDE.md
    ├── cmd/server.go
    └── internal/stripe/client.go
```

> **Lưu ý**: `.git/` và `.claude/` tự động bị skip khi index — chỉ source code được parse.

### Bước 1: Index toàn bộ workspace

```bash
# Qua skill (trong Claude Code)
/ci:init /workspace --project myproject -v

# Hoặc qua CLI
python -m cmd.cli index /workspace --project myproject -v
```

Output:
```
Indexing '/workspace' for project 'myproject'...
  [+] backend-api/app/auth/handler.py
  [+] backend-api/app/models/user.py
  [+] frontend-app/src/hooks/useAuth.ts
  [+] frontend-app/src/pages/checkout.tsx
  [+] payment-service/cmd/server.go
  [+] payment-service/internal/stripe/client.go
  [=] backend-api/app/config.py          ← unchanged, skipped
  [!] backend-api/app/broken.py          ← parse error

Done! Indexed 85 files (skipped 3 unchanged):
  Functions: 312
  Classes:   64
```

Relative path tự nhiên phân biệt module: `backend-api/...`, `frontend-app/...`, `payment-service/...`

Ký hiệu: `[+]` indexed, `[=]` skipped (hash unchanged), `[!]` error.

### Bước 2: Search xuyên suốt toàn project

Tất cả modules chia sẻ chung 1 graph + 1 vector index. Search trả kết quả từ mọi module:

```bash
# Tìm tất cả code liên quan "authentication" trong toàn project
/ci:search "authentication logic" --project myproject
```

Kết quả:
```
[0.92] login_handler       — backend-api/app/auth/handler.py:42
[0.87] useAuth              — frontend-app/src/hooks/useAuth.ts:15
[0.81] validate_token       — backend-api/app/auth/jwt.py:10
[0.75] AuthMiddleware        — payment-service/internal/auth/middleware.go:22
```

Search 1 lần, thấy code liên quan từ **tất cả modules** trong cùng domain.

### Bước 3: Call graph liên kết cross-module

```bash
/ci:graph "myproject::backend-api/app/auth/handler.py::login_handler" --depth 3
```

```
login_handler (backend-api/app/auth/handler.py:42)
├── calls:
│   ├── validate_token (backend-api/app/auth/jwt.py:10)
│   ├── get_user_by_id (backend-api/app/db/users.py:25)
│   └── log_auth_event (backend-api/app/events/logger.py:8)
└── called by:
    └── auth_middleware (backend-api/app/middleware.py:15)
```

Trong cùng 1 project, call graph resolve được tất cả liên kết cross-file, cross-folder.

### Bước 4: Memory chia sẻ toàn domain

Business rules, incidents, notes áp dụng cho **toàn bộ project**, không bị phân mảnh:

```bash
# Lưu rule áp dụng cho toàn domain
/ci:remember "Orders > $500 require manager approval" --project myproject
/ci:remember "All API endpoints must validate JWT" --project myproject
/ci:remember "Stripe webhook timeout: increase to 30s" --project myproject

# Recall tìm across toàn domain
/ci:recall "approval rules" --project myproject
/ci:recall "stripe" --project myproject
```

### Bước 5: Phân tích toàn diện cross-module

```bash
/ci:analyze "how does checkout work" --project myproject
```

Analyze tự động kết hợp:
1. Memory: business rules liên quan (approval, payment rules)
2. Search: tìm code "checkout" xuyên backend + frontend + payment
3. Graph: trace call chain từ frontend → backend → payment-service
4. Tổng hợp findings thành bức tranh end-to-end

### Auto-capture hoạt động tự động

Sau khi index, nếu Claude Code edit bất kỳ file nào trong `/workspace/`, DB tự động cập nhật (xem phần [Auto-Capture](#tự-động-cập-nhật-auto-capture)).

### Function ID format trong multi-module

```
{project_id}::{module/relative_path}::{ClassName.}function_name
```

Ví dụ:
```
myproject::backend-api/app/auth/handler.py::login_handler
myproject::frontend-app/src/hooks/useAuth.ts::useAuth
myproject::payment-service/cmd/server.go::HandlePayment
myproject::backend-api/app/models/user.py::User.validate
```

Module được phân biệt tự nhiên qua prefix path (`backend-api/`, `frontend-app/`, `payment-service/`).

---

## Index codebase

### Lần đầu (full index)

```bash
python -m cmd.cli index <path> --project <project_id> [--verbose]
```

- Scan toàn bộ file hỗ trợ trong thư mục
- Parse AST bằng tree-sitter
- Trích xuất functions, classes, imports, call expressions
- Build call graph (ai gọi ai)
- Tạo vector embeddings cho search
- Lưu project vào registry (`data/registry.json`)

### Re-index (incremental)

```bash
python -m cmd.cli index <path> --project <project_id>
```

- So sánh SHA256 hash từng file với lần index trước
- Chỉ re-parse file có hash thay đổi
- File không đổi → skip
- File thay đổi → xóa data cũ → parse lại → rebuild

### Force re-index

```bash
python -m cmd.cli index <path> --project <project_id> --force
```

Bỏ qua hash check, re-index toàn bộ.

### Kiểm tra trạng thái

```bash
python -m cmd.cli index --project <project_id> --status
```

Output:
```
Project: myproject
  Files:     85
  Functions: 312

Indexed files:
  backend-api/app/main.py
  backend-api/app/auth/handler.py
  frontend-app/src/hooks/useAuth.ts
  payment-service/cmd/server.go
  ...
```

### Thư mục bị bỏ qua

Các thư mục sau tự động bị skip khi scan:

```
.git, .claude, __pycache__, node_modules, .venv, venv, env,
.tox, .nox, .mypy_cache, .ruff_cache, .pytest_cache, .pytype,
build, dist, .eggs, site-packages, .idea, .vscode
```

Đặc biệt quan trọng với multi-module project: mỗi module có `.git/` và `.claude/` riêng — tất cả đều bị skip, chỉ source code được index.

---

## Tự động cập nhật (Auto-Capture)

### Hoạt động

Khi Claude Code thực hiện **Edit** hoặc **Write** tool trên bất kỳ file nào, PostToolUse hook tự động chạy:

```
Claude Code Edit file
  → PostToolUse hook fires
  → Đọc stdin JSON → lấy file_path
  → Check: file extension được hỗ trợ?
  → Check: file thuộc project đã index? (tra registry.json)
  → Match → incremental re-index file đó
  → Không match → skip (silent)
```

### Điều kiện hoạt động

1. Plugin đã được cài (`claude plugin install ci`)
2. Project đã được index ít nhất 1 lần (có trong `registry.json`)
3. File được edit có extension hỗ trợ (`.py`, `.ts`, `.js`, `.go`, `.rs`, `.java`, `.c`, `.cpp`, `.php`)

### Không cần cấu hình gì thêm

Hook được định nghĩa sẵn trong `plugin.json`:

```json
{
  "PostToolUse": [
    {
      "matcher": "Edit|Write",
      "hooks": [
        {
          "type": "command",
          "command": "cd \"${CLAUDE_PLUGIN_ROOT}\" && python3 hooks/post_tool_reindex.py",
          "timeout": 30000
        }
      ]
    }
  ]
}
```

### Performance

- **Fast path** (file không thuộc project nào): thoát ngay, không import nặng
- **Slow path** (file thuộc project): ~1-2 giây (load container + parse + save)
- Hook chạy **non-blocking** — không ảnh hưởng tốc độ Claude Code

---

## Watch mode

Watch mode dùng `watchdog` library để theo dõi thay đổi từ **bên ngoài Claude Code** (IDE, git pull, script, v.v.).

### Sử dụng

```bash
# Watch toàn bộ project (tất cả modules)
python -m cmd.cli watch --project myproject

# Custom debounce (mặc định 2 giây)
python -m cmd.cli watch --project myproject --debounce 5
```

Output:
```
Watching '/workspace' for project 'myproject' (debounce=2.0s)
Press Ctrl+C to stop.

  [myproject] 1 file(s) re-indexed
  [myproject] 3 file(s) re-indexed, 1 file(s) removed
```

### Debounce

Khi nhiều file thay đổi liên tiếp (ví dụ `git checkout` branch khác), watcher gom lại và chỉ chạy 1 lần re-index sau khoảng debounce.

### Xử lý file bị xóa

File bị xóa → tự động remove nodes và vectors khỏi DB.

### Khi nào dùng watch vs auto-capture

| Nguồn thay đổi | Cơ chế | Tự động? |
|---|---|---|
| Claude Code Edit/Write | PostToolUse hook | Tự động (luôn bật) |
| IDE edit, git pull, script | `watch` command | Cần chạy thủ công |

---

## Skills (Slash Commands)

Khi plugin được cài trong Claude Code, các skill có thể dùng qua slash command:

### `/ci:init` — Index codebase

```
/ci:init /workspace --project myproject -v
/ci:init --project myproject --status
```

### `/ci:search` — Tìm kiếm code

```
/ci:search "authentication logic" --project myproject
/ci:search "payment processing" --project myproject
```

Tìm kiếm theo ngữ nghĩa, trả về functions ranked by similarity + related callers/callees.

### `/ci:graph` — Phân tích call graph

```
/ci:graph "myproject::backend-api/app/auth/handler.py::login_handler" --depth 3
```

Hiển thị:
```
login_handler (backend-api/app/auth/handler.py:42)
├── calls:
│   ├── validate_token (backend-api/app/auth/jwt.py:10)
│   └── get_user_by_id (backend-api/app/db/users.py:25)
└── called by:
    ├── auth_middleware (backend-api/app/middleware.py:15)
    └── test_login (backend-api/tests/test_auth.py:8)
```

### `/ci:analyze` — Phân tích toàn diện

```
/ci:analyze "how does checkout work"
```

Kết hợp search + graph + memory để phân tích end-to-end:
1. Tìm memories liên quan (business rules, incidents)
2. Search code liên quan
3. Trace call graph cho key functions
4. Đọc source code
5. Tổng hợp findings

### `/ci:remember` — Lưu business memory

```
/ci:remember "Orders > $500 require manager approval" --project myproject
/ci:remember "Redis timeout fix: increase max_connections to 50" --project myproject
```

Memory types: `business_rule`, `incident`, `note`.

### `/ci:recall` — Tìm kiếm memory

```
/ci:recall "approval rules" --project myproject
/ci:recall --type incident --project myproject
```

---

## MCP Tools

Plugin expose 4 MCP tools qua stdio server, được Claude Code gọi tự động khi dùng skills:

| Tool | Mô tả | Params |
|---|---|---|
| `search_code` | Tìm kiếm code theo semantic query | `project_id`, `query`, `top_k` |
| `get_call_graph` | Lấy call graph cho function | `project_id`, `function_id`, `depth` |
| `search_memory` | Tìm kiếm memories | `project_id`, `query?`, `type?` |
| `add_memory` | Thêm memory mới | `project_id`, `type`, `content`, `tags?` |

### Function ID format

```
{project_id}::{module/relative_path}::{ClassName.}function_name
```

Ví dụ:
- `myproject::backend-api/app/auth/handler.py::login_handler`
- `myproject::backend-api/app/models/user.py::User.validate`
- `myproject::frontend-app/src/hooks/useAuth.ts::useAuth`
- `myproject::payment-service/cmd/server.go::HandlePayment`

---

## Kiến trúc hệ thống

### Hexagonal Architecture (Ports & Adapters)

```
┌─────────────────────────────────────────────────┐
│  Entry Points                                    │
│  ┌─────────┐  ┌──────────┐  ┌────────────────┐ │
│  │   CLI   │  │ REST API │  │   MCP Server   │ │
│  └────┬────┘  └────┬─────┘  └───────┬────────┘ │
│       │             │                │           │
│  ┌────▼─────────────▼────────────────▼────────┐ │
│  │              Services                       │ │
│  │  IndexingService  SearchService             │ │
│  │  MemoryService    WatcherService            │ │
│  └────────────────────┬───────────────────────┘ │
│                       │                          │
│  ┌────────────────────▼───────────────────────┐ │
│  │           Ports (Protocols)                 │ │
│  │  GraphStorePort    VectorStorePort          │ │
│  │  MemoryStorePort   EmbeddingPort            │ │
│  │  CachePort                                  │ │
│  └────────────────────┬───────────────────────┘ │
│                       │                          │
│  ┌────────────────────▼───────────────────────┐ │
│  │         Infrastructure (Adapters)           │ │
│  │                                             │ │
│  │  Local:       NetworkX + FAISS + SQLite     │ │
│  │  Production:  Neo4j + Qdrant + PostgreSQL   │ │
│  └─────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

### Container (Composition Root)

`app/container.py` là nơi wire tất cả dependencies. Đọc `STORAGE_BACKEND` env var:
- `local` (mặc định): NetworkX + FAISS + SQLite + MemoryCache
- `production`: Neo4j + Qdrant + PostgreSQL + Redis

### Indexing Pipeline

```
File → tree-sitter parse → AST
  → extract_symbols() → functions, classes, imports, calls
  → build_graph() → GraphStore (nodes + edges)
  → generate embeddings → VectorStore
  → resolve_calls() → cross-file call edges
```

### Hook Pipeline

```
SessionStart:
  → Cài dependencies (pip install -r requirements.txt)

PostToolUse (Edit|Write):
  → Đọc stdin JSON
  → Extract file_path
  → Check registry.json → tìm project
  → Incremental re-index file
```

---

## Cấu trúc dữ liệu

### Thư mục data/

```
plugins/ci/data/
├── registry.json               ← project_id → root_path mapping
├── graph_{project_id}.pkl      ← NetworkX graph (functions, classes, call edges)
├── faiss_{project_id}.index    ← FAISS vector index
├── faiss_{project_id}_meta.json ← Vector metadata (file, name, signature)
├── hashes_{project_id}.json    ← SHA256 hash per file (for incremental index)
└── db.sqlite                   ← SQLite database (business memories)
```

### Unified project — tất cả modules chung 1 namespace

Khi index `/workspace` thành 1 project `myproject`:

```
plugins/ci/data/
├── registry.json                    ← myproject → /workspace
├── graph_myproject.pkl              ← tất cả functions/classes/calls từ mọi module
├── faiss_myproject.index            ← tất cả vectors từ mọi module
├── faiss_myproject_meta.json        ← metadata phân biệt module qua field "file"
├── hashes_myproject.json            ← SHA256 per file, path gồm module prefix
└── db.sqlite                        ← memories chung cho toàn project
```

Module được phân biệt qua relative path trong data:
- Graph node: `file = "backend-api/app/auth/handler.py"`
- Vector metadata: `{"file": "frontend-app/src/hooks/useAuth.ts", ...}`
- Hash key: `"payment-service/cmd/server.go"`

### registry.json

```json
{
  "myproject": {
    "project_id": "myproject",
    "root_path": "/workspace",
    "registered_at": "2026-03-25T10:00:00+00:00"
  }
}
```

### Multi-project (nếu cần)

Có thể index nhiều workspace riêng biệt thành nhiều project_id:

```bash
python -m cmd.cli index /workspace-a --project project-a
python -m cmd.cli index /workspace-b --project project-b
```

Mỗi project có graph, vectors, hashes riêng. Memories isolated bởi `project_id` column trong SQLite.

---

## Cấu hình

Tất cả cấu hình qua environment variables:

| Variable | Mặc định | Mô tả |
|---|---|---|
| `STORAGE_BACKEND` | `local` | `local` hoặc `production` |
| `DATA_DIR` | `plugins/ci/data` | Thư mục lưu data |
| `EMBEDDING_DIM` | `128` | Kích thước vector embedding |
| `LOG_LEVEL` | `INFO` | Log level |
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j URI (production) |
| `QDRANT_URL` | `http://localhost:6333` | Qdrant URL (production) |
| `POSTGRES_HOST` | `localhost` | PostgreSQL host (production) |
| `REDIS_URL` | `redis://localhost:6379` | Redis URL (production) |
| `CACHE_TTL` | `300` | Cache TTL (giây) |

### Local backend (mặc định)

Không cần cấu hình gì thêm. Dữ liệu lưu trong `data/`.

### Production backend

```bash
export STORAGE_BACKEND=production
# Đảm bảo Neo4j, Qdrant, PostgreSQL, Redis đang chạy
docker compose up -d
```

### Migrate từ local sang production

```bash
# Kiểm tra trước
python -m cmd.cli migrate --dry-run

# Migrate toàn bộ
python -m cmd.cli migrate

# Migrate 1 project
python -m cmd.cli migrate --project myproject
```

---

## Xử lý sự cố

### "Project has no registered root path"

```
Error: Project 'myproject' has no registered root path.
Run 'index' first to register the project.
```

**Nguyên nhân**: Chưa index project, hoặc `registry.json` bị mất.

**Giải pháp**: Chạy index lại:
```bash
python -m cmd.cli index ./path/to/repo --project myproject
```

### "No results found" khi search

**Nguyên nhân có thể**:
1. Project chưa được index
2. Dùng sai `project_id`
3. File không có extension hỗ trợ

**Kiểm tra**:
```bash
python -m cmd.cli index --project myproject --status
```

### tree-sitter parse errors

**Nguyên nhân**: Thiếu grammar package cho ngôn ngữ.

**Giải pháp**:
```bash
pip install tree-sitter-python tree-sitter-typescript tree-sitter-javascript
pip install tree-sitter-go tree-sitter-rust tree-sitter-java
pip install tree-sitter-c tree-sitter-cpp tree-sitter-php
```

### Auto-capture hook không chạy

**Kiểm tra**:
1. Plugin đã cài đúng: `claude plugin list`
2. `registry.json` tồn tại và có project entry
3. File edit có extension hỗ trợ
4. Test thủ công:
```bash
echo '{"tool_name":"Edit","tool_input":{"file_path":"/full/path/to/file.py"}}' | \
  python3 hooks/post_tool_reindex.py
```

### Watch mode không detect thay đổi

**Kiểm tra**:
1. Project đã index: `python -m cmd.cli index --project myproject --status`
2. Watchdog đã cài: `pip install watchdog`
3. File thay đổi có extension hỗ trợ
4. File không nằm trong thư mục bị ignore (node_modules, .git, v.v.)

### Dữ liệu bị stale sau git checkout

Khi checkout branch khác, nhiều file thay đổi cùng lúc.

**Giải pháp**:
```bash
# Option 1: Re-index (incremental, chỉ file thay đổi)
python -m cmd.cli index /workspace --project myproject -v

# Option 2: Force re-index (toàn bộ)
python -m cmd.cli index /workspace --project myproject --force

# Option 3: Dùng watch mode (tự detect)
python -m cmd.cli watch --project myproject
```

---

## Tham khảo nhanh

```bash
# Index
python -m cmd.cli index <path> --project <id> [-v] [-f]
python -m cmd.cli index --project <id> --status

# Search
python -m cmd.cli search --project <id> "query" [-k 10]

# Call graph
python -m cmd.cli graph --project <id> "project::file::func" [-d 2]

# Memory
python -m cmd.cli add-memory --project <id> --type business_rule "content"
python -m cmd.cli search-memory --project <id> --query "keyword"

# Watch
python -m cmd.cli watch --project <id> [--debounce 2]

# Server
python -m cmd.cli serve              # REST API (port 8000)
python -m cmd.cli mcp                # MCP server (stdio)

# Migrate
python -m cmd.cli migrate [--project <id>] [--dry-run]

# Validate
python -m cmd.cli validate-plugin
```
