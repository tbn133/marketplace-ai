"""REST API routes — access services via container."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

router = APIRouter()


# --- Request/Response schemas (API layer only) ---

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


@router.get("/health")
def health():
    return {"status": "ok"}
