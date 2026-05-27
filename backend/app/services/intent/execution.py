"""
执行分工相关意图定义
"""
from enum import Enum
from app.services.intent.base import (
    IntentType,
    IntentPattern,
    RoutingTarget,
    INTENT_PATTERNS,
)


class ExecutionIntentType(str, Enum):
    """执行分工相关意图"""
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


# 执行分工意图模式注册
ExecutionIntentPatterns = [
    # ========== 执行分工基础操作 ==========

    # 查询执行分工列表
    IntentPattern(
        intent=IntentType.QUERY_EXECUTION_LIST,
        keywords=[
            "执行分工列表", "执行清单", "执行内容列表",
            "谁.*执行", "谁.*负责", "分配.*执行",
            "execution.*list", "assign.*list",
            "查看.*分工", "分工.*列表",
        ],
        routing_target=RoutingTarget.DB,
        suggested_model="gpt-3.5-turbo",
        priority=9,
    ),

    # 执行分工详情
    IntentPattern(
        intent=IntentType.QUERY_EXECUTION_DETAIL,
        keywords=[
            "执行.*详情", "执行.*内容.*详情",
            "execution.*detail", "任务.*详情",
        ],
        routing_target=RoutingTarget.DB,
        suggested_model="gpt-3.5-turbo",
        priority=8,
    ),

    # 创建执行分工
    IntentPattern(
        intent=IntentType.CREATE_EXECUTION,
        keywords=[
            "创建.*执行分工", "添加.*执行", "新建.*执行分工",
            "增加.*分工", "指派.*执行", "分配.*任务",
            "create.*execution", "add.*execution",
            "让.*去做", "安排.*执行",
        ],
        routing_target=RoutingTarget.CREATE,
        suggested_model="gpt-4-turbo",
        priority=10,
    ),

    # 编辑执行分工
    IntentPattern(
        intent=IntentType.UPDATE_EXECUTION,
        keywords=[
            "编辑.*执行", "修改.*执行分工", "更新.*执行",
            "edit.*execution", "update.*execution",
            "改.*执行", "调整.*执行",
        ],
        routing_target=RoutingTarget.UPDATE,
        suggested_model="gpt-4-turbo",
        priority=9,
    ),

    # 删除执行分工
    IntentPattern(
        intent=IntentType.DELETE_EXECUTION,
        keywords=[
            "删除.*执行", "移除.*执行", "取消.*执行",
            "delete.*execution", "remove.*execution",
        ],
        routing_target=RoutingTarget.UPDATE,
        suggested_model="gpt-4-turbo",
        priority=8,
    ),

    # 完成执行分工
    IntentPattern(
        intent=IntentType.COMPLETE_EXECUTION,
        keywords=[
            "完成.*执行", "执行.*完成", "标记.*完成",
            "complete.*execution", "finish.*execution",
            ".*执行.*了", "执行.*状态.*完成",
        ],
        routing_target=RoutingTarget.UPDATE,
        suggested_model="gpt-3.5-turbo",
        priority=9,
    ),

    # ========== 执行分工评分相关 ==========

    # 查询执行分工评分
    IntentPattern(
        intent=IntentType.QUERY_EXECUTION_SCORE,
        keywords=[
            "执行.*评分", "执行.*得分", "执行.*分数",
            "execution.*score", ".*执行.*评价.*分数",
        ],
        routing_target=RoutingTarget.DB,
        suggested_model="gpt-3.5-turbo",
        priority=8,
    ),

    # 添加执行分工评分
    IntentPattern(
        intent=IntentType.CREATE_EXECUTION_SCORE,
        keywords=[
            "给.*执行.*评分", "执行.*打.*分", "评定.*执行.*分",
            "add.*execution.*score", "rate.*execution",
            ".*执行.*打个分",
        ],
        routing_target=RoutingTarget.CREATE,
        suggested_model="gpt-4-turbo",
        priority=10,
    ),

    # 编辑执行分工评分
    IntentPattern(
        intent=IntentType.UPDATE_EXECUTION_SCORE,
        keywords=[
            "修改.*执行.*评分", "更新.*执行.*评分",
            "edit.*execution.*score", "modify.*execution.*score",
            "改.*执行.*分数",
        ],
        routing_target=RoutingTarget.UPDATE,
        suggested_model="gpt-4-turbo",
        priority=9,
    ),

    # 执行分工评分记录
    IntentPattern(
        intent=IntentType.QUERY_EXECUTION_SCORE_RECORD,
        keywords=[
            "执行.*评分.*记录", "执行.*评分.*历史",
            "execution.*score.*record", "execution.*score.*history",
            ".*执行.*评分.*日志",
        ],
        routing_target=RoutingTarget.DB,
        suggested_model="gpt-3.5-turbo",
        priority=7,
    ),

    # ========== 执行分工评价记录 ==========

    # 查询执行分工评价
    IntentPattern(
        intent=IntentType.QUERY_EXECUTION_EVALUATION,
        keywords=[
            "执行.*评价", "执行.*评语", "执行.*反馈",
            "execution.*evaluation", "execution.*comment",
            ".*执行.*怎么样", ".对.*执行.*评价",
        ],
        routing_target=RoutingTarget.DB,
        suggested_model="gpt-3.5-turbo",
        priority=8,
    ),

    # 添加执行分工评价
    IntentPattern(
        intent=IntentType.CREATE_EXECUTION_EVALUATION,
        keywords=[
            "添加.*执行.*评价", "评价.*执行", "给.*执行.*评语",
            "add.*execution.*evaluation", "comment.*execution",
            ".*执行.*怎么样", "觉得.*执行.*如何",
        ],
        routing_target=RoutingTarget.CREATE,
        suggested_model="gpt-4-turbo",
        priority=9,
    ),

    # 编辑执行分工评价
    IntentPattern(
        intent=IntentType.UPDATE_EXECUTION_EVALUATION,
        keywords=[
            "修改.*执行.*评价", "编辑.*执行.*评语",
            "edit.*execution.*evaluation", "modify.*execution.*comment",
            "改.*执行.*反馈",
        ],
        routing_target=RoutingTarget.UPDATE,
        suggested_model="gpt-4-turbo",
        priority=9,
    ),
]

# 注册到全局
INTENT_PATTERNS.extend(ExecutionIntentPatterns)
