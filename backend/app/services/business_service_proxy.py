"""
业务服务代理
负责根据意图调用对应的业务微服务

P2：入口二次槽位校验；去掉 mock 默认值，缺参返回 missing_params。
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional

from app.services.slot_validation import (
    build_missing_params_result,
    normalize_entities,
    validate_slots,
)

logger = logging.getLogger(__name__)

# 意图 → handler 名（多意图共用同一 handler）
INTENT_HANDLER_ALIASES: Dict[str, str] = {
    "query_my_tasks": "query_task_list",
    "query_all_tasks": "query_task_list",
    "query_task_status": "query_task_list",
    "query_task_progress": "query_task_detail",
    "query_task_members": "query_task_detail",
    "query_project_detail": "query_project",
    "query_project_list": "query_project_list",
    "query_project_tasks": "query_project_tasks",
    "query_project_members": "query_project",
    "query_project_scores": "query_project",
    "query_execution_list": "query_execution_list",
    "query_execution_detail": "query_execution",
    "query_execution_score": "query_score",
    "query_score": "query_score",
    "query_employee": "query_employee",
    "graph_traverse": "query_employee",
    "weekly_summary": "query_weekly_work_summary",
}


def _infer_routing_target(intent: str) -> str:
    if intent.startswith("create_"):
        return "create"
    if any(
        intent.startswith(prefix)
        for prefix in ("update_", "delete_", "complete_")
    ):
        return "update"
    if intent == "graph_traverse":
        return "graph"
    return "db"


def _routing_str(routing_target: Optional[str], intent: str) -> str:
    if routing_target is None:
        return _infer_routing_target(intent)
    return (
        routing_target.value
        if hasattr(routing_target, "value")
        else str(routing_target)
    )


def _task_ref(entities: Dict[str, Any]) -> Optional[Any]:
    return entities.get("task_id") or entities.get("task_title")


def _project_ref(entities: Dict[str, Any]) -> Optional[Any]:
    return entities.get("project_id") or entities.get("project_name")


def _execution_ref(entities: Dict[str, Any]) -> Optional[Any]:
    return entities.get("execution_id") or entities.get("execution_title")


def _person_ref(entities: Dict[str, Any]) -> Optional[Any]:
    return entities.get("employee_id") or entities.get("person_name")


class BusinessServiceProxy:
    """业务服务代理：校验 → 路由 → 调用（或 mock）。"""

    def __init__(self):
        pass

    async def execute(
        self,
        intent: str,
        entities: Dict[str, Any],
        user_context: Optional[Dict[str, Any]] = None,
        *,
        routing_target: Optional[str] = None,
    ) -> Dict[str, Any]:
        user_context = user_context or {}
        tenant_id = user_context.get("tenant_id", "TENANT_DEFAULT")
        employ_code = user_context.get("employ_code", "E_DEFAULT")
        normalized = normalize_entities(entities)
        rt = _routing_str(routing_target, intent)

        passed, missing, question = validate_slots(intent, rt, normalized)
        if not passed:
            logger.info(
                "business_proxy_missing_params",
                extra={"intent": intent, "missing": missing, "tenant_id": tenant_id},
            )
            return build_missing_params_result(intent, missing, question)

        service_headers = {
            "X-Tenant-Code": tenant_id,
            "X-Employ-Code": employ_code,
        }

        handler_key = INTENT_HANDLER_ALIASES.get(intent, intent)
        handler = self._handlers().get(handler_key)
        if not handler:
            logger.warning(f"未找到意图处理器: {intent}", extra={"tenant_id": tenant_id})
            return {
                "success": False,
                "error": f"unsupported_intent",
                "message": f"暂不支持该业务意图: {intent}",
            }

        try:
            return await handler(normalized, user_context, service_headers)
        except Exception as e:
            logger.error(f"执行意图 {intent} 失败: {e}", extra={"tenant_id": tenant_id})
            return {"success": False, "error": str(e), "message": "业务执行失败"}

    def _handlers(self) -> Dict[str, Callable]:
        return {
            "create_task": self._create_task,
            "query_task_list": self._query_task_list,
            "query_task_detail": self._query_task_detail,
            "update_task": self._update_task,
            "complete_task": self._complete_task,
            "delete_task": self._delete_task,
            "create_execution_score": self._create_execution_score,
            "query_score": self._query_score,
            "update_execution_score": self._update_execution_score,
            "create_project": self._create_project,
            "query_project": self._query_project,
            "query_project_list": self._query_project_list,
            "query_project_tasks": self._query_project_tasks,
            "create_execution": self._create_execution,
            "query_execution": self._query_execution,
            "query_execution_list": self._query_execution_list,
            "update_execution": self._update_execution,
            "query_employee": self._query_employee,
            "query_weekly_work_summary": self._query_weekly_work_summary,
            "general_chat": self._general_chat,
        }

    # ----- 任务 -----

    async def _create_task(
        self, entities: Dict[str, Any], user_context: Dict[str, Any], headers: Dict[str, str]
    ) -> Dict[str, Any]:
        title = entities["task_title"]
        logger.info("创建任务", extra={"tenant_id": headers.get("X-Tenant-Code"), "title": title})
        return {
            "success": True,
            "service": "task",
            "operation": "create",
            "data": {
                "task_id": 12345,
                "title": title,
                "project_id": entities.get("project_id"),
                "status": "待处理",
            },
            "message": f"任务「{title}」创建成功",
        }

    async def _query_task_list(
        self, entities: Dict[str, Any], user_context: Dict[str, Any], headers: Dict[str, str]
    ) -> Dict[str, Any]:
        logger.info("查询任务列表", extra={"tenant_id": headers.get("X-Tenant-Code")})
        return {
            "success": True,
            "service": "task",
            "operation": "query_list",
            "data": {
                "total": 3,
                "tasks": [
                    {"id": 1, "title": "完成需求文档", "status": "进行中"},
                    {"id": 2, "title": "代码评审", "status": "待处理"},
                    {"id": 3, "title": "编写测试用例", "status": "已完成"},
                ],
            },
            "message": "查询到 3 条任务",
        }

    async def _query_task_detail(
        self, entities: Dict[str, Any], user_context: Dict[str, Any], headers: Dict[str, str]
    ) -> Dict[str, Any]:
        ref = _task_ref(entities)
        logger.info("查询任务详情", extra={"tenant_id": headers.get("X-Tenant-Code"), "ref": ref})
        return {
            "success": True,
            "service": "task",
            "operation": "query_detail",
            "data": {
                "id": entities.get("task_id") or ref,
                "title": entities.get("task_title") or str(ref),
                "status": "进行中",
                "assignee": entities.get("person_name") or "待分配",
            },
            "message": f"已查询任务「{ref}」详情",
        }

    async def _update_task(
        self, entities: Dict[str, Any], user_context: Dict[str, Any], headers: Dict[str, str]
    ) -> Dict[str, Any]:
        ref = _task_ref(entities)
        updates = []
        if entities.get("task_status"):
            updates.append(f"状态改为「{entities['task_status']}」")
        if entities.get("priority"):
            updates.append(f"优先级改为「{entities['priority']}」")
        return {
            "success": True,
            "service": "task",
            "operation": "update",
            "data": {"task_ref": ref, "updates": updates},
            "message": f"任务「{ref}」已更新" + (f"：{', '.join(updates)}" if updates else ""),
        }

    async def _complete_task(
        self, entities: Dict[str, Any], user_context: Dict[str, Any], headers: Dict[str, str]
    ) -> Dict[str, Any]:
        ref = _task_ref(entities)
        return {
            "success": True,
            "service": "task",
            "operation": "complete",
            "data": {"task_ref": ref, "status": "已完成"},
            "message": f"任务「{ref}」已完成",
        }

    async def _delete_task(
        self, entities: Dict[str, Any], user_context: Dict[str, Any], headers: Dict[str, str]
    ) -> Dict[str, Any]:
        ref = _task_ref(entities)
        return {
            "success": True,
            "service": "task",
            "operation": "delete",
            "data": {"task_ref": ref},
            "message": f"任务「{ref}」已删除",
        }

    # ----- 项目 -----

    async def _create_project(
        self, entities: Dict[str, Any], user_context: Dict[str, Any], headers: Dict[str, str]
    ) -> Dict[str, Any]:
        name = entities["project_name"]
        return {
            "success": True,
            "service": "project",
            "operation": "create",
            "data": {"project_id": 100, "name": name, "status": "筹备中"},
            "message": f"项目「{name}」创建成功",
        }

    async def _query_project(
        self, entities: Dict[str, Any], user_context: Dict[str, Any], headers: Dict[str, str]
    ) -> Dict[str, Any]:
        ref = _project_ref(entities)
        return {
            "success": True,
            "service": "project",
            "operation": "query",
            "data": {
                "project_id": entities.get("project_id") or ref,
                "name": entities.get("project_name") or str(ref),
                "status": "进行中",
                "progress": 65,
            },
            "message": f"已查询项目「{ref}」",
        }

    async def _query_project_list(
        self, entities: Dict[str, Any], user_context: Dict[str, Any], headers: Dict[str, str]
    ) -> Dict[str, Any]:
        return {
            "success": True,
            "service": "project",
            "operation": "query_list",
            "data": {
                "total": 2,
                "projects": [
                    {"id": 1, "name": "企业协作平台", "status": "进行中"},
                    {"id": 2, "name": "移动端改版", "status": "筹备中"},
                ],
            },
            "message": "查询到 2 个项目",
        }

    async def _query_project_tasks(
        self, entities: Dict[str, Any], user_context: Dict[str, Any], headers: Dict[str, str]
    ) -> Dict[str, Any]:
        ref = _project_ref(entities)
        return {
            "success": True,
            "service": "project",
            "operation": "query_tasks",
            "data": {
                "project_ref": ref,
                "tasks": [
                    {"id": 1, "title": "需求分析", "status": "已完成"},
                    {"id": 2, "title": "接口开发", "status": "进行中"},
                ],
            },
            "message": f"已查询项目「{ref}」下的任务",
        }

    # ----- 执行分工 / 评分 -----

    async def _create_execution(
        self, entities: Dict[str, Any], user_context: Dict[str, Any], headers: Dict[str, str]
    ) -> Dict[str, Any]:
        title = entities["execution_title"]
        return {
            "success": True,
            "service": "execution",
            "operation": "create",
            "data": {"execution_id": 5001, "title": title},
            "message": f"执行分工「{title}」创建成功",
        }

    async def _query_execution_list(
        self, entities: Dict[str, Any], user_context: Dict[str, Any], headers: Dict[str, str]
    ) -> Dict[str, Any]:
        return {
            "success": True,
            "service": "execution",
            "operation": "query_list",
            "data": {"executions": [{"id": 1, "title": "模块开发", "status": "进行中"}]},
            "message": "查询到执行分工列表",
        }

    async def _query_execution(
        self, entities: Dict[str, Any], user_context: Dict[str, Any], headers: Dict[str, str]
    ) -> Dict[str, Any]:
        ref = _execution_ref(entities)
        return {
            "success": True,
            "service": "execution",
            "operation": "query",
            "data": {
                "execution_id": entities.get("execution_id") or ref,
                "title": entities.get("execution_title") or str(ref),
                "status": "进行中",
            },
            "message": f"已查询执行分工「{ref}」",
        }

    async def _update_execution(
        self, entities: Dict[str, Any], user_context: Dict[str, Any], headers: Dict[str, str]
    ) -> Dict[str, Any]:
        ref = _execution_ref(entities)
        return {
            "success": True,
            "service": "execution",
            "operation": "update",
            "data": {"execution_ref": ref},
            "message": f"执行分工「{ref}」已更新",
        }

    async def _create_execution_score(
        self, entities: Dict[str, Any], user_context: Dict[str, Any], headers: Dict[str, str]
    ) -> Dict[str, Any]:
        score = entities["score_value"]
        ref = _execution_ref(entities)
        return {
            "success": True,
            "service": "score",
            "operation": "create",
            "data": {
                "execution_ref": ref,
                "score": score,
                "comment": entities.get("evaluation_content", ""),
            },
            "message": f"已为「{ref}」提交评分 {score}",
        }

    async def _query_score(
        self, entities: Dict[str, Any], user_context: Dict[str, Any], headers: Dict[str, str]
    ) -> Dict[str, Any]:
        return {
            "success": True,
            "service": "score",
            "operation": "query",
            "data": {"score": 85.5, "grade": "优秀"},
            "message": "查询评分成功",
        }

    async def _update_execution_score(
        self, entities: Dict[str, Any], user_context: Dict[str, Any], headers: Dict[str, str]
    ) -> Dict[str, Any]:
        return {
            "success": True,
            "service": "score",
            "operation": "update",
            "message": "评分已更新",
        }

    async def _query_employee(
        self, entities: Dict[str, Any], user_context: Dict[str, Any], headers: Dict[str, str]
    ) -> Dict[str, Any]:
        ref = _person_ref(entities)
        return {
            "success": True,
            "service": "employee",
            "operation": "query",
            "data": {
                "employee_id": entities.get("employee_id") or ref,
                "name": entities.get("person_name") or str(ref),
                "department": "技术部",
            },
            "message": f"已查询员工「{ref}」",
        }

    async def _query_weekly_work_summary(
        self, entities: Dict[str, Any], user_context: Dict[str, Any], headers: Dict[str, str]
    ) -> Dict[str, Any]:
        """按自然周汇总任务与执行内容（mock，对接真实微服务时替换）。"""
        week_start = entities.get("week_start", "")
        week_end = entities.get("week_end", "")
        scope = entities.get("report_scope") or entities.get("project_name")

        all_tasks = [
            {
                "id": 1024,
                "title": "完成需求文档 v1.2 评审",
                "project_name": "企业协作平台",
                "status": "已完成",
                "completed_at": week_end or "2026-05-29",
            },
            {
                "id": 1031,
                "title": "接口开发",
                "project_name": "企业协作平台",
                "status": "进行中",
            },
            {
                "id": 2040,
                "title": "UI 组件库迁移",
                "project_name": "移动端改版",
                "status": "进行中",
            },
        ]
        all_executions = [
            {
                "id": 501,
                "title": "用户模块 API 设计与实现",
                "task_title": "接口开发",
                "project_name": "企业协作平台",
                "status": "已完成",
                "deliverable": "PR #456",
            },
            {
                "id": 502,
                "title": "单元测试补充",
                "task_title": "接口开发",
                "project_name": "企业协作平台",
                "status": "进行中",
                "deliverable": "覆盖率 65%",
            },
        ]

        if scope == "all_projects":
            tasks = all_tasks
            executions = all_executions
        elif scope and scope not in ("all_projects", "single_project"):
            # 指定项目名
            tasks = [t for t in all_tasks if t["project_name"] == scope]
            executions = [e for e in all_executions if e.get("project_name") == scope]
        elif entities.get("report_scope") == "single_project" and entities.get("project_name"):
            pname = entities["project_name"]
            tasks = [t for t in all_tasks if t["project_name"] == pname]
            executions = [e for e in all_executions if e.get("project_name") == pname]
        else:
            tasks = all_tasks
            executions = all_executions

        projects = sorted({t["project_name"] for t in tasks})
        return {
            "success": True,
            "service": "weekly",
            "operation": "query_summary",
            "data": {
                "week_start": week_start,
                "week_end": week_end,
                "task_count": len(tasks),
                "execution_count": len(executions),
                "tasks": tasks,
                "executions": executions,
                "projects": [{"name": n} for n in projects],
            },
            "message": f"已汇总 {week_start} ~ {week_end} 共 {len(tasks)} 条任务",
        }

    async def _general_chat(
        self, entities: Dict[str, Any], user_context: Dict[str, Any], headers: Dict[str, str]
    ) -> Dict[str, Any]:
        return {
            "success": True,
            "service": "chat",
            "operation": "general",
            "data": {},
            "message": "",
        }


_business_service_proxy: Optional[BusinessServiceProxy] = None


def get_business_service_proxy() -> BusinessServiceProxy:
    global _business_service_proxy
    if _business_service_proxy is None:
        _business_service_proxy = BusinessServiceProxy()
    return _business_service_proxy
