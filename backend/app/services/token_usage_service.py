"""将 Agent / 意图链路 LLM 用量持久化到 MySQL"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.config import get_settings
from app.services.cost_monitor import get_cost_monitor


def _user_context_from_state(state: Dict[str, Any]) -> Dict[str, Any]:
    return state.get("user_context") or {}


async def persist_intent_llm_usages(
    state: Dict[str, Any],
    llm_usages: List[Dict[str, Any]],
    *,
    recognized_intent: Optional[str] = None,
) -> None:
    """意图识别阶段的 entity / intent LLM 调用各记一笔。"""
    if not llm_usages:
        return

    user_context = _user_context_from_state(state)
    conversation_id = user_context.get("conversation_id")
    monitor = await get_cost_monitor()

    for item in llm_usages:
        input_tokens = int(item.get("input_tokens") or 0)
        output_tokens = int(item.get("output_tokens") or 0)
        if input_tokens <= 0 and output_tokens <= 0:
            continue
        await monitor.record_usage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=str(item.get("model") or get_settings().openai_model),
            tenant_id=user_context.get("tenant_id"),
            user_key=user_context.get("employ_code"),
            conversation_id=conversation_id,
            intent=recognized_intent,
            stage=str(item.get("stage") or "intent_recognition"),
        )


async def persist_token_usage_from_state(
    state: Dict[str, Any],
    *,
    conversation_id: Optional[int] = None,
) -> None:
    """主回答 LLM（流式/非流式）完成后记一笔 stage=answer。"""
    usage = state.get("token_usage") or {}
    input_tokens = int(usage.get("input_tokens") or 0)
    output_tokens = int(usage.get("output_tokens") or 0)
    if input_tokens <= 0 and output_tokens <= 0:
        return

    settings = get_settings()
    user_context = _user_context_from_state(state)
    conv_id = conversation_id if conversation_id is not None else user_context.get("conversation_id")

    monitor = await get_cost_monitor()
    await monitor.record_usage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        model=str(usage.get("model") or settings.openai_model),
        tenant_id=user_context.get("tenant_id"),
        user_key=user_context.get("employ_code"),
        conversation_id=conv_id,
        intent=state.get("intent") or None,
        stage="answer",
    )
    state["token_usage"] = {}
