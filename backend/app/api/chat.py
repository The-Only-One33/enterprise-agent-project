"""
对话 API — 会话与消息 MySQL 持久化
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.services.conversation_service import get_conversation_service

router = APIRouter()


class MessageCreate(BaseModel):
    role: str
    content: str
    conversation_id: Optional[int] = None


class ConversationCreate(BaseModel):
    title: Optional[str] = "新对话"


def _user_scope(
    tenant_code: Optional[str],
    employ_code: Optional[str],
) -> tuple[str, str]:
    return tenant_code or "TENANT_DEFAULT", employ_code or "E_DEFAULT"


def _iso(dt: datetime) -> str:
    return dt.isoformat()


@router.post("/conversations")
async def create_conversation(
    request: ConversationCreate,
    tenant_code: Optional[str] = Header(None, alias="X-Tenant-Code"),
    employ_code: Optional[str] = Header(None, alias="X-Employ-Code"),
):
    tenant_id, user_key = _user_scope(tenant_code, employ_code)
    svc = get_conversation_service()
    conv = await svc.create_conversation(
        tenant_id=tenant_id,
        user_key=user_key,
        title=request.title,
    )
    return {
        "id": conv.id,
        "title": conv.title,
        "user_id": user_key,
        "created_at": _iso(conv.created_at),
    }


@router.get("/conversations")
async def list_conversations(
    limit: int = 20,
    tenant_code: Optional[str] = Header(None, alias="X-Tenant-Code"),
    employ_code: Optional[str] = Header(None, alias="X-Employ-Code"),
):
    tenant_id, user_key = _user_scope(tenant_code, employ_code)
    svc = get_conversation_service()
    conversations, total = await svc.list_conversations(
        tenant_id=tenant_id,
        user_key=user_key,
        limit=limit,
    )
    return {
        "conversations": [
            {
                "id": c.id,
                "title": c.title,
                "message_count": c.message_count,
                "created_at": _iso(c.created_at),
                "updated_at": _iso(c.updated_at),
            }
            for c in conversations
        ],
        "total": total,
    }


@router.get("/conversations/{conversation_id}/messages")
async def get_messages(
    conversation_id: int,
    limit: int = 50,
    tenant_code: Optional[str] = Header(None, alias="X-Tenant-Code"),
    employ_code: Optional[str] = Header(None, alias="X-Employ-Code"),
):
    tenant_id, user_key = _user_scope(tenant_code, employ_code)
    svc = get_conversation_service()
    conv = await svc.get_conversation(conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    if conv.tenant_id != tenant_id or conv.user_key != user_key:
        raise HTTPException(status_code=403, detail="无权访问该会话")

    messages = await svc.get_messages(conversation_id, limit=limit)
    return {
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "pinned": m.pinned,
                "created_at": _iso(m.created_at),
            }
            for m in messages
        ]
    }
