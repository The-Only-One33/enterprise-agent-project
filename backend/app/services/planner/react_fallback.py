"""ReAct 兜底：观测异常时追问或调整策略。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class ReactDecision:
    action: str  # continue | clarify | widen_range
    question: str = ""
    reason: str = ""
    patch_entities: Dict[str, Any] | None = None


def _project_names(data: Dict[str, Any]) -> List[str]:
    projects = data.get("projects") or []
    names: List[str] = []
    for p in projects:
        if isinstance(p, dict):
            names.append(str(p.get("name") or p.get("project_name") or ""))
        else:
            names.append(str(p))
    return [n for n in names if n]


def evaluate_weekly_observations(
    observations: Dict[str, Any],
    entities: Dict[str, Any],
) -> ReactDecision:
    """
    根据 query_data 步骤观测决定是否继续、追问或放宽范围。

    触发条件（对齐 RAG 指南 §4）：
    - 0 任务 → 追问是否扩大时间范围
    - 多项目且未指定 scope → 追问单项目 / 全部总周报
    - 无执行内容 → 继续但标记 partial（LLM 按规范写推进说明）
    """
    weekly = observations.get("weekly_data") or {}
    task_count = int(weekly.get("task_count") or 0)
    execution_count = int(weekly.get("execution_count") or 0)
    projects = _project_names(weekly)

    scope = entities.get("report_scope") or entities.get("project_name")

    if task_count == 0 and not entities.get("widen_range"):
        return ReactDecision(
            action="clarify",
            question=(
                "本周暂无任务记录。是否扩大时间范围到「上周」或「近两周」？"
                "请回复：上周 / 近两周 / 取消"
            ),
            reason="zero_tasks",
        )

    if len(projects) >= 2 and not scope:
        proj_list = "、".join(projects[:5])
        return ReactDecision(
            action="clarify",
            question=(
                f"检测到您同时参与多个项目（{proj_list}）。"
                "请选择周报范围：回复「单项目：项目名」或「全部项目总周报」。"
            ),
            reason="multi_project",
        )

    if execution_count == 0 and task_count > 0:
        return ReactDecision(
            action="continue",
            reason="empty_executions_partial",
        )

    return ReactDecision(action="continue", reason="ok")
