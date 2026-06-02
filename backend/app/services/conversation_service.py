"""对话与消息 MySQL 持久化"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select, update

from app.core.database import AsyncSessionLocal
from app.core.logging import get_logger
from app.models.conversation import Conversation, Message

logger = get_logger(__name__)

DEFAULT_TITLE = "新对话"
TITLE_MAX_LEN = 48


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _title_from_message(content: str) -> str:
    text = content.strip().replace("\n", " ")
    if not text:
        return DEFAULT_TITLE
    return text[:TITLE_MAX_LEN] + ("…" if len(text) > TITLE_MAX_LEN else "")


class ConversationService:
    async def create_conversation(
        self,
        *,
        tenant_id: str,
        user_key: str,
        title: Optional[str] = None,
    ) -> Conversation:
        async with AsyncSessionLocal() as session:
            conv = Conversation(
                tenant_id=tenant_id,
                user_key=user_key,
                title=(title or DEFAULT_TITLE).strip() or DEFAULT_TITLE,
            )
            session.add(conv)
            await session.commit()
            await session.refresh(conv)
            logger.info(
                "conversation_created",
                conversation_id=conv.id,
                tenant_id=tenant_id,
                user_key=user_key,
            )
            return conv

    async def get_conversation(self, conversation_id: int) -> Optional[Conversation]:
        async with AsyncSessionLocal() as session:
            return await session.get(Conversation, conversation_id)

    async def ensure_conversation(
        self,
        conversation_id: Optional[int],
        *,
        tenant_id: str,
        user_key: str,
        title: Optional[str] = None,
    ) -> int:
        if conversation_id:
            conv = await self.get_conversation(conversation_id)
            if conv is not None:
                return conv.id
            logger.warning(
                "conversation_not_found_creating_new",
                conversation_id=conversation_id,
            )
        conv = await self.create_conversation(
            tenant_id=tenant_id,
            user_key=user_key,
            title=title,
        )
        return conv.id

    async def list_conversations(
        self,
        *,
        tenant_id: str,
        user_key: str,
        limit: int = 20,
    ) -> tuple[List[Conversation], int]:
        async with AsyncSessionLocal() as session:
            base = select(Conversation).where(
                Conversation.tenant_id == tenant_id,
                Conversation.user_key == user_key,
            )
            total = await session.scalar(
                select(func.count(Conversation.id)).where(
                    Conversation.tenant_id == tenant_id,
                    Conversation.user_key == user_key,
                )
            )
            rows = await session.scalars(
                base.order_by(Conversation.updated_at.desc()).limit(limit)
            )
            return list(rows.all()), int(total or 0)

    async def get_messages(
        self,
        conversation_id: int,
        *,
        limit: int = 50,
    ) -> List[Message]:
        async with AsyncSessionLocal() as session:
            rows = await session.scalars(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.id.desc())
                .limit(limit)
            )
            items = list(rows.all())
            items.reverse()
            return items

    async def get_history(
        self,
        conversation_id: int,
        *,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        messages = await self.get_messages(conversation_id, limit=limit)
        history: List[Dict[str, Any]] = []
        for msg in messages:
            item: Dict[str, Any] = {"role": msg.role, "content": msg.content}
            if msg.pinned:
                item["pinned"] = True
            history.append(item)
        return history

    async def append_message(
        self,
        conversation_id: int,
        role: str,
        content: str,
        *,
        pinned: bool = False,
    ) -> Optional[Message]:
        text = str(content).strip()
        if not text:
            return None

        async with AsyncSessionLocal() as session:
            conv = await session.get(Conversation, conversation_id)
            if conv is None:
                logger.warning("append_message_missing_conversation", conversation_id=conversation_id)
                return None

            msg = Message(
                conversation_id=conversation_id,
                role=role,
                content=text,
                pinned=pinned,
            )
            session.add(msg)

            new_count = conv.message_count + 1
            new_title = conv.title
            if role == "user" and conv.title == DEFAULT_TITLE:
                new_title = _title_from_message(text)

            await session.execute(
                update(Conversation)
                .where(Conversation.id == conversation_id)
                .values(
                    message_count=new_count,
                    title=new_title,
                    updated_at=_utc_now(),
                )
            )
            await session.commit()
            await session.refresh(msg)
            return msg


_conversation_service: Optional[ConversationService] = None


def get_conversation_service() -> ConversationService:
    global _conversation_service
    if _conversation_service is None:
        _conversation_service = ConversationService()
    return _conversation_service
