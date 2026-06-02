"""Agent 图执行：新对话 invoke / 澄清 interrupt resume（P4）。"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Tuple

from langgraph.types import Command

from app.agent.checkpointer import graph_thread_config
from app.agent.graph import AgentState

RunOutcome = Literal["clarification", "agent", "ready"]


def _extract_interrupt_payload(result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    interrupts = result.get("__interrupt__")
    if not interrupts:
        return None
    first = interrupts[0]
    value = first.value if hasattr(first, "value") else first
    if isinstance(value, dict):
        return value
    return {"clarification_question": str(value), "clarification_type": "intent"}


async def _is_graph_interrupted(graph, config: Dict[str, Any]) -> bool:
    snapshot = await graph.aget_state(config)
    return bool(snapshot and snapshot.next)


async def invoke_agent_graph(
    graph,
    *,
    message: str,
    initial_state: AgentState,
    conversation_id: int,
) -> Tuple[RunOutcome, Dict[str, Any]]:
    """
    执行完整 Agent 图（非流式）。
    若处于 interrupt 暂停态则 Command(resume=message)，否则注入 initial_state。
    """
    config = graph_thread_config(conversation_id)
    interrupted = await _is_graph_interrupted(graph, config)

    if interrupted:
        result = await graph.ainvoke(Command(resume=message), config)
    else:
        await clear_graph_thread(graph, conversation_id)
        result = await graph.ainvoke(initial_state, config)

    interrupt_payload = _extract_interrupt_payload(result)
    if interrupt_payload is not None:
        snap = await graph.aget_state(config)
        values = dict(snap.values) if snap and snap.values else dict(result)
        return "clarification", _build_clarification_result(values, interrupt_payload, conversation_id)

    snap = await graph.aget_state(config)
    final = dict(snap.values) if snap and snap.values else dict(result)
    return "agent", final


async def invoke_prepare_graph(
    graph,
    *,
    message: str,
    initial_state: AgentState,
    conversation_id: int,
) -> Tuple[RunOutcome, Dict[str, Any]]:
    """
    执行预处理图（LLM 前 interrupt_before）。
    返回 clarification / ready(state) / agent（极少直接完成）。
    """
    config = graph_thread_config(conversation_id)
    interrupted = await _is_graph_interrupted(graph, config)

    if interrupted:
        result = await graph.ainvoke(Command(resume=message), config)
    else:
        await clear_graph_thread(graph, conversation_id)
        result = await graph.ainvoke(initial_state, config)

    interrupt_payload = _extract_interrupt_payload(result)
    if interrupt_payload is not None:
        snap = await graph.aget_state(config)
        values = dict(snap.values) if snap and snap.values else dict(result)
        return "clarification", _build_clarification_result(values, interrupt_payload, conversation_id)

    snap = await graph.aget_state(config)
    values = dict(snap.values) if snap and snap.values else dict(result)

    if snap and snap.next and "llm_reasoning" in snap.next:
        return "ready", values

    if values.get("needs_clarification"):
        return "clarification", _build_clarification_result(
            values,
            {
                "clarification_question": values.get("clarification_question"),
                "clarification_type": values.get("clarification_type") or "intent",
                "missing_slots": values.get("missing_slots") or [],
            },
            conversation_id,
        )

    return "agent", values


def _build_clarification_result(
    state: Dict[str, Any],
    interrupt_payload: Dict[str, Any],
    conversation_id: int,
) -> Dict[str, Any]:
    return {
        "type": "clarification",
        "clarification_question": interrupt_payload.get("clarification_question")
        or state.get("clarification_question")
        or "您具体想做什么？",
        "conversation_id": conversation_id,
        "reasoning_steps": state.get("reasoning_steps") or [],
        "clarification_type": interrupt_payload.get("clarification_type")
        or state.get("clarification_type")
        or "intent",
        "missing_slots": interrupt_payload.get("missing_slots")
        or state.get("missing_slots")
        or [],
    }


async def clear_graph_thread(graph, conversation_id: int) -> None:
    """清除会话的 LangGraph checkpoint（与澄清 pending 一并清理）。"""
    config = graph_thread_config(conversation_id)
    try:
        await graph.aupdate_state(config, values=None)
    except Exception:
        pass
