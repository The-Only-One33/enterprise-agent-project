"""
通用对话意图定义
"""
from app.services.intent.base import (
    IntentType,
    IntentPattern,
    RoutingTarget,
    INTENT_PATTERNS,
)


# 通用对话意图模式注册
ChatIntentPatterns = [
    # 通用对话（兜底）
    IntentPattern(
        intent=IntentType.GENERAL_CHAT,
        keywords=[
            "你好", "嗨", "hi", "hello", "在吗",
            "谢谢", "辛苦了", "打扰",
            "今天天气", "新闻", "笑话"
        ],
        routing_target=RoutingTarget.LLM,
        suggested_model="gpt-3.5-turbo",
        priority=1,
    ),

    # 复杂推理
    IntentPattern(
        intent=IntentType.GRAPH_TRAVERSE,
        keywords=[
            "分析", "评估", "预测", "建议",
            "analyze", "evaluate", "predict", "advise",
            "对比", "比较", "推荐"
        ],
        routing_target=RoutingTarget.LLM,
        suggested_model="gpt-4-turbo",
        priority=6,
    ),
]

# 注册到全局
INTENT_PATTERNS.extend(ChatIntentPatterns)
