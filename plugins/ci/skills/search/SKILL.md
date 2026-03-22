---
name: search
description: Search indexed code using semantic similarity and call graph expansion. Use when user asks to find functions, understand code, locate implementations, or search the codebase by meaning rather than exact text.
---

# Code Search

Search indexed code using semantic vectors and call graph expansion. Returns matching functions ranked by similarity, plus related callers/callees.

## When to use

- User asks "where is X implemented?"
- User asks "find functions related to Y"
- User wants to understand how a feature works across files
- User needs to locate code by description, not exact name

## How to search

Use the MCP tool `search_code` provided by the `ci` server:

- **project_id** (required): The project identifier used during indexing
- **query** (required): Natural language description of what to find
- **top_k** (optional, default 10): Number of results to return

## Steps

1. Determine the `project_id`. If not specified by the user:
   - Check if the current directory name matches a known project
   - Ask the user which project to search
2. Call the `search_code` MCP tool with the user's query
3. Present results clearly:
   - List matched functions with file paths and line numbers
   - Highlight the most relevant matches
   - Show related functions (callers/callees) if present
4. If no results found, suggest the user run `/ci:init` first

## Output format

For each result, show:
```
[score] function_name — file/path.py:line
  → calls: func_a, func_b
  → called by: func_c
```

## Notes

- Search quality depends on indexing completeness — suggest re-indexing if results seem stale
- The system uses hash-based embeddings by default; results are based on token overlap rather than deep semantics
