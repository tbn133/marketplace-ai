# Design: Reliable code-index.json Update After Indexing

## Problem

After indexing a project via CLI or MCP, `_write_code_index_json()` in `IndexingService` silently swallows `OSError` exceptions. The `.claude/code-index.json` marker file in the target project does not get updated, even though the actual index data (FAISS, graph, hashes, registry) is persisted successfully.

This causes downstream issues: when Claude opens a session in the target project, the `code-search-plugin` rule reads `code-index.json` to determine the `project_id`. If this file is stale, Claude uses the wrong `project_id` for search queries.

## Solution

Approach A: Make `_write_code_index_json` robust with retry/fallback, report success/failure in `ProjectInfo`, and provide manual update instructions when auto-update fails.

## Changes

### 1. `ProjectInfo` dataclass (`app/domain/models.py`)

Add two fields:

```python
@dataclass
class ProjectInfo:
    project_id: str
    root_path: str
    total_files: int = 0
    total_functions: int = 0
    total_classes: int = 0
    skipped_files: int = 0
    error_files: list[tuple[str, str]] = field(default_factory=list)
    code_index_updated: bool = True          # NEW
    code_index_error: str | None = None      # NEW
```

- `code_index_updated`: Whether `.claude/code-index.json` was successfully written.
- `code_index_error`: Error message with manual update instructions when `code_index_updated` is `False`.

### 2. `_write_code_index_json` method (`app/services/indexing_service.py`)

Change signature from `-> None` to `-> tuple[bool, str | None]`.

Flow:
1. Try atomic write (write to `.json.tmp`, then `rename` to `.json`).
2. If atomic write fails, fallback to direct `write_text()`.
3. If both fail, return `(False, error_message)` with manual update instructions.
4. On success, return `(True, None)`.

Manual update instruction format:
```
Failed to write .claude/code-index.json in <root>: <error>.
To update manually, write this to <root>/.claude/code-index.json:
{"project_id": "<project_id>", "path": "<root>"}
```

### 3. `index_directory` method (`app/services/indexing_service.py`)

After calling `_write_code_index_json`, capture the return value and set `code_index_updated` and `code_index_error` on the `ProjectInfo` before returning.

### 4. CLI `index` command (`cmd/cli.py`)

After printing the "Done!" summary, check `info.code_index_updated`. If `False`, print a warning block:

```
WARNING: Could not update .claude/code-index.json: <error>
  To update manually, write this to <path>/.claude/code-index.json:
  {"project_id": "...", "path": "..."}
```

### 5. MCP `index_directory` tool (no change needed)

`asdict(info)` already serializes all `ProjectInfo` fields, so `code_index_updated` and `code_index_error` appear in the JSON response automatically.

## Files Changed

| File | Change |
|---|---|
| `plugins/code/app/domain/models.py` | Add `code_index_updated`, `code_index_error` to `ProjectInfo` |
| `plugins/code/app/services/indexing_service.py` | Fix `_write_code_index_json` with retry/fallback + return result; update `index_directory` to use result |
| `plugins/code/cmd/cli.py` | Print warning when `code_index_updated` is `False` |

## Testing

- Existing test `test_indexing_service.py` already verifies `code-index.json` creation — extend to verify the new fields in `ProjectInfo`.
- Add test case for fallback write (mock `Path.rename` to raise `OSError`).
- Add test case for complete failure (mock both `rename` and `write_text` to raise `OSError`) — verify `code_index_updated=False` and error message contains manual instructions.
