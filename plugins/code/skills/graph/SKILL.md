---
name: graph
description: "Analyze call graph relationships for a function — show callers, callees, and dependency chains. Use when user asks about function dependencies, call chains, impact analysis, or what calls this function / what does this function call."
argument-hint: "<function_id> --project <project_id> [--depth N]"
---

# Code Graph

Retrieve and visualize the call graph for a specific function. Shows who calls it (callers) and what it calls (callees), up to a configurable depth.

## When to use

- "What calls this function?"
- "What does this function call?"
- "Show me the dependency chain for X"
- "What's the impact if I change function Y?"
- Analyzing function relationships before refactoring

## How to use

Use the MCP tool `get_call_graph` provided by the `code` server:

- **project_id** (required): The project identifier
- **function_id** (required): Function ID in format `{project_id}::{file_path}::{ClassName.}func_name`
- **depth** (optional, default 2): How many levels deep to traverse (1-5)

## Steps

1. Determine the `project_id` and `function_id`:
   - If user gives a simple function name, help construct the full ID
   - If unsure of the exact ID, use `search_code` first to find the function
2. Call the `get_call_graph` MCP tool
3. Present the graph as a readable tree:

```
function_name (file.py:42)
├── calls:
│   ├── helper_a (utils.py:10)
│   └── helper_b (utils.py:25)
└── called by:
    ├── main_handler (routes.py:15)
    └── test_function (test_main.py:8)
```

4. If depth > 1, show nested relationships
5. Highlight circular dependencies if detected

## Function ID format

`{project_id}::{relative_file_path}::{ClassName.}func_name`

Examples:
- `myproject::app/services/auth.py::authenticate`
- `myproject::app/models/user.py::User.validate`

## Notes

- The codebase must be indexed first — suggest `/code:init` if no data found
- Deep graphs (depth > 3) may return large results; suggest starting with depth 2
