"""
业务服务代理
负责根据意图调用对应的业务微服务

架构说明：
- Agent 只负责 AI 能力（意图识别、实体提取、答案生成）
- 具体业务逻辑由各业务微服务实现
- 租户隔离：微服务调用时携带 tenant_id

权限说明：
- 租户隔离由微服务内部处理
- 此处仅传递 tenant_id，由微服务根据租户过滤数据
"""
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class BusinessServiceProxy:
    """
    业务服务代理

    职责：
    1. 根据意图路由到对应的业务微服务
    2. 传递租户上下文（微服务根据 tenant_id 做数据隔离）
    3. 处理微服务返回的结果
    """

    def __init__(self):
        # TODO: 后续接入微服务时，初始化 HTTP 客户端
        # self.http_client = httpx.AsyncClient(timeout=30.0)
        pass

    async def execute(
        self,
        intent: str,
        entities: Dict[str, Any],
        user_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        根据意图执行业务操作

        Args:
            intent: 意图类型
            entities: 提取的实体
            user_context: 用户上下文（包含 tenant_id, employ_code）

        Returns:
            业务执行结果
        """
        user_context = user_context or {}
        tenant_id = user_context.get("tenant_id", "TENANT_DEFAULT")
        employ_code = user_context.get("employ_code", "E_DEFAULT")

        # 构建微服务调用头（用于租户隔离）
        service_headers = {
            "X-Tenant-Code": tenant_id,
            "X-Employ-Code": employ_code,
        }

        # 路由到对应的业务服务
        intent_handlers = {
            # 任务相关
            "create_task": self._create_task,
            "query_task_list": self._query_task_list,
            "query_task_detail": self._query_task_detail,
            "update_task": self._update_task,
            "complete_task": self._complete_task,
            "delete_task": self._delete_task,

            # 评分相关
            "create_execution_score": self._create_execution_score,
            "query_score": self._query_score,
            "update_execution_score": self._update_execution_score,

            # 项目相关
            "create_project": self._create_project,
            "query_project": self._query_project,

            # 执行分工相关
            "create_execution": self._create_execution,
            "query_execution": self._query_execution,
            "update_execution": self._update_execution,

            # 员工相关
            "query_employee": self._query_employee,

            # 通用
            "general_chat": self._general_chat,
        }

        handler = intent_handlers.get(intent)
        if handler:
            try:
                # 传递租户上下文给具体业务方法
                return await handler(entities, user_context, service_headers)
            except Exception as e:
                logger.error(f"执行意图 {intent} 失败: {e}", extra={"tenant_id": tenant_id})
                return {"success": False, "error": str(e), "message": "业务执行失败"}
        else:
            logger.warning(f"未找到意图处理器: {intent}", extra={"tenant_id": tenant_id})
            return {"success": False, "error": f"未支持意图: {intent}"}

    # ==================== 任务服务 ====================

    async def _create_task(
        self,
        entities: Dict[str, Any],
        user_context: Dict[str, Any],
        headers: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        创建任务

        TODO: 调用 Task 微服务
        POST /api/tasks
        Headers: X-Tenant-Code, X-Employ-Code
        """
        tenant_id = headers.get("X-Tenant-Code")
        logger.info(f"创建任务", extra={"tenant_id": tenant_id, "entities": entities})

        # TODO: 调用微服务
        # response = await self.http_client.post(
        #     "/api/tasks",
        #     json={"title": entities.get("task_title")},
        #     headers=headers,
        # )
        # return response.json()

        # Mock 实现
        return {
            "success": True,
            "service": "task",
            "operation": "create",
            "data": {
                "task_id": 12345,
                "title": entities.get("task_title", "新任务"),
                "status": "待处理",
                "created_at": "2025-01-20 10:00:00",
            },
            "message": f"任务「{entities.get('task_title', '新任务')}」创建成功",
        }

    async def _query_task_list(
        self,
        entities: Dict[str, Any],
        user_context: Dict[str, Any],
        headers: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        查询任务列表

        TODO: 调用 Task 微服务
        GET /api/tasks?user_id=xxx&project_id=xxx&status=xxx
        Headers: X-Tenant-Code, X-Employ-Code

        说明：微服务内部会根据 tenant_id + employ_code 过滤：
        - 只返回与当前员工相关的任务（负责人、参与人、执行人）
        """
        tenant_id = headers.get("X-Tenant-Code")
        employ_code = headers.get("X-Employ-Code")
        logger.info(f"查询任务列表", extra={"tenant_id": tenant_id, "employ_code": employ_code})

        # TODO: 调用微服务（携带租户和员工信息）
        # response = await self.http_client.get(
        #     "/api/tasks",
        #     params={"employ_code": employ_code},
        #     headers=headers,
        # )
        # 微服务内部会做数据过滤：WHERE tenant_id = ? AND (assignee = ? OR participant = ?)

        # Mock 实现
        return {
            "success": True,
            "service": "task",
            "operation": "query_list",
            "data": {
                "total": 3,
                "tasks": [
                    {"id": 1, "title": "完成需求文档", "status": "进行中", "priority": "高", "assignee": "张三"},
                    {"id": 2, "title": "代码评审", "status": "待处理", "priority": "中", "assignee": "张三"},
                    {"id": 3, "title": "编写测试用例", "status": "已完成", "priority": "低", "assignee": "张三"},
                ],
            },
            "message": "查询到 3 条任务",
        }

    async def _query_task_detail(
        self,
        entities: Dict[str, Any],
        user_context: Dict[str, Any],
        headers: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        查询任务详情

        TODO: 调用 Task 微服务
        GET /api/tasks/{task_id}
        """
        tenant_id = headers.get("X-Tenant-Code")
        task_id = entities.get("task_id") or entities.get("task_id_value")
        logger.info(f"查询任务详情", extra={"tenant_id": tenant_id, "task_id": task_id})

        return {
            "success": True,
            "service": "task",
            "operation": "query_detail",
            "data": {
                "id": task_id or 1,
                "title": "完成需求文档",
                "description": "完成本周的需求分析文档编写",
                "status": "进行中",
                "priority": "高",
                "assignee": "张三",
                "participants": ["李四", "王五"],
                "deadline": "2025-01-25",
            },
        }

    async def _update_task(
        self,
        entities: Dict[str, Any],
        user_context: Dict[str, Any],
        headers: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        更新任务

        TODO: 调用 Task 微服务
        PUT /api/tasks/{task_id}
        """
        tenant_id = headers.get("X-Tenant-Code")
        task_id = entities.get("task_id") or entities.get("task_id_value")
        logger.info(f"更新任务", extra={"tenant_id": tenant_id, "task_id": task_id})

        updates = []
        if entities.get("task_status"):
            updates.append(f"状态改为「{entities['task_status']}」")
        if entities.get("priority"):
            updates.append(f"优先级改为「{entities['priority']}」")

        return {
            "success": True,
            "service": "task",
            "operation": "update",
            "data": {"task_id": task_id or 1},
            "message": f"任务已更新：{', '.join(updates)}" if updates else "任务信息已更新",
        }

    async def _complete_task(
        self,
        entities: Dict[str, Any],
        user_context: Dict[str, Any],
        headers: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        完成任务

        TODO: 调用 Task 微服务
        POST /api/tasks/{task_id}/complete
        """
        tenant_id = headers.get("X-Tenant-Code")
        task_id = entities.get("task_id") or entities.get("task_id_value")
        logger.info(f"完成任务", extra={"tenant_id": tenant_id, "task_id": task_id})

        return {
            "success": True,
            "service": "task",
            "operation": "complete",
            "data": {"task_id": task_id or 1, "status": "已完成"},
            "message": "任务已完成",
        }

    async def _delete_task(
        self,
        entities: Dict[str, Any],
        user_context: Dict[str, Any],
        headers: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        删除任务

        TODO: 调用 Task 微服务
        DELETE /api/tasks/{task_id}
        """
        tenant_id = headers.get("X-Tenant-Code")
        task_id = entities.get("task_id") or entities.get("task_id_value")
        logger.info(f"删除任务", extra={"tenant_id": tenant_id, "task_id": task_id})

        return {
            "success": True,
            "service": "task",
            "operation": "delete",
            "data": {"task_id": task_id or 1},
            "message": "任务已删除",
        }

    # ==================== 评分服务 ====================

    async def _create_execution_score(
        self,
        entities: Dict[str, Any],
        user_context: Dict[str, Any],
        headers: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        创建执行分工评分

        TODO: 调用 Score 微服务
        POST /api/scores
        """
        tenant_id = headers.get("X-Tenant-Code")
        logger.info(f"创建执行分工评分", extra={"tenant_id": tenant_id, "entities": entities})

        score = entities.get("score_value")

        return {
            "success": True,
            "service": "score",
            "operation": "create",
            "data": {
                "score_id": 1001,
                "execution_id": entities.get("execution_id"),
                "score": score or 85,
                "comment": entities.get("evaluation_content", ""),
            },
            "message": f"评分 {score or 85} 分已提交",
        }

    async def _query_score(
        self,
        entities: Dict[str, Any],
        user_context: Dict[str, Any],
        headers: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        查询评分

        TODO: 调用 Score 微服务
        GET /api/scores?execution_id=xxx
        """
        tenant_id = headers.get("X-Tenant-Code")
        logger.info(f"查询评分", extra={"tenant_id": tenant_id})

        return {
            "success": True,
            "service": "score",
            "operation": "query",
            "data": {
                "score": 85.5,
                "grade": "优秀",
                "comment": "工作质量很高，按时完成",
            },
        }

    async def _update_execution_score(
        self,
        entities: Dict[str, Any],
        user_context: Dict[str, Any],
        headers: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        更新评分

        TODO: 调用 Score 微服务
        PUT /api/scores/{score_id}
        """
        tenant_id = headers.get("X-Tenant-Code")
        logger.info(f"更新评分", extra={"tenant_id": tenant_id})

        return {
            "success": True,
            "service": "score",
            "operation": "update",
            "message": "评分已更新",
        }

    # ==================== 项目服务 ====================

    async def _create_project(
        self,
        entities: Dict[str, Any],
        user_context: Dict[str, Any],
        headers: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        创建项目

        TODO: 调用 Project 微服务
        POST /api/projects
        """
        tenant_id = headers.get("X-Tenant-Code")
        project_name = entities.get("project_name", "新项目")
        logger.info(f"创建项目: {project_name}", extra={"tenant_id": tenant_id})

        return {
            "success": True,
            "service": "project",
            "operation": "create",
            "data": {
                "project_id": 100,
                "name": project_name,
                "status": "筹备中",
            },
            "message": f"项目「{project_name}」创建成功",
        }

    async def _query_project(
        self,
        entities: Dict[str, Any],
        user_context: Dict[str, Any],
        headers: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        查询项目

        TODO: 调用 Project 微服务
        GET /api/projects/{project_id}
        """
        tenant_id = headers.get("X-Tenant-Code")
        logger.info(f"查询项目", extra={"tenant_id": tenant_id})

        return {
            "success": True,
            "service": "project",
            "operation": "query",
            "data": {
                "project_id": entities.get("project_id") or 1,
                "name": "企业协作平台",
                "status": "进行中",
                "progress": 65,
            },
        }

    # ==================== 执行分工服务 ====================

    async def _create_execution(
        self,
        entities: Dict[str, Any],
        user_context: Dict[str, Any],
        headers: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        创建执行分工

        TODO: 调用 Execution 微服务
        POST /api/executions
        """
        tenant_id = headers.get("X-Tenant-Code")
        logger.info(f"创建执行分工", extra={"tenant_id": tenant_id, "entities": entities})

        return {
            "success": True,
            "service": "execution",
            "operation": "create",
            "data": {
                "execution_id": 5001,
                "title": entities.get("execution_title", "新分工"),
            },
            "message": "执行分工创建成功",
        }

    async def _query_execution(
        self,
        entities: Dict[str, Any],
        user_context: Dict[str, Any],
        headers: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        查询执行分工

        TODO: 调用 Execution 微服务
        GET /api/executions/{execution_id}
        """
        tenant_id = headers.get("X-Tenant-Code")
        logger.info(f"查询执行分工", extra={"tenant_id": tenant_id})

        return {
            "success": True,
            "service": "execution",
            "operation": "query",
            "data": {
                "execution_id": entities.get("execution_id") or 1,
                "title": "模块开发",
                "assignee": "李四",
                "status": "进行中",
            },
        }

    async def _update_execution(
        self,
        entities: Dict[str, Any],
        user_context: Dict[str, Any],
        headers: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        更新执行分工

        TODO: 调用 Execution 微服务
        PUT /api/executions/{execution_id}
        """
        tenant_id = headers.get("X-Tenant-Code")
        logger.info(f"更新执行分工", extra={"tenant_id": tenant_id})

        return {
            "success": True,
            "service": "execution",
            "operation": "update",
            "message": "执行分工已更新",
        }

    # ==================== 员工服务 ====================

    async def _query_employee(
        self,
        entities: Dict[str, Any],
        user_context: Dict[str, Any],
        headers: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        查询员工信息

        TODO: 调用 User 微服务
        GET /api/users/{employee_id}
        """
        tenant_id = headers.get("X-Tenant-Code")
        logger.info(f"查询员工", extra={"tenant_id": tenant_id})

        return {
            "success": True,
            "service": "employee",
            "operation": "query",
            "data": {
                "employee_id": entities.get("employee_id"),
                "name": entities.get("person_name") or "张三",
                "department": "技术部",
                "position": "高级工程师",
            },
        }

    # ==================== 通用处理 ====================

    async def _general_chat(
        self,
        entities: Dict[str, Any],
        user_context: Dict[str, Any],
        headers: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        通用对话（不需要执行业务操作）
        """
        return {
            "success": True,
            "service": "chat",
            "operation": "general",
            "data": {},
            "message": "",
        }


# 全局单例
_business_service_proxy: Optional[BusinessServiceProxy] = None


def get_business_service_proxy() -> BusinessServiceProxy:
    """获取业务服务代理实例"""
    global _business_service_proxy
    if _business_service_proxy is None:
        _business_service_proxy = BusinessServiceProxy()
    return _business_service_proxy
