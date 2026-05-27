"""
任务相关意图定义
"""
from enum import Enum
from app.services.intent.base import (
    IntentType,
    IntentPattern,
    RoutingTarget,
    INTENT_PATTERNS,
)


class TaskIntentType(str, Enum):
    """任务相关意图"""
    # 任务列表查询
    QUERY_MY_TASKS = "query_my_tasks"           # 我的任务
    QUERY_ALL_TASKS = "query_all_tasks"          # 所有任务
    QUERY_TASKS_BY_STATUS = "query_tasks_by_status"  # 按状态查询任务
    QUERY_TASKS_BY_DATE = "query_tasks_by_date"      # 按日期查询任务
    QUERY_TASKS_BY_PRIORITY = "query_tasks_by_priority"  # 按优先级查询

    # 任务详情
    QUERY_TASK_DETAIL = "query_task_detail"     # 任务详情
    QUERY_TASK_PROGRESS = "query_task_progress" # 任务进度
    QUERY_TASK_MEMBERS = "query_task_members"   # 任务成员

    # 任务执行内容
    QUERY_EXECUTION_LIST = "query_execution_list"       # 执行内容列表
    QUERY_EXECUTION_DETAIL = "query_execution_detail"   # 执行内容详情
    UPDATE_EXECUTION = "update_execution"               # 更新执行内容
    CREATE_EXECUTION = "create_execution"               # 创建执行内容

    # 任务操作
    CREATE_TASK = "create_task"              # 创建任务
    UPDATE_TASK = "update_task"              # 更新任务
    DELETE_TASK = "delete_task"              # 删除任务
    COMPLETE_TASK = "complete_task"          # 完成任务

    # 任务评价
    QUERY_TASK_EVALUATION = "query_task_evaluation"  # 任务评价记录
    CREATE_TASK_EVALUATION = "create_task_evaluation"  # 添加任务评价
    UPDATE_TASK_EVALUATION = "update_task_evaluation"  # 编辑任务评价


# 任务意图模式注册
TaskIntentPatterns = [
    # ========== 任务列表查询 ==========

    # 我的任务
    IntentPattern(
        intent=IntentType.QUERY_TASK_LIST,
        keywords=[
            "我的任务", "当前任务", "待办任务", "我负责的任务",
            "我参与的任务", "分配给我的", "assign.*me", "my.*task",
            "有哪些任务", "有什么任务", "查一下我的任务"
        ],
        exclude_keywords=["创建", "新建", "添加"],
        routing_target=RoutingTarget.DB,
        suggested_model="gpt-3.5-turbo",
        priority=10,
    ),

    # 按状态查询任务
    IntentPattern(
        intent=IntentType.QUERY_TASK_STATUS,
        keywords=[
            "待处理", "进行中", "已完成", "待审核", "已拒绝",
            "pending", "in_progress", "completed", "review",
            "任务.*状态", ".*状态的任务", "状态是.*的任务"
        ],
        routing_target=RoutingTarget.DB,
        suggested_model="gpt-3.5-turbo",
        priority=8,
    ),

    # 按日期查询任务
    IntentPattern(
        intent=IntentType.QUERY_TASK_LIST,
        keywords=[
            "今天", "明天", "本周", "本月", "最近",
            "截止.*", "截止日期", "创建时间",
            "today", "tomorrow", "this week", "due.*"
        ],
        routing_target=RoutingTarget.DB,
        suggested_model="gpt-3.5-turbo",
        priority=7,
    ),

    # ========== 任务详情/状态 ==========

    # 任务详情
    IntentPattern(
        intent=IntentType.QUERY_TASK_DETAIL,
        keywords=[
            "任务详情", "任务内容", ".*任务.*详情",
            "看一下.*任务", ".*任务的.*", "task.*detail"
        ],
        routing_target=RoutingTarget.DB,
        suggested_model="gpt-3.5-turbo",
        priority=6,
    ),

    # 任务进度
    IntentPattern(
        intent=IntentType.QUERY_TASK_PROGRESS,
        keywords=[
            "任务进度", "完成.*进度", ".*进度.*如何",
            "task.*progress", "完成.*百分之", "完成率"
        ],
        routing_target=RoutingTarget.DB,
        suggested_model="gpt-3.5-turbo",
        priority=7,
    ),

    # 任务成员
    IntentPattern(
        intent=IntentType.QUERY_TASK_MEMBERS,
        keywords=[
            "任务成员", ".*任务.*谁", ".*任务.*人",
            "task.*member", ".*任务.*参加",
        ],
        routing_target=RoutingTarget.DB,
        suggested_model="gpt-3.5-turbo",
        priority=6,
    ),

    # ========== 任务操作 ==========

    # 创建任务
    IntentPattern(
        intent=IntentType.CREATE_TASK,
        keywords=[
            "创建任务", "新建任务", "添加任务", "新建.*任务",
            "create.*task", "new.*task", "add.*task",
            "我想.*任务", "要.*任务"
        ],
        routing_target=RoutingTarget.CREATE,
        suggested_model="gpt-4-turbo",
        priority=9,
    ),

    # 更新任务
    IntentPattern(
        intent=IntentType.UPDATE_TASK,
        keywords=[
            "更新任务", "修改任务", "编辑任务",
            "标记.*完成", "标记.*进行", "标记.*待处理",
            "update.*task", "modify.*task", "edit.*task",
            "把.*任务.*改成", "把.*任务.*改为"
        ],
        routing_target=RoutingTarget.UPDATE,
        suggested_model="gpt-4-turbo",
        priority=9,
    ),

    # 删除任务
    IntentPattern(
        intent=IntentType.DELETE_TASK,
        keywords=[
            "删除任务", "移除任务", "取消任务",
            "delete.*task", "remove.*task",
        ],
        routing_target=RoutingTarget.UPDATE,
        suggested_model="gpt-4-turbo",
        priority=8,
    ),

    # 完成任务
    IntentPattern(
        intent=IntentType.COMPLETE_TASK,
        keywords=[
            "完成任务", "任务.*完成", "标记.*完成",
            "complete.*task", "finish.*task",
        ],
        routing_target=RoutingTarget.UPDATE,
        suggested_model="gpt-3.5-turbo",
        priority=9,
    ),

    # ========== 执行内容/子任务 ==========

    # 执行内容列表
    IntentPattern(
        intent=IntentType.QUERY_EXECUTION_LIST,
        keywords=[
            "执行内容列表", "子任务列表", "执行清单", "任务分解",
            "execution.*list", "subtask.*list", "checklist"
        ],
        routing_target=RoutingTarget.DB,
        suggested_model="gpt-3.5-turbo",
        priority=8,
    ),

    # 执行内容详情
    IntentPattern(
        intent=IntentType.QUERY_EXECUTION_DETAIL,
        keywords=[
            "执行.*详情", "子任务.*详情",
            "execution.*detail",
        ],
        routing_target=RoutingTarget.DB,
        suggested_model="gpt-3.5-turbo",
        priority=7,
    ),

    # 创建执行内容
    IntentPattern(
        intent=IntentType.CREATE_EXECUTION,
        keywords=[
            "添加.*执行内容", "新建.*子任务", "增加.*执行",
            "add.*subtask", "add.*execution",
            "创建.*子任务",
        ],
        routing_target=RoutingTarget.CREATE,
        suggested_model="gpt-4-turbo",
        priority=9,
    ),

    # 更新执行内容
    IntentPattern(
        intent=IntentType.UPDATE_EXECUTION,
        keywords=[
            "修改.*执行内容", "更新.*子任务",
            "update.*subtask", "update.*execution",
        ],
        routing_target=RoutingTarget.UPDATE,
        suggested_model="gpt-4-turbo",
        priority=9,
    ),

    # ========== 任务评价 ==========

    # 查询任务评价
    IntentPattern(
        intent=IntentType.QUERY_TASK_EVALUATION,
        keywords=[
            "任务评价", "任务评语", "任务反馈", "任务.*怎么样",
            "task.*evaluation", "task.*comment",
            "对.*任务.*评价", ".*任务.*如何",
        ],
        routing_target=RoutingTarget.DB,
        suggested_model="gpt-3.5-turbo",
        priority=8,
    ),

    # 添加任务评价
    IntentPattern(
        intent=IntentType.CREATE_TASK_EVALUATION,
        keywords=[
            "添加.*任务.*评价", "评价.*任务", "给.*任务.*评语",
            "add.*task.*evaluation", "comment.*task",
            "对.*任务.*怎么.*看",
        ],
        routing_target=RoutingTarget.CREATE,
        suggested_model="gpt-4-turbo",
        priority=9,
    ),

    # 编辑任务评价
    IntentPattern(
        intent=IntentType.UPDATE_TASK_EVALUATION,
        keywords=[
            "修改.*任务.*评价", "编辑.*任务.*评语",
            "edit.*task.*evaluation", "modify.*task.*comment",
        ],
        routing_target=RoutingTarget.UPDATE,
        suggested_model="gpt-4-turbo",
        priority=9,
    ),

    # 查看任务执行内容和评分
    IntentPattern(
        intent=IntentType.QUERY_TASK_LIST,
        keywords=[
            "任务.*执行.*评分", "任务.*内容.*评分",
            ".*执行.*列表.*评分",
        ],
        routing_target=RoutingTarget.DB,
        suggested_model="gpt-3.5-turbo",
        priority=7,
    ),

    # 编辑任务执行内容和评分
    IntentPattern(
        intent=IntentType.UPDATE_TASK,
        keywords=[
            "编辑.*任务.*执行.*评分", "修改.*任务.*内容.*评分",
            "edit.*task.*execution.*score",
        ],
        routing_target=RoutingTarget.UPDATE,
        suggested_model="gpt-4-turbo",
        priority=8,
    ),
]

# 注册到全局
INTENT_PATTERNS.extend(TaskIntentPatterns)
