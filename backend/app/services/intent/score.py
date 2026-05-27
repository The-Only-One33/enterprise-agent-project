"""
评分相关意图定义
"""
from enum import Enum
from app.services.intent.base import (
    IntentType,
    IntentPattern,
    RoutingTarget,
    INTENT_PATTERNS,
)


class ScoreIntentType(str, Enum):
    """评分相关意图"""
    # 任务评分
    QUERY_TASK_SCORE = "query_task_score"           # 任务评分
    CREATE_TASK_SCORE = "create_task_score"          # 创建任务评分

    # 执行内容评分
    QUERY_EXECUTION_SCORE = "query_execution_score"  # 执行内容评分
    CREATE_EXECUTION_SCORE = "create_execution_score"  # 创建执行内容评分

    # 邀请评分
    QUERY_INVITATION_SCORE = "query_invitation_score"  # 邀请评分
    CREATE_INVITATION_SCORE = "create_invitation_score"  # 创建邀请评分
    ACCEPT_INVITATION = "accept_invitation"              # 接受邀请评分
    REJECT_INVITATION = "reject_invitation"              # 拒绝邀请评分

    # 催办
    REMIND_SCORE = "remind_score"                     # 催办评分
    QUERY_PENDING_REMINDERS = "query_pending_reminders"  # 待催办列表

    # 评分记录
    QUERY_SCORE_RECORDS = "query_score_records"     # 评分记录
    QUERY_SCORE_HISTORY = "query_score_history"     # 评分历史


# 评分意图模式注册
ScoreIntentPatterns = [
    # 任务评分查询
    IntentPattern(
        intent=IntentType.QUERY_SCORE,
        keywords=[
            "任务评分", "得分", "评分", "分数", "绩效",
            "任务.*分", "完成质量", "task.*score", "rating"
        ],
        routing_target=RoutingTarget.DB,
        suggested_model="gpt-3.5-turbo",
        priority=8,
    ),

    # 执行内容评分
    IntentPattern(
        intent=IntentType.QUERY_SCORE,
        keywords=[
            "执行评分", "子任务.*评分", ".*执行.*评分",
            "execution.*score"
        ],
        routing_target=RoutingTarget.DB,
        suggested_model="gpt-3.5-turbo",
        priority=7,
    ),

    # 邀请评分
    IntentPattern(
        intent=IntentType.CREATE_INVITATION_SCORE,
        keywords=[
            "邀请.*评分", "请.*评分", "发起.*评分",
            "invite.*score", "request.*score", "ask.*rate"
        ],
        routing_target=RoutingTarget.CREATE,
        suggested_model="gpt-4-turbo",
        priority=9,
    ),

    # 接受/拒绝邀请
    IntentPattern(
        intent=IntentType.QUERY_SCORE,
        keywords=[
            "收到.*评分", "评分邀请", "待评分",
            "评分.*待", "pending.*score"
        ],
        routing_target=RoutingTarget.DB,
        suggested_model="gpt-3.5-turbo",
        priority=8,
    ),

    # 催办评分
    IntentPattern(
        intent=IntentType.REMIND_SCORE,
        keywords=[
            "催办", "提醒.*评分", "催.*评分",
            "remind", "urge.*score", "follow.*up"
        ],
        routing_target=RoutingTarget.DB,
        suggested_model="gpt-3.5-turbo",
        priority=8,
    ),

    # 评分记录
    IntentPattern(
        intent=IntentType.QUERY_SCORE_RECORD,
        keywords=[
            "评分记录", "评分.*历史", "历史评分",
            "score.*record", "score.*history", "评分.*日志"
        ],
        routing_target=RoutingTarget.DB,
        suggested_model="gpt-3.5-turbo",
        priority=7,
    ),

    # 创建评分
    IntentPattern(
        intent=IntentType.CREATE_SCORE,
        keywords=[
            "给.*评分", "打分", "评定.*分",
            "rate.*task", "score.*task", "给.*打个分"
        ],
        routing_target=RoutingTarget.CREATE,
        suggested_model="gpt-4-turbo",
        priority=9,
    ),
]

# 注册到全局
INTENT_PATTERNS.extend(ScoreIntentPatterns)
