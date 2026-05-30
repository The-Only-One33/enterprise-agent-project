"""
意图基础定义
"""
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel


class IntentType(str, Enum):
    """基础意图类型枚举"""

    # ========== 任务相关 ==========
    # 任务列表查询
    QUERY_TASK_LIST = "query_task_list"           # 查询任务列表
    QUERY_MY_TASKS = "query_my_tasks"             # 我的任务
    QUERY_ALL_TASKS = "query_all_tasks"           # 所有任务

    # 任务详情/状态
    QUERY_TASK_STATUS = "query_task_status"       # 查询任务状态
    QUERY_TASK_DETAIL = "query_task_detail"       # 查询任务详情
    QUERY_TASK_PROGRESS = "query_task_progress"   # 查询任务进度
    QUERY_TASK_MEMBERS = "query_task_members"     # 查询任务成员

    # 任务操作
    CREATE_TASK = "create_task"                    # 创建任务
    UPDATE_TASK = "update_task"                   # 更新任务
    DELETE_TASK = "delete_task"                   # 删除任务
    COMPLETE_TASK = "complete_task"               # 完成任务

    # ========== 执行分工相关 ==========
    # 执行分工基础
    QUERY_EXECUTION_LIST = "query_execution_list"      # 执行分工列表
    QUERY_EXECUTION_DETAIL = "query_execution_detail"  # 执行分工详情
    CREATE_EXECUTION = "create_execution"              # 创建执行分工
    UPDATE_EXECUTION = "update_execution"              # 编辑执行分工
    DELETE_EXECUTION = "delete_execution"              # 删除执行分工
    COMPLETE_EXECUTION = "complete_execution"          # 完成执行分工

    # 执行分工评分
    QUERY_EXECUTION_SCORE = "query_execution_score"    # 执行分工评分
    CREATE_EXECUTION_SCORE = "create_execution_score"  # 添加执行分工评分
    UPDATE_EXECUTION_SCORE = "update_execution_score"  # 编辑执行分工评分
    QUERY_EXECUTION_SCORE_RECORD = "query_execution_score_record"  # 执行分工评分记录

    # 执行分工评价
    QUERY_EXECUTION_EVALUATION = "query_execution_evaluation"  # 执行分工评价记录
    CREATE_EXECUTION_EVALUATION = "create_execution_evaluation"  # 添加评价记录
    UPDATE_EXECUTION_EVALUATION = "update_execution_evaluation"  # 编辑评价记录

    # ========== 项目相关 ==========
    QUERY_PROJECT_LIST = "query_project_list"      # 查询项目列表
    QUERY_PROJECT_DETAIL = "query_project_detail"  # 查询项目详情
    CREATE_PROJECT = "create_project"              # 创建项目
    UPDATE_PROJECT = "update_project"              # 更新项目

    # 项目下的任务和人员
    QUERY_PROJECT_TASKS = "query_project_tasks"     # 项目下任务列表（含执行内容/评分）
    UPDATE_PROJECT_TASKS = "update_project_tasks"   # 编辑项目下任务列表
    QUERY_PROJECT_MEMBERS = "query_project_members"  # 项目下人员列表（含评分）
    QUERY_PROJECT_SCORES = "query_project_scores"    # 项目下所有评分

    # ========== 任务评价 ==========
    QUERY_TASK_EVALUATION = "query_task_evaluation"  # 任务评价记录
    CREATE_TASK_EVALUATION = "create_task_evaluation"  # 添加任务评价
    UPDATE_TASK_EVALUATION = "update_task_evaluation"  # 编辑任务评价

    # ========== 评分相关 ==========
    QUERY_SCORE = "query_score"                   # 查询评分
    CREATE_SCORE = "create_score"                  # 创建评分
    UPDATE_SCORE = "update_score"                  # 更新评分
    QUERY_SCORE_RECORD = "query_score_record"      # 查询评分记录
    CREATE_INVITATION_SCORE = "create_invitation_score"  # 邀请评分
    REMIND_SCORE = "remind_score"                 # 催办评分

    # ========== 知识库/RAG ==========
    RAG_SEMANTIC = "rag_semantic"                 # 语义检索
    RAG_SIMILAR = "rag_similar"                   # 相似任务检索

    # ========== 图谱/关系 ==========
    GRAPH_TRAVERSE = "graph_traverse"             # 图谱遍历

    # ========== 通用 ==========
    GENERAL_CHAT = "general_chat"                 # 通用对话


class IntentPriority(str, Enum):
    """意图匹配优先级"""
    KEYWORD = "keyword"      # 关键词匹配
    ENTITY = "entity"       # 实体提取
    LLM = "llm"             # LLM语义识别


class RoutingTarget(str, Enum):
    """路由目标"""
    DB = "db"               # 数据库查询
    RAG = "rag"             # 向量检索
    GRAPH = "graph"         # 图谱查询
    LLM = "llm"             # LLM推理
    CREATE = "create"       # 创建操作
    UPDATE = "update"       # 更新操作


class IntentResult(BaseModel):
    """意图识别结果"""
    intent: IntentType
    confidence: float                    # 0-1 置信度
    entities: Dict[str, Any]             # 提取的实体
    routing_target: RoutingTarget        # 路由目标
    suggested_model: str                 # 建议使用的模型
    reasoning: str                      # 推理过程

    # 调试信息
    needs_clarification: bool = False   # 是否需要澄清
    clarification_question: str = ""    # 
    candidate_intents: List[str] = []  # 可能的意图列表
    confidence_breakdown: Dict[str, Any] = {}  # 各意图置信度分解
    # 意图链路 LLM 用量（实体提取、意图识别），供 cost_monitor 落库
    llm_usages: List[Dict[str, Any]] = []


class IntentPattern(BaseModel):
    """意图模式定义"""
    intent: IntentType
    keywords: List[str]                 # 关键词列表
    exclude_keywords: List[str] = []    # 排除关键词
    routing_target: RoutingTarget
    suggested_model: str = "gpt-3.5-turbo"
    priority: int = 0                    # 优先级，数字越大优先级越高


# 全局意图模式注册表
INTENT_PATTERNS: List[IntentPattern] = []
