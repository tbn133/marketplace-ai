---
name: index
description: "Index a codebase using AST parsing (tree-sitter) for Python, TypeScript, JavaScript, Go, Rust, Java, C, C++, PHP. Check indexing status with --status. Use when user wants to index, re-index, check what is indexed, or update the code intelligence database."
argument-hint: "<path> --project <project_id> [--force] [--status]"
---

# Code Index

Index a codebase using tree-sitter AST parsing, or check what is already indexed.
Supports: Python, TypeScript, JavaScript, Go, Rust, Java, C, C++, PHP.

## Arguments from user

- `$ARGUMENTS` — Parse the user's input to extract:
  - **path**: Directory to index. Use the current working directory if not specified. Must be an **absolute path**.
  - **project_id**: Project group name (required). This is the **group** name, not the final project_id. The final `project_id` is always `{group}-{folder_basename}` (e.g. `--project tool` indexing `code-intelligence-system/` → `tool-code-intelligence-system`).
  - **--status**: Show indexed files and functions for the project. No indexing is performed.
  - **--force**: Re-index all files (ignoring SHA-256 cache).

## Steps

1. Parse `--project` value as the **group name**
2. Resolve `path` to an **absolute path** (prepend working directory if relative)
3. Derive the final `project_id` = `{group}-{basename_of_path}` (lowercase, spaces → hyphens)
   - Example: `--project tool`, path = `/home/user/code-intelligence-system` → `tool-code-intelligence-system`
   - This enables cross-repo search via wildcard `--project "tool-*"`
4. If user asks for status (e.g., `--status`, "what is indexed", "show indexed"):
   - Call MCP tool `index_status` with the derived `project_id`
5. Otherwise, call MCP tool `index_directory` with:
   - `path`: absolute path to directory
   - `project_id`: project identifier
   - `force`: true if `--force` specified
6. Report the results (files indexed, functions, classes, errors), including the derived `project_id`

## Notes

- Supported code: `.py`, `.ts`, `.tsx`, `.js`, `.jsx`, `.go`, `.rs`, `.java`, `.c`, `.h`, `.cpp`, `.cc`, `.php`
- Supported documents: `.md`, `.txt`, `.docx`, `.xlsx`, `.pdf`, `.pptx`, `.html`, `.csv`, `.json`, `.xml`
- Document conversion uses `markitdown` (auto-installed) — converts rich documents to markdown for chunking
- Incremental indexing: unchanged files (by SHA-256) are skipped unless `--force` is used
- Data is stored in the shared data directory (`~/.code-intelligence/data/`)
- After indexing, a `.claude/code-index.json` marker file is written to the target project directory
- For multi-repo projects, use the naming convention `{group}-{reponame}` so repos in the same group can search across each other with wildcard `{group}-*`
