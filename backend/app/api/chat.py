"""
对话API
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

router = APIRouter()


class MessageCreate(BaseModel):
    role: str
    content: str
    conversation_id: Optional[int] = None


class ConversationCreate(BaseModel):
    title: Optional[str] = "新对话"


@router.post("/conversations")
async def create_conversation(request: ConversationCreate):
    return {
        "id": 1,
        "title": request.title or "新对话",
        "user_id": 1,
        "created_at": datetime.utcnow().isoformat(),
    }


@router.get("/conversations")
async def list_conversations(limit: int = 20):
    return {
        "conversations": [
            {"id": 1, "title": "项目A任务讨论", "message_count": 15, "created_at": "2026-05-14T10:00:00", "updated_at": "2026-05-15T09:30:00"},
            {"id": 2, "title": "新对话", "message_count": 3, "created_at": "2026-05-15T08:00:00", "updated_at": "2026-05-15T08:15:00"},
        ],
        "total": 2,
    }


@router.get("/conversations/{conversation_id}/messages")
async def get_messages(conversation_id: int, limit: int = 50):
    return {
        "messages": [
            {"id": 1, "role": "user", "content": "查找张三参与的重点项目下的所有任务", "created_at": "2026-05-15T09:00:00"},
            {"id": 2, "role": "assistant", "content": "好的，我为您找到了张三参与的以下项目及任务...", "created_at": "2026-05-15T09:00:05"},
        ]
    }
