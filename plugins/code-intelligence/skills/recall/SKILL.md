---
name: recall
description: Search persistent business memory — retrieve saved business rules, incident notes, and project knowledge from previous sessions. Use when user asks "what do we know about", "what was the rule for", "recall", or needs context from past decisions.
argument-hint: [query]
---

# Recall

Search and retrieve persistent business memories saved in previous sessions.

## When to use

- User asks "what do we know about X?"
- User asks "what was the rule for Y?"
- User asks "recall" or "remember when"
- Before making changes that might conflict with saved business rules
- When context from past sessions would inform current work

## How to use

Use the MCP tool `search_memory` provided by the `code-intelligence` server:

- **project_id** (required): The project identifier
- **query** (optional): Search text to filter memories
- **type** (optional): Filter by type — `business_rule`, `incident`, `note`

## Steps

1. Determine the `project_id` from context or ask the user
2. Call `search_memory` MCP tool with the user's query
3. Present results grouped by type:

```
Business Rules:
  - Orders over $500 require manager approval [tags: orders, approval]

Incidents:
  - Redis timeout caused by connection pool exhaustion [tags: redis, performance]

Notes:
  - We use snake_case for all Python API endpoints [tags: conventions]
```

4. If no results, suggest:
   - Broadening the search query
   - Checking if the project has been indexed with the correct project_id
   - Using `/remember` to save new knowledge

## Notes

- Memories are isolated per project
- Empty query returns all memories for the project
- Use type filter to narrow results (e.g., only `business_rule`)
