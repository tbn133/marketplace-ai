# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Claude Code plugin **marketplace** containing code intelligence tools. The repo hosts multiple plugins under `plugins/`. Each plugin is self-contained with its own `.claude-plugin/plugin.json`, source code, skills, and MCP servers.

## Repository Structure

```text
.claude-plugin/marketplace.json     # Marketplace manifest
plugins/
  ci/                               # Plugin: AST indexing + search + memory
    .claude-plugin/plugin.json      # Plugin manifest
    app/                            # Source code (hexagonal architecture)
    cmd/cli.py                      # CLI entry point
    skills/                         # 6 Claude Code skills
    mcp-servers.json                # MCP server config
    requirements.txt
```

## Working with the ci plugin

All commands must be run from `plugins/ci/`:

```bash
cd plugins/ci

# Install dependencies (Python 3.12+)
pip install -r requirements.txt

# Index a codebase
python -m cmd.cli index ./path/to/repo --project myproject

# Search indexed code
python -m cmd.cli search --project myproject "query text"

# Show call graph
python -m cmd.cli graph --project myproject "project_id::file.py::func_name"

# Memory operations
python -m cmd.cli add-memory --project myproject --type business_rule "content"
python -m cmd.cli search-memory --project myproject --query "keyword"

# Start REST API server
python -m cmd.cli serve

# Start MCP server (stdio)
python -m cmd.cli mcp

# Validate plugin structure
python -m cmd.cli validate-plugin
```

## Marketplace Commands

```bash
# Users add this marketplace
claude plugin marketplace add github.com/tabi4/code-intelligence-system

# Install a plugin
claude plugin install ci@code-intelligence-system --scope project

# Or install from local path (development)
claude plugin install ./plugins/ci --scope project
```

## Architecture (ci plugin)

### Dual Storage Backend

Controlled by `STORAGE_BACKEND` env var (default: `local`):

- **local**: NetworkX (graph) + FAISS (vectors) + SQLite (memory) + in-memory cache. Zero external dependencies. Data persisted in `data/` directory.
- **production**: Neo4j + Qdrant + PostgreSQL + Redis. Docker Compose wires these up.

The `Container` in `app/container.py` is the composition root — it reads `STORAGE_BACKEND` and wires either local or production implementations.

### Ports & Adapters (Hexagonal Architecture)

- **Ports** (`app/domain/ports.py`): Protocol interfaces — `GraphStorePort`, `VectorStorePort`, `MemoryStorePort`, `EmbeddingPort`, `CachePort`.
- **Domain** (`app/domain/models.py`): Pure dataclasses — `FunctionNode`, `ClassNode`, `ImportNode`, `Memory`, `SearchResult`.
- **Infrastructure** (`app/infrastructure/`): Concrete implementations of each port (local + production).
- **Services** (`app/services/`): Business logic depending only on ports. `IndexingService`, `SearchService`, `MemoryService`, `MigrationService`.

### Key Constraints

- **AST-only parsing**: Never use LLM for code parsing. All extraction is via tree-sitter. Supports Python, TypeScript, JavaScript, Go, Rust, Java, C, C++.
- **Project isolation**: `project_id` is required on every data operation.
- **Embedding is a mock**: `HashEmbeddingService` uses deterministic hash-based vectors. Designed to be swapped for a real model (e.g., `bge-small`).

## Adding a New Plugin

1. Create `plugins/<name>/` with `.claude-plugin/plugin.json`
2. Add skills, MCP servers, agents as needed
3. Register in `.claude-plugin/marketplace.json` under `plugins` array

## Configuration

All config via environment variables with defaults in `plugins/ci/app/config.py`. Key vars: `STORAGE_BACKEND`, `NEO4J_URI`, `QDRANT_URL`, `POSTGRES_HOST`, `REDIS_URL`, `EMBEDDING_DIM`, `LOG_LEVEL`.
