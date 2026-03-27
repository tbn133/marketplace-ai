---
name: init
description: "Index a codebase using AST parsing (tree-sitter) for Python, TypeScript, JavaScript, Go, Rust, Java, C, C++, PHP. Check indexing status with --status. Use when user wants to index, re-index, check what is indexed, or update the code intelligence database."
argument-hint: "<path> --project <project_id> [--force] [--status]"
---

# Code Index

Index a codebase using tree-sitter AST parsing, or check what is already indexed.
Supports: Python, TypeScript, JavaScript, Go, Rust, Java, C, C++, PHP.

## Arguments from user

- `$ARGUMENTS` — Parse the user's input to extract:
  - **path**: Directory to index. Use the current working directory if not specified. Must be an **absolute path**.
  - **project_id**: Project identifier (required). If not provided, derive from the directory basename (lowercase, hyphens for spaces). For multi-repo projects, use format `{group}-{reponame}` (e.g. `myapp-backend`).
  - **--status**: Show indexed files and functions for the project. No indexing is performed.
  - **--force**: Re-index all files (ignoring SHA-256 cache).

## Steps

1. Determine the `project_id` from user arguments
2. Resolve `path` to an **absolute path** (prepend working directory if relative)
3. If user asks for status (e.g., `--status`, "what is indexed", "show indexed"):
   - Call MCP tool `index_status` with `project_id`
4. Otherwise, call MCP tool `index_directory` with:
   - `path`: absolute path to directory
   - `project_id`: project identifier
   - `force`: true if `--force` specified
5. Report the results (files indexed, functions, classes, errors)

## Notes

- Supported: `.py`, `.ts`, `.tsx`, `.js`, `.jsx`, `.go`, `.rs`, `.java`, `.c`, `.h`, `.cpp`, `.cc`, `.php`
- Incremental indexing: unchanged files (by SHA-256) are skipped unless `--force` is used
- Data is stored in the shared data directory (`~/.code-intelligence/data/`)
- For multi-repo projects, use the naming convention `{group}-{reponame}` so repos in the same group can search across each other with wildcard `{group}-*`
