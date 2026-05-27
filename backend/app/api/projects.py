"""
项目API
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

router = APIRouter()

MOCK_PROJECTS = [
    {"id": 1, "name": "智能协同平台", "status": "active", "progress": 60, "member_count": 5},
    {"id": 2, "name": "知识图谱建设", "status": "active", "progress": 40, "member_count": 3},
]


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    goal: Optional[str] = None
    key_results: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


@router.get("/")
async def list_projects(status: Optional[str] = None):
    projects = MOCK_PROJECTS if status is None else [p for p in MOCK_PROJECTS if p["status"] == status]
    return {"projects": projects, "total": len(projects)}


@router.get("/{project_id}")
async def get_project(project_id: int):
    project = next((p for p in MOCK_PROJECTS if p["id"] == project_id), None)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return project


@router.post("/", status_code=201)
async def create_project(request: ProjectCreate):
    return {"id": 100, "name": request.name, "status": "active", "created_at": datetime.utcnow().isoformat()}
