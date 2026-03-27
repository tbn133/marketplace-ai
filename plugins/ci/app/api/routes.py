"""REST API routes — access services via container."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

router = APIRouter()


# --- Request/Response schemas (API layer only) ---

class IndexRequest(BaseModel):
    path: str
    project_id: str
    force: bool = False


class MemoryCreateRequest(BaseModel):
    project_id: str
    type: str
    content: str
    tags: list[str] = Field(default_factory=list)


# --- Helpers ---

def _container(request: Request):
    return request.app.state.container


# --- Routes ---

@router.get("/search")
def search_code(
    request: Request,
    project_id: str = Query(..., description="Project identifier"),
    query: str = Query(..., description="Search query"),
    top_k: int = Query(10, ge=1, le=100),
):
    svc = _container(request).search_service
    result = svc.search(project_id=project_id, query=query, top_k=top_k)
    return asdict(result)


@router.get("/function/{function_id:path}")
def get_function(
    request: Request,
    function_id: str,
    project_id: str = Query(...),
):
    svc = _container(request).search_service
    func = svc.get_function(project_id=project_id, function_id=function_id)
    if not func:
        raise HTTPException(status_code=404, detail="Function not found")
    return func


@router.get("/graph")
def get_call_graph(
    request: Request,
    function_id: str = Query(...),
    project_id: str = Query(...),
    depth: int = Query(2, ge=1, le=5),
):
    svc = _container(request).search_service
    return svc.get_call_graph(project_id=project_id, function_id=function_id, depth=depth)


@router.post("/memory")
def create_memory(request: Request, data: MemoryCreateRequest):
    svc = _container(request).memory_service
    memory = svc.add(
        project_id=data.project_id,
        type=data.type,
        content=data.content,
        tags=data.tags,
    )
    return asdict(memory)


@router.get("/memory/search")
def search_memory(
    request: Request,
    project_id: str = Query(...),
    query: str = Query(""),
    type: str = Query("", alias="type"),
    limit: int = Query(20, ge=1, le=100),
):
    svc = _container(request).memory_service
    result = svc.search(project_id=project_id, query=query, type_filter=type, limit=limit)
    return asdict(result)


@router.delete("/memory/{memory_id}")
def delete_memory(request: Request, memory_id: str):
    svc = _container(request).memory_service
    if not svc.delete(memory_id):
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"ok": True}


@router.post("/index")
def index_directory(request: Request, data: IndexRequest):
    svc = _container(request).indexing_service
    info = svc.index_directory(
        directory=data.path,
        project_id=data.project_id,
        force=data.force,
    )
    return asdict(info)


@router.post("/index/file")
def index_file(request: Request, data: dict):
    """Incremental re-index a single file. Used by PostToolUse hook."""
    svc = _container(request).indexing_service
    from pathlib import Path

    project_id = data.get("project_id", "")
    file_path = data.get("file_path", "")
    root_path = data.get("root_path", "")

    if not all([project_id, file_path, root_path]):
        raise HTTPException(status_code=400, detail="Missing project_id, file_path, or root_path")

    info = svc.index_files(
        [Path(file_path)],
        project_id=project_id,
        root=Path(root_path),
    )
    return asdict(info)


@router.get("/projects")
def list_projects(
    request: Request,
    group: str = Query("", description="Group prefix filter (e.g. 'myapp')"),
):
    svc = _container(request).indexing_service
    projects = svc.list_projects(group_prefix=group if group else None)
    return [
        {
            "project_id": p.project_id,
            "root_path": p.root_path,
            "registered_at": p.registered_at,
        }
        for p in projects
    ]


@router.get("/projects/{project_id}/status")
def project_status(request: Request, project_id: str):
    svc = _container(request).indexing_service
    info = svc.get_project_status(project_id)
    if not info["has_data"]:
        raise HTTPException(status_code=404, detail="Project not indexed")
    return info


@router.get("/health")
def health():
    return {"status": "ok"}
