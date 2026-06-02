"""澄清 pending 存储后端：Redis（P3）+ 内存回退。"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.core.logging import get_logger
from app.services.clarification_state import (
    build_clarification_snapshot,
    clarification_redis_key,
)

logger = get_logger(__name__)


class ClarificationStoreBackend(ABC):
    @abstractmethod
    def save(self, conversation_id: int, state: Dict[str, Any]) -> None:
        ...

    @abstractmethod
    def get(self, conversation_id: int) -> Optional[Dict[str, Any]]:
        ...

    @abstractmethod
    def delete(self, conversation_id: int) -> None:
        ...

    @property
    @abstractmethod
    def backend_name(self) -> str:
        ...


class MemoryClarificationBackend(ClarificationStoreBackend):
    def __init__(self) -> None:
        self._states: Dict[int, Dict[str, Any]] = {}
        self._saved_at: Dict[int, datetime] = {}

    @property
    def backend_name(self) -> str:
        return "memory"

    def save(self, conversation_id: int, state: Dict[str, Any]) -> None:
        self._states[conversation_id] = build_clarification_snapshot(state)
        self._saved_at[conversation_id] = datetime.now(timezone.utc)

    def get(self, conversation_id: int) -> Optional[Dict[str, Any]]:
        return self._states.get(conversation_id)

    def delete(self, conversation_id: int) -> None:
        self._states.pop(conversation_id, None)
        self._saved_at.pop(conversation_id, None)


class RedisClarificationBackend(ClarificationStoreBackend):
    def __init__(self, redis_client: Any, *, ttl_seconds: int) -> None:
        self._redis = redis_client
        self._ttl = ttl_seconds

    @property
    def backend_name(self) -> str:
        return "redis"

    def save(self, conversation_id: int, state: Dict[str, Any]) -> None:
        payload = build_clarification_snapshot(state)
        payload["_saved_at"] = datetime.now(timezone.utc).isoformat()
        key = clarification_redis_key(conversation_id)
        self._redis.setex(key, self._ttl, json.dumps(payload, ensure_ascii=False))

    def get(self, conversation_id: int) -> Optional[Dict[str, Any]]:
        raw = self._redis.get(clarification_redis_key(conversation_id))
        if not raw:
            return None
        data = json.loads(raw)
        data.pop("_saved_at", None)
        return data

    def delete(self, conversation_id: int) -> None:
        self._redis.delete(clarification_redis_key(conversation_id))


def create_clarification_backend() -> ClarificationStoreBackend:
    from app.config import get_settings

    settings = get_settings()
    backend_pref = (settings.clarification_state_backend or "auto").lower().strip()

    if backend_pref == "memory":
        logger.info("clarification_store_backend", backend="memory", reason="configured")
        return MemoryClarificationBackend()

    if backend_pref == "redis" and not settings.redis_url:
        logger.warning(
            "clarification_store_redis_url_missing",
            fallback="memory",
        )
        return MemoryClarificationBackend()

    if settings.redis_url and backend_pref in ("redis", "auto"):
        try:
            import redis

            client = redis.Redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=settings.redis_connect_timeout_seconds,
            )
            client.ping()
            logger.info(
                "clarification_store_backend",
                backend="redis",
                ttl_seconds=settings.clarification_state_ttl_seconds,
            )
            return RedisClarificationBackend(
                client,
                ttl_seconds=settings.clarification_state_ttl_seconds,
            )
        except Exception as exc:
            logger.warning(
                "clarification_store_redis_unavailable",
                error=str(exc),
                fallback="memory",
            )

    logger.info("clarification_store_backend", backend="memory", reason="default")
    return MemoryClarificationBackend()


_backend: Optional[ClarificationStoreBackend] = None


def get_clarification_backend() -> ClarificationStoreBackend:
    global _backend
    if _backend is None:
        _backend = create_clarification_backend()
    return _backend


def reset_clarification_backend() -> None:
    """测试或热重载时重置后端单例。"""
    global _backend
    _backend = None


def close_clarification_backend() -> None:
    """应用关闭时释放 Redis 连接。"""
    global _backend
    if _backend is None:
        return
    if isinstance(_backend, RedisClarificationBackend):
        try:
            _backend._redis.close()
        except Exception:
            pass
    _backend = None
