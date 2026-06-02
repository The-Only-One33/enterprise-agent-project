"""固定 Planner 步骤：周报主路径。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class PlanStep:
    id: str
    name: str
    description: str = ""


WEEKLY_PLAN_STEPS: List[PlanStep] = [
    PlanStep("rag_guide", "检索周报撰写规范", "从知识库拉取模板与 6 章结构"),
    PlanStep("query_data", "查询本周任务与执行内容", "按自然周过滤任务/执行分工"),
    PlanStep("generate", "生成周报正文", "结合规范与业务数据由 LLM 撰写"),
    PlanStep("export", "导出 Markdown 文件", "写入 exports 目录供下载"),
]


def build_weekly_plan(entities: Dict[str, Any] | None = None) -> List[Dict[str, str]]:
    """返回可序列化的计划步骤列表。"""
    _ = entities
    return [
        {"id": s.id, "name": s.name, "description": s.description}
        for s in WEEKLY_PLAN_STEPS
    ]


def step_index(step_id: str) -> int:
    for i, s in enumerate(WEEKLY_PLAN_STEPS):
        if s.id == step_id:
            return i
    return 0
