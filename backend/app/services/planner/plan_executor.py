"""执行周报 Planner 步骤（RAG + DB + ReAct），生成阶段交给 LLM 节点。"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.services.planner.react_fallback import ReactDecision, evaluate_weekly_observations
from app.services.planner.task_planner import build_weekly_plan, step_index
from app.services.planner.weekly_report import resolve_week_range

logger = logging.getLogger(__name__)


async def _run_rag_guide(state: Dict[str, Any]) -> None:
    from app.services.rag_service import get_rag_service

    rag = get_rag_service()
    user_context = state.get("user_context") or {}
    tenant_id = user_context.get("tenant_id", "TENANT_DEFAULT")
    results = await rag.similarity_search(
        query="周报撰写规范 六章节 执行内容明细 模板",
        tenant_id=tenant_id,
        resolved_query="员工周报撰写规范与模板",
    )
    state["rag_results"] = results
    obs = state.setdefault("plan_observations", {})
    obs["rag_count"] = len([r for r in results if r.get("type") != "optimization_info"])


async def _run_query_data(state: Dict[str, Any]) -> ReactDecision:
    from app.services.business_service_proxy import get_business_service_proxy

    entities = state.get("entities") or {}
    week_start, week_end = resolve_week_range(entities)
    entities = {**entities, "week_start": week_start, "week_end": week_end}
    state["entities"] = entities

    proxy = get_business_service_proxy()
    result = await proxy.execute(
        "weekly_summary",
        entities,
        state.get("user_context") or {},
        routing_target="planner",
    )
    state["db_results"] = result
    weekly = (result.get("data") or {}) if result.get("success") else {}
    obs = state.setdefault("plan_observations", {})
    obs["weekly_data"] = weekly
    obs["week_start"] = week_start
    obs["week_end"] = week_end

    return evaluate_weekly_observations(obs, entities)


def _apply_clarification(state: Dict[str, Any], decision: ReactDecision) -> None:
    state["needs_clarification"] = True
    state["clarification_type"] = "plan"
    state["clarification_question"] = decision.question
    state["plan_current_step"] = step_index("query_data")
    state["reasoning_steps"].append({
        "step": "react_fallback",
        "thought": f"ReAct 观测异常: {decision.reason}",
        "action": decision.question[:120],
    })


async def execute_weekly_plan(state: Dict[str, Any], *, from_step: str = "rag_guide") -> None:
    """
    执行非 LLM 步骤。完成后设置 weekly_report_mode，由 llm_reasoning 生成正文；
    export 在 llm 节点或 API 层完成。
    """
    if not state.get("plan_steps"):
        state["plan_steps"] = build_weekly_plan(state.get("entities"))

    start_idx = step_index(from_step)
    steps = [s["id"] for s in state["plan_steps"]]

    for step_id in steps[start_idx:]:
        state["plan_current_step"] = step_index(step_id)

        if step_id == "rag_guide":
            await _run_rag_guide(state)
            state["reasoning_steps"].append({
                "step": "plan_rag_guide",
                "thought": "Planner: 检索周报撰写规范",
                "action": f"命中 {state.get('plan_observations', {}).get('rag_count', 0)} 条",
            })

        elif step_id == "query_data":
            decision = await _run_query_data(state)
            if decision.action == "clarify":
                _apply_clarification(state, decision)
                return
            if decision.reason == "empty_executions_partial":
                state["reasoning_steps"].append({
                    "step": "react_fallback",
                    "thought": "执行内容为空，按规范写推进说明（继续生成）",
                    "action": "partial_data",
                })
            else:
                state["reasoning_steps"].append({
                    "step": "plan_query_data",
                    "thought": "Planner: 查询本周任务与执行内容",
                    "action": f"任务 {state['plan_observations'].get('weekly_data', {}).get('task_count', 0)} 条",
                })

        elif step_id == "generate":
            state["weekly_report_mode"] = True
            state["reasoning_steps"].append({
                "step": "plan_generate",
                "thought": "Planner: 上下文就绪，交由 LLM 生成周报",
                "action": "weekly_report_mode=True",
            })
            return

        elif step_id == "export":
            # export 在 LLM 完成后执行
            state["weekly_export_pending"] = True
            return

    state["weekly_report_mode"] = True
