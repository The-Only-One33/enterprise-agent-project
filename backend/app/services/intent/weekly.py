"""
周报生成 / 导出相关意图
"""
from app.services.intent.base import (
    IntentType,
    IntentPattern,
    RoutingTarget,
    INTENT_PATTERNS,
)

WeeklyIntentPatterns = [
    IntentPattern(
        intent=IntentType.WEEKLY_SUMMARY,
        keywords=[
            "周报",
            "工作总结",
            "本周总结",
            "本周工作",
            "导出周报",
            "生成周报",
            "写周报",
            "weekly.*report",
            "work.*summary",
        ],
        exclude_keywords=[
            "怎么写",
            "如何写",
            "格式",
            "规范",
            "模板说明",
        ],
        routing_target=RoutingTarget.PLANNER,
        suggested_model="gpt-4o-mini",
        priority=8,
    ),
]

INTENT_PATTERNS.extend(WeeklyIntentPatterns)
