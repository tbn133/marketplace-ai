---
name: analyze
description: Comprehensive code analysis combining semantic search, call graph traversal, and business memory. Use when user asks for deep analysis, impact assessment, refactoring guidance, or needs to understand a feature end-to-end across the codebase.
argument-hint: "<topic or function name>"
---

# Code Analyze

Perform comprehensive code analysis by orchestrating multiple Code Intelligence tools together. This combines semantic search, call graph analysis, and business memory into a unified investigation.

## When to use

- "Analyze how feature X works end-to-end"
- "What's the impact of changing function Y?"
- "Help me understand the authentication flow"
- "What should I know before refactoring module Z?"
- Deep investigation that needs multiple data sources

## Analysis workflow

### Step 1: Gather context from memory

Call `search_memory` to check if there are saved business rules, incidents, or notes related to the topic. This provides historical context before diving into code.

### Step 2: Search for relevant code

Call `search_code` with the user's topic/query to find the most relevant functions and entry points.

### Step 3: Trace the call graph

For each key function found in Step 2, call `get_call_graph` (depth 2-3) to understand:
- What calls it (entry points, API routes, event handlers)
- What it calls (dependencies, utilities, external services)

### Step 4: Read the actual code

Use the `Read` tool to read the source code of the most critical functions identified in Steps 2-3. Focus on:
- The main function body
- Key callers (to understand usage patterns)
- Key callees (to understand dependencies)

### Step 5: Synthesize findings

Present a structured analysis:

```
## Analysis: [Topic]

### Entry Points
- How this feature is triggered (API routes, CLI commands, events)

### Core Logic
- Main functions and their responsibilities
- Data flow through the system

### Dependencies
- Internal dependencies (other modules)
- External dependencies (libraries, services)

### Business Context
- Relevant business rules or past incidents from memory
- Constraints that must be respected

### Impact Assessment (if applicable)
- What would break if this code changes
- Upstream callers that depend on current behavior
- Downstream callees that might be affected

### Recommendations
- Suggested approach for the user's goal
- Risks to watch for
```

## Notes

- This skill orchestrates multiple MCP tools — it may take several steps
- Start broad (search) then narrow (graph + read) for efficiency
- Always check memory first — past incidents may be critical context
- If the codebase isn't indexed yet, suggest `/code:init` first
