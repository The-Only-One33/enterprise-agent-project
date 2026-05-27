"""
意图识别模块

按业务域拆分的意图定义：
- task: 任务相关意图
- project: 项目相关意图
- score: 评分相关意图
- execution: 执行分工相关意图
- knowledge: 知识库/RAG相关意图
- chat: 通用对话意图
"""
from app.services.intent.base import IntentType, IntentResult, IntentPriority
from app.services.intent.task import TaskIntentType
from app.services.intent.project import ProjectIntentType
from app.services.intent.score import ScoreIntentType
from app.services.intent.execution import ExecutionIntentType
from app.services.intent.knowledge import KnowledgeIntentType

__all__ = [
    "IntentType",
    "IntentResult",
    "IntentPriority",
    "TaskIntentType",
    "ProjectIntentType",
    "ScoreIntentType",
    "ExecutionIntentType",
    "KnowledgeIntentType",
]
