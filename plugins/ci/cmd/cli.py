"""CLI entry point — uses Container for all dependencies."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import click
import uvicorn

from app.container import create_container

PLUGIN_ROOT = Path(__file__).resolve().parent.parent


@click.group()
def cli():
    """Code Intelligence System CLI."""
    pass


@cli.command()
@click.argument("path", type=click.Path(exists=True), required=False, default=None)
@click.option("--project", "-p", required=True, help="Project identifier")
@click.option("--force", "-f", is_flag=True, help="Force re-index all files")
@click.option("--verbose", "-v", is_flag=True, help="Show per-file progress")
@click.option("--status", "-s", is_flag=True, help="Show what is already indexed, do not index")
def index(path: str | None, project: str, force: bool, verbose: bool, status: bool):
    """Index a source code directory, or check what is already indexed.

    \b
    Examples:
      python -m cmd.cli index ./repo --project hotel
      python -m cmd.cli index ./repo --project hotel -v
      python -m cmd.cli index --project hotel --status
    """
    container = create_container()

    if status:
        info = container.indexing_service.get_project_status(project)
        if not info["has_data"]:
            click.echo(f"Project '{project}' has not been indexed yet.")
            return
        click.echo(f"Project: {project}")
        click.echo(f"  Files:     {info['indexed_files']}")
        click.echo(f"  Functions: {info['total_functions']}")
        click.echo(f"\nIndexed files:")
        for f in info["files"]:
            click.echo(f"  {f}")
        return

    if path is None:
        raise click.UsageError("PATH is required when not using --status.")

    click.echo(f"Indexing '{path}' for project '{project}'...")

    def on_progress(action: str, file_path: str) -> None:
        if verbose:
            symbol = {"index": "+", "skip": "=", "error": "!"}[action]
            click.echo(f"  [{symbol}] {file_path}")

    info = container.indexing_service.index_directory(
        path, project_id=project, force=force, on_progress=on_progress,
    )

    click.echo(f"\nDone! Indexed {info.total_files} files (skipped {info.skipped_files} unchanged):")
    click.echo(f"  Functions: {info.total_functions}")
    click.echo(f"  Classes:   {info.total_classes}")
    if info.error_files:
        click.echo(f"  Errors:    {len(info.error_files)}")
        for fp, err in info.error_files[:10]:
            click.echo(f"    ! {fp}: {err}")


@cli.command()
@click.option("--project", "-p", required=True)
@click.argument("query")
@click.option("--top-k", "-k", default=10)
def search(project: str, query: str, top_k: int):
    """Search indexed code.

    Example: python -m cmd.cli search --project hotel "user authentication"
    """
    container = create_container()
    result = container.search_service.search(project_id=project, query=query, top_k=top_k)

    if not result.functions:
        click.echo("No results found.")
        return

    click.echo(f"Found {len(result.functions)} functions:")
    for fn in result.functions:
        score = fn.get("score", 0)
        click.echo(f"  [{score:.3f}] {fn.get('name', '?')} — {fn.get('file', '?')}:{fn.get('start_line', '?')}")

    if result.related:
        click.echo(f"\nRelated ({len(result.related)}):")
        for r in result.related[:5]:
            click.echo(f"  {r.get('name', '?')} — {r.get('file', '?')}")


@cli.command()
@click.option("--project", "-p", required=True)
@click.argument("function_id")
@click.option("--depth", "-d", default=2)
def graph(project: str, function_id: str, depth: int):
    """Show call graph for a function."""
    container = create_container()
    result = container.search_service.get_call_graph(
        project_id=project, function_id=function_id, depth=depth,
    )
    click.echo(json.dumps(result, indent=2))


@cli.command()
@click.option("--project", "-p", required=True, help="Project identifier")
@click.option("--debounce", "-d", default=2.0, type=float, help="Debounce seconds (default: 2)")
def watch(project: str, debounce: float):
    """Watch a project directory and auto re-index on file changes.

    The project must have been indexed at least once so the root path is known.

    \b
    Examples:
      python -m cmd.cli watch --project hotel
      python -m cmd.cli watch --project hotel --debounce 5
    """
    container = create_container()

    root = container.indexing_service.get_project_root(project)
    if root is None:
        click.echo(f"Error: Project '{project}' has no registered root path.", err=True)
        click.echo("Run 'index' first to register the project.", err=True)
        raise SystemExit(1)

    click.echo(f"Watching '{root}' for project '{project}' (debounce={debounce}s)")
    click.echo("Press Ctrl+C to stop.\n")

    def on_reindex(project_id: str, indexed: int, deleted: int) -> None:
        parts = []
        if indexed:
            parts.append(f"{indexed} file(s) re-indexed")
        if deleted:
            parts.append(f"{deleted} file(s) removed")
        if parts:
            click.echo(f"  [{project_id}] {', '.join(parts)}")

    try:
        container.watcher_service.watch(
            project_id=project,
            root=root,
            debounce_seconds=debounce,
            on_reindex=on_reindex,
        )
    except KeyboardInterrupt:
        click.echo("\nStopped.")


@cli.command("add-memory")
@click.option("--project", "-p", required=True)
@click.option("--type", "-t", "mem_type", required=True, help="Memory type: business_rule, incident, note")
@click.option("--tags", default="", help="Comma-separated tags")
@click.argument("content")
def add_memory(project: str, mem_type: str, tags: str, content: str):
    """Add a memory entry."""
    container = create_container()
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    memory = container.memory_service.add(
        project_id=project, type=mem_type, content=content, tags=tag_list,
    )
    click.echo(f"Memory created: {memory.id}")


@cli.command("search-memory")
@click.option("--project", "-p", required=True)
@click.option("--query", "-q", default="")
@click.option("--type", "-t", "type_filter", default="")
def search_memory(project: str, query: str, type_filter: str):
    """Search memory entries."""
    container = create_container()
    result = container.memory_service.search(
        project_id=project, query=query, type_filter=type_filter,
    )

    if not result.memories:
        click.echo("No memories found.")
        return

    for m in result.memories:
        click.echo(f"  [{m.type}] {m.content[:80]}{'...' if len(m.content) > 80 else ''}")
        if m.tags:
            click.echo(f"    tags: {', '.join(m.tags)}")


@cli.command()
@click.option("--host", default="0.0.0.0")
@click.option("--port", default=8000, type=int)
def serve(host: str, port: int):
    """Start the REST API server."""
    click.echo(f"Starting API server on {host}:{port}...")
    uvicorn.run("app.api.server:app", host=host, port=port, reload=False)


@cli.command("mcp")
def run_mcp():
    """Start the MCP server (stdio)."""
    from app.mcp.server import run_mcp_server

    click.echo("Starting MCP server on stdio...", err=True)
    asyncio.run(run_mcp_server())


@cli.command("serve-mcp")
@click.option("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
@click.option("--port", default=8100, type=int, help="Port (default: 8100)")
@click.option(
    "--data-dir",
    default="~/.code-intelligence/data",
    help="Shared data directory (default: ~/.code-intelligence/data)",
)
@click.option("--log-level", default="INFO", help="Log level (default: INFO)")
def serve_mcp(host: str, port: int, data_dir: str, log_level: str):
    """Start the MCP server over HTTP for multi-repo sharing.

    All Claude instances connect to this single server via:

    \b
      { "mcpServers": { "ci": { "url": "http://HOST:PORT/mcp" } } }

    \b
    Index repos first (use same --data-dir):
      DATA_DIR=~/.code-intelligence/data python -m cmd.cli index /repo --project myapp-backend

    \b
    Examples:
      python -m cmd.cli serve-mcp
      python -m cmd.cli serve-mcp --port 9000 --data-dir /shared/ci-data
    """
    from app.mcp.http_server import run_http_mcp_server

    resolved = Path(data_dir).expanduser().resolve()
    click.echo(f"Starting MCP HTTP server on {host}:{port}")
    click.echo(f"Data directory: {resolved}")
    click.echo(f"Connect via: http://{host}:{port}/mcp")
    run_http_mcp_server(host=host, port=port, data_dir=data_dir, log_level=log_level)


@cli.command()
@click.option("--project", "-p", default=None, help="Migrate specific project (default: all discovered)")
@click.option("--source-dir", "-s", default="./data", type=click.Path(exists=True), help="Local data directory")
@click.option("--dry-run", is_flag=True, help="Show what would be migrated without writing")
def migrate(project: str | None, source_dir: str, dry_run: bool):
    """Migrate data from local storage to production backend.

    Reads from local files (NetworkX + FAISS + SQLite) and writes to
    production services (Neo4j + Qdrant + PostgreSQL).

    \b
    Examples:
      python -m cmd.cli migrate --dry-run
      python -m cmd.cli migrate --project hotel
      python -m cmd.cli migrate -s ./data
    """
    import os
    from pathlib import Path

    from app.config import load_config
    from app.infrastructure.embedding import HashEmbeddingService
    from app.infrastructure.graph_store import NetworkXGraphStore
    from app.infrastructure.memory_cache import MemoryCache
    from app.infrastructure.memory_store import SqliteMemoryStore
    from app.infrastructure.vector_store import FaissVectorStore
    from app.services.migration_service import MigrationService, discover_local_projects

    data_path = Path(source_dir).resolve()

    # Discover projects
    if project:
        projects = [project]
    else:
        projects = discover_local_projects(data_path)
        if not projects:
            click.echo(f"No projects found in {data_path}")
            return

    click.echo(f"Source: {data_path}")
    click.echo(f"Projects to migrate: {', '.join(projects)}")

    if dry_run:
        click.echo("(DRY RUN — no data will be written)\n")

    # Source: always local
    config = load_config()
    embedding = HashEmbeddingService(dimension=config.embedding.dimension)
    source_graph = NetworkXGraphStore(data_dir=data_path)
    source_vector = FaissVectorStore(data_dir=data_path, dimension=embedding.dimension)
    db_path = data_path / "db.sqlite"
    source_memory = SqliteMemoryStore(db_path=db_path) if db_path.exists() else None

    # Dry-run: use source as both source and target (just counts, no writes)
    if dry_run:
        migration = MigrationService(
            source_graph=source_graph,
            source_vector=source_vector,
            source_memory=source_memory,
            target_graph=source_graph,
            target_vector=source_vector,
            target_memory=source_memory,
        )
    else:
        # Target: production container
        os.environ["STORAGE_BACKEND"] = "production"
        try:
            target_container = create_container()
        except Exception as e:
            click.echo(f"ERROR: Cannot connect to production services: {e}", err=True)
            click.echo("Make sure Neo4j, Qdrant, PostgreSQL, Redis are running.", err=True)
            click.echo("Hint: docker compose up -d", err=True)
            raise SystemExit(1)

        migration = MigrationService(
            source_graph=source_graph,
            source_vector=source_vector,
            source_memory=source_memory,
            target_graph=target_container.graph_store,
            target_vector=target_container.vector_store,
            target_memory=target_container.memory_store,
        )

    total_stats = {"graph_nodes": 0, "graph_edges": 0, "vectors": 0, "memories": 0}

    for pid in projects:
        click.echo(f"\n--- Migrating project: {pid} ---")
        stats = migration.migrate_project(pid, dry_run=dry_run)
        click.echo(f"  Nodes:    {stats['graph_nodes']}")
        click.echo(f"  Edges:    {stats['graph_edges']}")
        click.echo(f"  Vectors:  {stats['vectors']}")
        click.echo(f"  Memories: {stats['memories']}")

        for k in total_stats:
            total_stats[k] += stats[k]

    click.echo(f"\n{'=== DRY RUN SUMMARY ===' if dry_run else '=== MIGRATION COMPLETE ==='}")
    click.echo(f"  Total nodes:    {total_stats['graph_nodes']}")
    click.echo(f"  Total edges:    {total_stats['graph_edges']}")
    click.echo(f"  Total vectors:  {total_stats['vectors']}")
    click.echo(f"  Total memories: {total_stats['memories']}")


@cli.command()
def validate_plugin():
    """Validate plugin structure for distribution."""
    manifest_path = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
    skills_dir = PLUGIN_ROOT / "skills"
    mcp_config = PLUGIN_ROOT / "mcp-servers.json"

    errors = []
    if not manifest_path.exists():
        errors.append(f"Missing manifest: {manifest_path}")
    if not skills_dir.exists():
        errors.append(f"Missing skills directory: {skills_dir}")
    if not mcp_config.exists():
        errors.append(f"Missing MCP config: {mcp_config}")

    skill_dirs = list(skills_dir.iterdir()) if skills_dir.exists() else []
    for sd in sorted(skill_dirs):
        skill_md = sd / "SKILL.md"
        if sd.is_dir() and not skill_md.exists():
            errors.append(f"Missing SKILL.md in {sd.name}/")

    if errors:
        click.echo("Validation FAILED:")
        for e in errors:
            click.echo(f"  - {e}")
        raise SystemExit(1)

    manifest = json.loads(manifest_path.read_text())
    click.echo(f"Plugin: {manifest['name']} v{manifest.get('version', '?')}")
    click.echo(f"Skills: {len(skill_dirs)}")
    for sd in sorted(skill_dirs):
        click.echo(f"  - {sd.name}")
    click.echo(f"MCP config: {mcp_config}")
    click.echo("\nValidation OK. Ready for distribution.")
    click.echo(f"\nInstall methods:")
    click.echo(f"  # From GitHub (after pushing)")
    click.echo(f"  claude plugin install ci")
    click.echo(f"  # From local path (development)")
    click.echo(f"  claude plugin install {PLUGIN_ROOT} --scope project")


if __name__ == "__main__":
    cli()
