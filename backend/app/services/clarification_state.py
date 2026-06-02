"""澄清 pending 快照：序列化字段与 Redis key。"""
from __future__ import annotations

from typing import Any, Dict

CLARIFICATION_KEY_PREFIX = "ea:clarification:"


def clarification_redis_key(conversation_id: int) -> str:
    return f"{CLARIFICATION_KEY_PREFIX}{conversation_id}"


def build_clarification_snapshot(state: Dict[str, Any]) -> Dict[str, Any]:
    """从 Agent 图 state 提取可 JSON 持久化的澄清快照。"""
    routing = state.get("routing_target")
    if hasattr(routing, "value"):
        routing = routing.value

    return {
        "intent": state.get("intent"),
        "confidence": state.get("confidence"),
        "entities": state.get("entities") or {},
        "routing_target": routing,
        "needs_clarification": bool(state.get("needs_clarification", False)),
        "clarification_question": state.get("clarification_question"),
        "clarification_type": state.get("clarification_type") or "intent",
        "missing_slots": state.get("missing_slots") or [],
        "reasoning_steps": state.get("reasoning_steps") or [],
        "resolved_query": state.get("resolved_query") or "",
        "plan_steps": state.get("plan_steps") or [],
        "plan_current_step": state.get("plan_current_step") or 0,
        "plan_observations": state.get("plan_observations") or {},
        "rag_results": state.get("rag_results") or [],
    }
