"""
知识库/RAG相关意图定义
"""
from enum import Enum
from app.services.intent.base import (
    IntentType,
    IntentPattern,
    RoutingTarget,
    INTENT_PATTERNS,
)


class KnowledgeIntentType(str, Enum):
    """知识库相关意图"""
    SEMANTIC_SEARCH = "semantic_search"           # 语义搜索
    SIMILAR_TASK = "similar_task"                 # 相似任务
    SIMILAR_PROJECT = "similar_project"           # 相似项目
    KNOWLEDGE_QA = "knowledge_qa"                # 知识问答
    DOCUMENT_SEARCH = "document_search"            # 文档搜索


# 知识库意图模式注册
KnowledgeIntentPatterns = [
    # 语义检索 - 排除业务查询关键词
    IntentPattern(
        intent=IntentType.RAG_SEMANTIC,
        keywords=[
            "怎么", "如何", "怎么办", "有没有",
            "查找", "搜索", "查询.*方法",
            "how.*to", "how.*can", "is.*there",
            "查找.*方法", "有什么方法"
        ],
        exclude_keywords=[
            # 业务实体
            "任务", "项目", "执行", "评分", "得分", "记录",
            "列表", "详情", "查询", "查看", "我的",
            # 操作类
            "创建", "编辑", "删除", "更新", "完成",
            # 统计类
            "统计", "汇总", "总额", "平均",
        ],
        routing_target=RoutingTarget.RAG,
        suggested_model="gpt-3.5-turbo",
        priority=3,  # 优先级较低，作为兜底
    ),

    # 相似任务 - 排除业务查询
    IntentPattern(
        intent=IntentType.RAG_SIMILAR,
        keywords=[
            "相似任务", "类似任务", "参考.*任务",
            "similar.*task", "like.*task",
            "有没有.*任务", "参考.*案例"
        ],
        exclude_keywords=[
            "列表", "详情", "查询", "查看", "我的", "创建", "编辑", "删除"
        ],
        routing_target=RoutingTarget.RAG,
        suggested_model="gpt-3.5-turbo",
        priority=7,
    ),

    # 相似项目 - 排除业务查询
    IntentPattern(
        intent=IntentType.RAG_SIMILAR,
        keywords=[
            "相似项目", "类似项目", "参考.*项目",
            "similar.*project", "like.*project"
        ],
        exclude_keywords=[
            "列表", "详情", "查询", "查看", "我的", "创建", "编辑", "删除"
        ],
        routing_target=RoutingTarget.RAG,
        suggested_model="gpt-3.5-turbo",
        priority=7,
    ),

    # 文档搜索 - 排除具体业务实体
    IntentPattern(
        intent=IntentType.RAG_SEMANTIC,
        keywords=[
            "文档", "资料", "手册", "指南",
            "document", "guide", "manual",
            "有没有.*文档", "查一下.*资料"
        ],
        exclude_keywords=[
            "任务", "项目", "执行", "列表", "详情", "查询", "查看", "我的"
        ],
        routing_target=RoutingTarget.RAG,
        suggested_model="gpt-3.5-turbo",
        priority=5,
    ),
]

# 注册到全局
INTENT_PATTERNS.extend(KnowledgeIntentPatterns)
