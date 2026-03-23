---
name: init
description: "Index a codebase using AST parsing (tree-sitter) for Python, TypeScript, JavaScript, Go, Rust, Java, C, C++. Check indexing status with --status. Use when user wants to index, re-index, check what is indexed, or update the code intelligence database."
disable-model-invocation: true
argument-hint: "<path> --project <project_id> [--force] [--status] [--verbose]"
---

# Code Index

Index a codebase using tree-sitter AST parsing, or check what is already indexed.
Supports: Python, TypeScript, JavaScript, Go, Rust, Java, C, C++.

## Modes

### Index mode (default)
```
python -m cmd.cli index <path> --project <project_id> [--force] [--verbose]
```

### Status mode
```
python -m cmd.cli index --project <project_id> --status
```

## Arguments from user

- `$ARGUMENTS` — Parse the user's input to extract:
  - **path**: Directory to index. Use `.` or current working directory if not specified. Not needed with `--status`.
  - **project_id**: Project identifier (required). If not provided, derive from the directory basename (lowercase, hyphens for spaces).
  - **--status**: Show indexed files and functions for the project. No indexing is performed.
  - **--force**: Re-index all files (ignoring SHA-256 cache).
  - **--verbose** / **-v**: Show per-file progress during indexing.

## Steps

1. Determine the `project_id` from user arguments
2. If user asks for status (e.g., `--status`, "what is indexed", "show indexed"):
   ```bash
   cd ${CLAUDE_SKILL_DIR}/../.. && python -m cmd.cli index --project <project_id> --status
   ```
3. Otherwise, determine `path` and run the index command:
   ```bash
   cd ${CLAUDE_SKILL_DIR}/../.. && python -m cmd.cli index <path> --project <project_id> [--force] [--verbose]
   ```
4. Report the results
5. If errors occur (e.g., missing tree-sitter), suggest: `pip install -r requirements.txt`

## Notes

- Supported: `.py`, `.ts`, `.tsx`, `.js`, `.jsx`, `.go`, `.rs`, `.java`, `.c`, `.h`, `.cpp`, `.cc`
- Incremental indexing: unchanged files (by SHA-256) are skipped unless `--force` is used
- Use `--verbose` to see per-file progress: `[+]` indexed, `[=]` skipped, `[!]` error
- Data is stored in the `data/` directory under the Code Intelligence System root
