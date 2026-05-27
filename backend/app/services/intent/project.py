"""
项目相关意图定义
"""
from enum import Enum
from app.services.intent.base import (
    IntentType,
    IntentPattern,
    RoutingTarget,
    INTENT_PATTERNS,
)


class ProjectIntentType(str, Enum):
    """项目相关意图"""
    QUERY_MY_PROJECTS = "query_my_projects"         # 我的项目
    QUERY_ALL_PROJECTS = "query_all_projects"        # 所有项目
    QUERY_PROJECT_DETAIL = "query_project_detail"   # 项目详情
    QUERY_PROJECT_MEMBERS = "query_project_members" # 项目成员
    QUERY_PROJECT_TASKS = "query_project_tasks"      # 项目任务

    CREATE_PROJECT = "create_project"              # 创建项目
    UPDATE_PROJECT = "update_project"              # 更新项目
    INVITE_MEMBER = "invite_member"                # 邀请成员


# 项目意图模式注册
ProjectIntentPatterns = [
    # ========== 基础项目操作 ==========

    # 我的项目
    IntentPattern(
        intent=IntentType.QUERY_PROJECT_LIST,
        keywords=[
            "我的项目", "参与的项目", "负责的项目",
            "my.*project", "project.*me", "my.*works"
        ],
        exclude_keywords=["创建", "新建"],
        routing_target=RoutingTarget.DB,
        suggested_model="gpt-3.5-turbo",
        priority=10,
    ),

    # 所有项目
    IntentPattern(
        intent=IntentType.QUERY_PROJECT_LIST,
        keywords=[
            "所有项目", "项目列表", "项目清单",
            "all.*project", "project.*list",
        ],
        routing_target=RoutingTarget.DB,
        suggested_model="gpt-3.5-turbo",
        priority=9,
    ),

    # 项目详情
    IntentPattern(
        intent=IntentType.QUERY_PROJECT_DETAIL,
        keywords=[
            "项目详情", "项目.*信息", ".*项目.*情况",
            "project.*detail", "project.*info"
        ],
        routing_target=RoutingTarget.DB,
        suggested_model="gpt-3.5-turbo",
        priority=6,
    ),

    # 创建项目
    IntentPattern(
        intent=IntentType.CREATE_PROJECT,
        keywords=[
            "创建项目", "新建项目", "发起项目",
            "create.*project", "new.*project"
        ],
        routing_target=RoutingTarget.CREATE,
        suggested_model="gpt-4-turbo",
        priority=9,
    ),

    # 更新项目
    IntentPattern(
        intent=IntentType.UPDATE_PROJECT,
        keywords=[
            "更新项目", "修改项目",
            "update.*project", "modify.*project"
        ],
        routing_target=RoutingTarget.UPDATE,
        suggested_model="gpt-4-turbo",
        priority=9,
    ),

    # ========== 项目下任务相关 ==========

    # 项目任务列表（含执行内容/评分）
    IntentPattern(
        intent=IntentType.QUERY_PROJECT_TASKS,
        keywords=[
            "项目.*任务.*列表", "项目.*所有.*任务",
            ".*项目.*任务.*执行", ".*项目.*任务.*评分",
            "project.*tasks", ".*project.*task.*list",
            "项目.*有哪些.*任务",
        ],
        routing_target=RoutingTarget.DB,
        suggested_model="gpt-3.5-turbo",
        priority=9,
    ),

    # 编辑项目任务列表
    IntentPattern(
        intent=IntentType.UPDATE_PROJECT_TASKS,
        keywords=[
            "编辑.*项目.*任务", "修改.*项目.*任务列表",
            "edit.*project.*tasks", "modify.*project.*task.*list",
            "调整.*项目.*任务",
        ],
        routing_target=RoutingTarget.UPDATE,
        suggested_model="gpt-4-turbo",
        priority=9,
    ),

    # 项目任务执行内容列表
    IntentPattern(
        intent=IntentType.QUERY_PROJECT_TASKS,
        keywords=[
            "项目.*执行.*列表", "项目.*执行.*内容",
            ".*项目.*有哪些.*执行",
        ],
        routing_target=RoutingTarget.DB,
        suggested_model="gpt-3.5-turbo",
        priority=8,
    ),

    # 项目任务评分
    IntentPattern(
        intent=IntentType.QUERY_PROJECT_TASKS,
        keywords=[
            "项目.*任务.*评分", "项目.*任务.*分数",
            ".*项目.*任务.*得分",
        ],
        routing_target=RoutingTarget.DB,
        suggested_model="gpt-3.5-turbo",
        priority=8,
    ),

    # ========== 项目人员相关 ==========

    # 项目成员列表
    IntentPattern(
        intent=IntentType.QUERY_PROJECT_MEMBERS,
        keywords=[
            "项目成员", "谁.*项目", ".*项目.*人",
            "project.*member", ".*project.*people",
            "项目.*参与者", "项目.*人员",
        ],
        routing_target=RoutingTarget.DB,
        suggested_model="gpt-3.5-turbo",
        priority=8,
    ),

    # 项目人员评分
    IntentPattern(
        intent=IntentType.QUERY_PROJECT_MEMBERS,
        keywords=[
            "项目.*成员.*评分", "项目.*人员.*分数",
            "项目.*人.*得分", ".*项目.*谁.*评分",
            "project.*member.*score",
        ],
        routing_target=RoutingTarget.DB,
        suggested_model="gpt-3.5-turbo",
        priority=8,
    ),

    # 项目所有评分
    IntentPattern(
        intent=IntentType.QUERY_PROJECT_SCORES,
        keywords=[
            "项目.*评分.*列表", "项目.*所有.*评分",
            "项目.*评分.*汇总", ".*project.*scores",
            "项目.*得分.*统计",
        ],
        routing_target=RoutingTarget.DB,
        suggested_model="gpt-3.5-turbo",
        priority=8,
    ),

    # 邀请成员
    IntentPattern(
        intent=IntentType.QUERY_PROJECT_LIST,
        keywords=[
            "邀请.*加入", "加入项目", "添加成员",
            "invite.*join", "add.*member"
        ],
        routing_target=RoutingTarget.UPDATE,
        suggested_model="gpt-4-turbo",
        priority=8,
    ),
]

# 注册到全局
INTENT_PATTERNS.extend(ProjectIntentPatterns)
