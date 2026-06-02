"""
意图识别与路由服务（兼容旧接口）

导入新模块，保持向后兼容
"""
# 导出新模块的核心类和函数
from app.services.intent.router import IntentRouter, get_intent_router
from app.services.intent.base import (
    IntentType,
    IntentResult,
    IntentPriority,
    RoutingTarget,
)
from app.services.intent.task import TaskIntentType
from app.services.intent.project import ProjectIntentType
from app.services.intent.score import ScoreIntentType
from app.services.intent.knowledge import KnowledgeIntentType
from app.services.intent import weekly  # noqa: F401 — 注册周报意图模式

__all__ = [
    "IntentRouter",
    "get_intent_router",
    "IntentType",
    "IntentResult",
    "IntentPriority",
    "RoutingTarget",
    "TaskIntentType",
    "ProjectIntentType",
    "ScoreIntentType",
    "KnowledgeIntentType",
]
