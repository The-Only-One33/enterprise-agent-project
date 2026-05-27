"""
会话状态管理服务
用于在澄清流程中保存和恢复 Agent 状态
"""
import json
from typing import Dict, Any, Optional
from datetime import datetime


class SessionState:
    """会话状态存储（内存版，生产环境建议用 Redis）"""

    def __init__(self):
        # conversation_id -> state dict
        self._states: Dict[int, Dict[str, Any]] = {}
        # conversation_id -> created_at
        self._timestamps: Dict[int, datetime] = {}

    def save_state(self, conversation_id: int, state: Dict[str, Any]) -> None:
        """保存会话状态"""
        # 只保存关键状态
        save_data = {
            "intent": state.get("intent"),
            "confidence": state.get("confidence"),
            "entities": state.get("entities", {}),
            "routing_target": state.get("routing_target"),
            "needs_clarification": state.get("needs_clarification", False),
            "clarification_question": state.get("clarification_question"),
            "reasoning_steps": state.get("reasoning_steps", []),
        }
        self._states[conversation_id] = save_data
        self._timestamps[conversation_id] = datetime.utcnow()

    def get_state(self, conversation_id: int) -> Optional[Dict[str, Any]]:
        """获取会话状态"""
        return self._states.get(conversation_id)

    def clear_state(self, conversation_id: int) -> None:
        """清除会话状态"""
        self._states.pop(conversation_id, None)
        self._timestamps.pop(conversation_id, None)

    def has_pending_clarification(self, conversation_id: int) -> bool:
        """检查是否有待处理的澄清"""
        state = self.get_state(conversation_id)
        return state is not None and state.get("needs_clarification", False) is True


# 全局单例
_session_state = SessionState()


def get_session_state() -> SessionState:
    """获取会话状态服务实例"""
    return _session_state


# ==================== 对话历史管理 ====================


def get_conversation_messages(conversation_id: int) -> list:
    """
    从数据库获取对话历史

    TODO: 实际实现时从数据库读取
    """
    # 暂时返回空列表，后续接入数据库
    return []


def append_message(conversation_id: int, role: str, content: str) -> None:
    """
    添加消息到对话历史

    TODO: 实际实现时写入数据库
    """
    pass


def save_message_with_context(
    conversation_id: int,
    role: str,
    content: str,
    intent: str = None,
    reasoning_steps: list = None,
    needs_clarification: bool = False,
    clarification_question: str = None,
) -> None:
    """
    保存消息及其上下文

    TODO: 实际实现时写入数据库
    """
    pass
