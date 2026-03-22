---
name: remember
description: Save persistent business memory — business rules, incident notes, architecture decisions, or any knowledge that should survive across sessions. Use when user says "remember this", "save this rule", "note that", or shares important project knowledge.
argument-hint: [content]
---

# Remember

Store persistent business memory that survives across Claude Code sessions. Unlike Claude's built-in memory (CLAUDE.md-based), this stores structured entries with types, tags, and searchable content in a database.

## When to use

- User says "remember this", "save this", "note that"
- User shares a business rule, constraint, or decision
- An incident occurs and the resolution should be recorded
- Architecture decisions or conventions need to be documented
- Any knowledge that should be retrievable in future sessions

## How to use

Use the MCP tool `add_memory` provided by the `ci` server:

- **project_id** (required): The project identifier
- **type** (required): One of `business_rule`, `incident`, `note`
- **content** (required): The memory content
- **tags** (optional): Array of tags for categorization

## Memory types

| Type | When to use | Example |
|------|-------------|---------|
| `business_rule` | Constraints, invariants, domain rules | "Orders over $500 require manager approval" |
| `incident` | Bugs found, outages, resolutions | "Redis timeout caused by connection pool exhaustion — fixed by increasing max_connections" |
| `note` | General knowledge, conventions, decisions | "We use snake_case for all Python API endpoints" |

## Steps

1. Determine the `project_id` from context or ask the user
2. Classify the memory type based on content
3. Extract or summarize the content concisely
4. Suggest relevant tags based on the content
5. Call `add_memory` MCP tool
6. Confirm to the user what was saved

## Notes

- Memories are isolated per project — they won't leak across projects
- Use `/ci:recall` to search saved memories later
- Keep content concise but complete — this is what future sessions will see
