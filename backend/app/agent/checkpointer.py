"""LangGraph Checkpointer（P4）：Redis 优先，内存回退。"""
from __future__ import annotations

from typing import Any, Dict, Optional

from app.core.logging import get_logger

logger = get_logger(__name__)

_checkpointer: Any = None
_backend_name: str = "memory"


def graph_thread_config(conversation_id: int) -> Dict[str, Any]:
    return {"configurable": {"thread_id": f"conv_{conversation_id}"}}


async def init_checkpointer() -> Any:
    """应用启动时初始化 checkpointer（Redis 需 asetup）。"""
    global _checkpointer, _backend_name
    if _checkpointer is not None:
        return _checkpointer

    from app.config import get_settings

    settings = get_settings()
    pref = (settings.graph_checkpoint_backend or "auto").lower().strip()

    if pref == "memory":
        _checkpointer = _create_memory_saver()
        _backend_name = "memory"
        logger.info("graph_checkpointer_ready", backend=_backend_name)
        return _checkpointer

    if pref == "redis" and not settings.redis_url:
        logger.warning("graph_checkpoint_redis_url_missing", fallback="memory")
        _checkpointer = _create_memory_saver()
        _backend_name = "memory"
        return _checkpointer

    if settings.redis_url and pref in ("redis", "auto"):
        saver = await _try_create_redis_saver(settings.redis_url)
        if saver is not None:
            _checkpointer = saver
            _backend_name = "redis"
            logger.info("graph_checkpointer_ready", backend=_backend_name)
            return _checkpointer
        logger.warning("graph_checkpoint_redis_unavailable", fallback="memory")

    _checkpointer = _create_memory_saver()
    _backend_name = "memory"
    logger.info("graph_checkpointer_ready", backend=_backend_name)
    return _checkpointer


def ensure_checkpointer() -> Any:
    """懒初始化（测试或未走 lifespan 时）。"""
    global _checkpointer, _backend_name
    if _checkpointer is not None:
        return _checkpointer
    _checkpointer = _create_memory_saver()
    _backend_name = "memory"
    return _checkpointer


def get_checkpointer() -> Any:
    if _checkpointer is None:
        return ensure_checkpointer()
    return _checkpointer


def get_checkpoint_backend_name() -> str:
    return _backend_name


async def close_checkpointer() -> None:
    global _checkpointer, _backend_name
    if _checkpointer is None:
        return
    try:
        aclose = getattr(_checkpointer, "aclose", None)
        if callable(aclose):
            await aclose()
        close = getattr(_checkpointer, "close", None)
        if callable(close):
            close()
    except Exception as exc:
        logger.warning("graph_checkpointer_close_failed", error=str(exc))
    _checkpointer = None
    _backend_name = "memory"


def _create_memory_saver():
    from langgraph.checkpoint.memory import InMemorySaver

    return InMemorySaver()


async def _try_create_redis_saver(redis_url: str) -> Optional[Any]:
    try:
        from langgraph.checkpoint.redis.aio import AsyncRedisSaver
    except ImportError:
        logger.warning(
            "langgraph_checkpoint_redis_not_installed",
            hint="pip install langgraph-checkpoint-redis",
        )
        return None

    try:
        saver = AsyncRedisSaver.from_conn_string(redis_url)
        await saver.asetup()
        return saver
    except Exception as exc:
        logger.warning("graph_checkpoint_redis_init_failed", error=str(exc))
        return None
