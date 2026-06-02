"""
意图槽位配置：路由到 DB/CREATE/UPDATE/GRAPH 前校验必填参数。

slot_groups：每组至少填一个（OR），例如 task_id | task_title。
required_slots：全部必填（AND）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.services.intent.base import IntentType, RoutingTarget


@dataclass(frozen=True)
class IntentSlotConfig:
    required_slots: List[str] = field(default_factory=list)
    slot_groups: List[List[str]] = field(default_factory=list)
    slot_prompts: Dict[str, str] = field(default_factory=dict)
    skip: bool = False


DEFAULT_SLOT_PROMPTS: Dict[str, str] = {
    "task_title": "请问任务标题是什么？",
    "task_id": "请问要操作哪个任务？可以提供任务 ID 或任务名称。",
    "task_status": "请问要筛选哪种任务状态？",
    "project_name": "请问是哪个项目？",
    "project_id": "请问项目 ID 或项目名称是什么？",
    "execution_id": "请问是哪个执行分工？",
    "execution_title": "请问执行分工的标题是什么？",
    "score_value": "请问评分是多少？",
    "employee_id": "请问是哪位员工？",
    "person_name": "请问员工姓名或工号是什么？",
    "evaluation_content": "请问评价内容是什么？",
}


def _cfg(
    *,
    required: Optional[List[str]] = None,
    groups: Optional[List[List[str]]] = None,
    prompts: Optional[Dict[str, str]] = None,
    skip: bool = False,
) -> IntentSlotConfig:
    return IntentSlotConfig(
        required_slots=required or [],
        slot_groups=groups or [],
        slot_prompts=prompts or {},
        skip=skip,
    )


# 按 IntentType 配置（列表查询类通常无必填槽）
INTENT_SLOT_CONFIG: Dict[str, IntentSlotConfig] = {
    # ----- 任务 -----
    IntentType.CREATE_TASK.value: _cfg(
        required=["task_title"],
        prompts={"task_title": "请问要创建的任务标题是什么？"},
    ),
    IntentType.QUERY_TASK_DETAIL.value: _cfg(
        groups=[["task_id", "task_title"]],
        prompts={"task_id": "请问要查看哪个任务？请提供任务名称或 ID。"},
    ),
    IntentType.QUERY_TASK_PROGRESS.value: _cfg(
        groups=[["task_id", "task_title"]],
    ),
    IntentType.QUERY_TASK_MEMBERS.value: _cfg(
        groups=[["task_id", "task_title"]],
    ),
    IntentType.UPDATE_TASK.value: _cfg(
        groups=[["task_id", "task_title"]],
        prompts={"task_id": "请问要更新哪个任务？请提供任务名称或 ID。"},
    ),
    IntentType.DELETE_TASK.value: _cfg(
        groups=[["task_id", "task_title"]],
        prompts={"task_id": "请问要删除哪个任务？请提供任务名称或 ID。"},
    ),
    IntentType.COMPLETE_TASK.value: _cfg(
        groups=[["task_id", "task_title"]],
        prompts={"task_id": "请问要完成哪个任务？请提供任务名称或 ID。"},
    ),
    # 列表/我的任务：无必填
    IntentType.QUERY_TASK_LIST.value: _cfg(skip=True),
    IntentType.QUERY_MY_TASKS.value: _cfg(skip=True),
    IntentType.QUERY_ALL_TASKS.value: _cfg(skip=True),
    IntentType.QUERY_TASK_STATUS.value: _cfg(skip=True),
    # ----- 项目 -----
    IntentType.CREATE_PROJECT.value: _cfg(
        required=["project_name"],
        prompts={"project_name": "请问新项目的名称是什么？"},
    ),
    IntentType.QUERY_PROJECT_DETAIL.value: _cfg(
        groups=[["project_id", "project_name"]],
        prompts={"project_id": "请问要查看哪个项目？请提供项目名称或 ID。"},
    ),
    IntentType.QUERY_PROJECT_TASKS.value: _cfg(
        groups=[["project_id", "project_name"]],
        prompts={"project_id": "请问要查询哪个项目下的任务？"},
    ),
    IntentType.QUERY_PROJECT_MEMBERS.value: _cfg(
        groups=[["project_id", "project_name"]],
    ),
    IntentType.QUERY_PROJECT_SCORES.value: _cfg(
        groups=[["project_id", "project_name"]],
    ),
    IntentType.UPDATE_PROJECT.value: _cfg(
        groups=[["project_id", "project_name"]],
    ),
    IntentType.QUERY_PROJECT_LIST.value: _cfg(skip=True),
    # ----- 执行分工 -----
    IntentType.CREATE_EXECUTION.value: _cfg(
        required=["execution_title"],
        prompts={"execution_title": "请问执行分工的标题是什么？"},
    ),
    IntentType.QUERY_EXECUTION_DETAIL.value: _cfg(
        groups=[["execution_id", "execution_title"]],
    ),
    IntentType.UPDATE_EXECUTION.value: _cfg(
        groups=[["execution_id", "execution_title"]],
    ),
    IntentType.DELETE_EXECUTION.value: _cfg(
        groups=[["execution_id", "execution_title"]],
    ),
    IntentType.COMPLETE_EXECUTION.value: _cfg(
        groups=[["execution_id", "execution_title"]],
    ),
    IntentType.QUERY_EXECUTION_LIST.value: _cfg(skip=True),
    IntentType.CREATE_EXECUTION_SCORE.value: _cfg(
        groups=[["execution_id", "execution_title"]],
        required=["score_value"],
        prompts={"score_value": "请问要打多少分？"},
    ),
    # ----- 图谱 -----
    IntentType.GRAPH_TRAVERSE.value: _cfg(
        groups=[["employee_id", "person_name"]],
        prompts={"person_name": "请问要查询哪位员工的关联关系？"},
    ),
    # ----- RAG / 闲聊：不校验 -----
    IntentType.RAG_SEMANTIC.value: _cfg(skip=True),
    IntentType.RAG_SIMILAR.value: _cfg(skip=True),
    IntentType.GENERAL_CHAT.value: _cfg(skip=True),
    IntentType.WEEKLY_SUMMARY.value: _cfg(skip=True),
}


# 无专门配置时，按路由决定是否校验
ROUTE_REQUIRES_SLOT_CHECK = frozenset({
    RoutingTarget.DB.value,
    RoutingTarget.CREATE.value,
    RoutingTarget.UPDATE.value,
    RoutingTarget.GRAPH.value,
})


def get_slot_config(intent: str) -> IntentSlotConfig:
    return INTENT_SLOT_CONFIG.get(intent, IntentSlotConfig())


def should_validate_slots(intent: str, routing_target: str) -> bool:
    cfg = get_slot_config(intent)
    if cfg.skip:
        return False
    if cfg.required_slots or cfg.slot_groups:
        return True
    return routing_target in ROUTE_REQUIRES_SLOT_CHECK
