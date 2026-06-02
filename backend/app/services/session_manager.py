"""
会话状态管理服务（P3）

- 澄清 pending：Redis 持久化（多实例共享），无 Redis 时回退内存
- 对话历史：MySQL（conversation_service）
"""
from typing import Any, Dict, Optional

from app.services.clarification_store import (
    ClarificationStoreBackend,
    get_clarification_backend,
)


class SessionState:
    """澄清 pending 状态；底层由 Redis 或内存实现。"""

    def __init__(self, backend: Optional[ClarificationStoreBackend] = None) -> None:
        self._backend = backend or get_clarification_backend()

    @property
    def backend_name(self) -> str:
        return self._backend.backend_name

    def save_state(self, conversation_id: int, state: Dict[str, Any]) -> None:
        self._backend.save(conversation_id, state)

    def get_state(self, conversation_id: int) -> Optional[Dict[str, Any]]:
        return self._backend.get(conversation_id)

    def clear_state(self, conversation_id: int) -> None:
        self._backend.delete(conversation_id)

    def has_pending_clarification(self, conversation_id: int) -> bool:
        state = self.get_state(conversation_id)
        return state is not None and state.get("needs_clarification", False) is True

    def get_clarification_type(self, conversation_id: int) -> Optional[str]:
        state = self.get_state(conversation_id)
        if not state or not state.get("needs_clarification"):
            return None
        return state.get("clarification_type") or "intent"

    def clear_clarification_pending(self, conversation_id: int) -> None:
        """用户已回复澄清：清除 pending 标记，对话历史在 MySQL 中保留。"""
        self.clear_state(conversation_id)


_session_state: Optional[SessionState] = None


def get_session_state() -> SessionState:
    global _session_state
    if _session_state is None:
        _session_state = SessionState()
    return _session_state


def reset_session_state() -> None:
    """测试时重置 SessionState 单例（会重新选择 Redis/内存后端）。"""
    global _session_state
    from app.services.clarification_store import reset_clarification_backend

    _session_state = None
    reset_clarification_backend()
