---
name: init
description: Index a Python codebase using AST parsing (tree-sitter) to build call graphs and semantic search vectors. Use when user wants to index, re-index, or update the code intelligence database for a project.
disable-model-invocation: true
argument-hint: "<path> --project <project_id> [--force]"
---

# Code Index

Index a Python codebase using tree-sitter AST parsing. This builds:
- Function and class nodes with metadata (file, line numbers, docstrings)
- Call graph edges (caller → callee relationships)
- Semantic embedding vectors for search

## Usage

Run the indexing CLI command. The Code Intelligence System must be installed.

```
python -m cmd.cli index <path> --project <project_id> [--force]
```

## Arguments from user

- `$ARGUMENTS` — Parse the user's input to extract:
  - **path**: Directory to index (required). Use `.` or current working directory if not specified.
  - **project_id**: Project identifier (required). If not provided, ask the user or derive from the directory name.
  - **--force**: Include if user wants to re-index all files (ignoring SHA-256 cache).

## Steps

1. Determine the `path` and `project_id` from user arguments
2. If `project_id` is not provided, derive it from the directory basename (lowercase, hyphens for spaces)
3. Run the index command:
   ```bash
   cd ${CLAUDE_SKILL_DIR}/../.. && python -m cmd.cli index <path> --project <project_id>
   ```
4. Report the results: number of files, functions, and classes indexed
5. If errors occur (e.g., missing tree-sitter), suggest: `pip install -r requirements.txt`

## Notes

- Only Python files (`.py`) are supported currently
- Incremental indexing: unchanged files (by SHA-256) are skipped unless `--force` is used
- Data is stored in the `data/` directory under the Code Intelligence System root
