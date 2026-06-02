"""
槽位校验：合并实体、检测缺失、生成追问文案。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from app.services.intent.slot_registry import (
    DEFAULT_SLOT_PROMPTS,
    IntentSlotConfig,
    get_slot_config,
    should_validate_slots,
)

# 实体字段别名 → 规范槽位名
ENTITY_ALIASES: Dict[str, str] = {
    "title": "task_title",
    "task_name": "task_title",
    "task_id_value": "task_id",
    "project": "project_name",
    "project_id_value": "project_id",
    "employee": "person_name",
    "user_name": "person_name",
    "assignee": "person_name",
    "execution_name": "execution_title",
    "subtask_title": "execution_title",
    "score": "score_value",
}


def _is_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def normalize_entities(entities: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """别名归一 + 去掉空值。"""
    if not entities:
        return {}
    normalized: Dict[str, Any] = {}
    for key, value in entities.items():
        if not _is_present(value):
            continue
        slot = ENTITY_ALIASES.get(key, key)
        normalized[slot] = value
    return normalized


def merge_entities(
    base: Optional[Dict[str, Any]],
    incoming: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    merged = normalize_entities(base)
    for key, value in normalize_entities(incoming).items():
        merged[key] = value
    return merged


def _group_missing(group: List[str], entities: Dict[str, Any]) -> bool:
    """组内是否至少有一个槽位已填。"""
    return any(_is_present(entities.get(slot)) for slot in group)


def find_missing_slots(
    intent: str,
    entities: Dict[str, Any],
    *,
    config: Optional[IntentSlotConfig] = None,
) -> List[str]:
    """
    返回仍缺失的槽位名（用于生成追问）。
    slot_groups 中整组缺失时，返回该组第一个槽位作为代表。
    """
    cfg = config or get_slot_config(intent)
    normalized = normalize_entities(entities)
    missing: List[str] = []

    for slot in cfg.required_slots:
        if not _is_present(normalized.get(slot)):
            missing.append(slot)

    for group in cfg.slot_groups:
        if not _group_missing(group, normalized):
            missing.append(group[0])

    return missing


def build_slot_clarification_question(
    intent: str,
    missing_slots: List[str],
    *,
    config: Optional[IntentSlotConfig] = None,
) -> str:
    if not missing_slots:
        return "请补充必要的信息。"

    cfg = config or get_slot_config(intent)
    prompts = {**DEFAULT_SLOT_PROMPTS, **cfg.slot_prompts}

    if len(missing_slots) == 1:
        return prompts.get(
            missing_slots[0],
            f"请提供「{missing_slots[0]}」相关信息。",
        )

    parts = [prompts.get(s, s) for s in missing_slots[:3]]
    return " ".join(parts)


def validate_slots(
    intent: str,
    routing_target: str,
    entities: Dict[str, Any],
) -> Tuple[bool, List[str], str]:
    """
    校验槽位是否满足。
    返回 (passed, missing_slots, clarification_question)。
    """
    rt = (
        routing_target.value
        if hasattr(routing_target, "value")
        else str(routing_target or "")
    )
    if not should_validate_slots(intent, rt):
        return True, [], ""

    missing = find_missing_slots(intent, entities)
    if not missing:
        return True, [], ""

    question = build_slot_clarification_question(intent, missing)
    return False, missing, question


def build_missing_params_result(
    intent: str,
    missing_slots: List[str],
    clarification_question: str,
) -> Dict[str, Any]:
    """业务层二次校验：缺参时统一返回结构（不伪造成功）。"""
    return {
        "success": False,
        "error": "missing_params",
        "needs_clarification": True,
        "clarification_type": "slot",
        "missing_fields": missing_slots,
        "intent": intent,
        "message": clarification_question,
        "service": "validation",
        "operation": "slot_check",
    }


def apply_clarification_to_state(
    state: Dict[str, Any],
    *,
    missing_slots: List[str],
    clarification_question: str,
    source_step: str,
) -> None:
    """将缺参结果写入 AgentState，触发 clarification 路由。"""
    state["needs_clarification"] = True
    state["clarification_type"] = "slot"
    state["missing_slots"] = missing_slots
    state["clarification_question"] = clarification_question
    state.setdefault("reasoning_steps", []).append({
        "step": source_step,
        "thought": f"服务端校验缺少参数: {missing_slots}",
        "action": clarification_question[:120],
    })


def result_needs_clarification(result: Optional[Dict[str, Any]]) -> bool:
    if not result:
        return False
    return bool(
        result.get("needs_clarification")
        or result.get("error") == "missing_params"
    )


def clarification_from_service_result(
    result: Dict[str, Any],
) -> tuple[List[str], str]:
    missing = list(result.get("missing_fields") or result.get("missing_slots") or [])
    question = str(
        result.get("message")
        or result.get("clarification_question")
        or "请补充必要的信息。"
    )
    return missing, question


def apply_slot_fill_fallback(
    entities: Dict[str, Any],
    missing_slots: List[str],
    user_text: str,
) -> Dict[str, Any]:
    """用户短句直接当作唯一缺失槽位的值（如只回复「项目A」）。"""
    merged = dict(entities)
    text = user_text.strip()
    if len(missing_slots) == 1 and text and not _is_present(merged.get(missing_slots[0])):
        merged[missing_slots[0]] = text
    return merged
