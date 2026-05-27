"""
任务API
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

router = APIRouter()

# 模拟任务数据
MOCK_TASKS = [
    {"id": 1, "title": "需求文档撰写", "status": "in_progress", "priority": "high", "assignee": "张三", "score": None},
    {"id": 2, "title": "代码开发", "status": "completed", "priority": "high", "assignee": "张三", "score": 92},
    {"id": 3, "title": "图谱设计", "status": "in_progress", "priority": "medium", "assignee": "张三", "score": 88},
]


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    project_id: Optional[int] = None
    assignee_id: Optional[int] = None
    priority: Optional[str] = "medium"
    due_date: Optional[str] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None


@router.get("/")
async def list_tasks(status: Optional[str] = None):
    tasks = MOCK_TASKS if status is None else [t for t in MOCK_TASKS if t["status"] == status]
    return {"tasks": tasks, "total": len(tasks)}


@router.get("/{task_id}")
async def get_task(task_id: int):
    task = next((t for t in MOCK_TASKS if t["id"] == task_id), None)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@router.post("/", status_code=201)
async def create_task(request: TaskCreate):
    return {"id": 100, "title": request.title, "status": "pending", "created_at": datetime.utcnow().isoformat()}


@router.put("/{task_id}")
async def update_task(task_id: int, request: TaskUpdate):
    return {"id": task_id, "updated": True}
