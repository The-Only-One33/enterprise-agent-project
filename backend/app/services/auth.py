"""
权限控制服务
Permission & Access Control
"""
from typing import List, Optional, Callable
from functools import wraps
from fastapi import HTTPException, status

from app.core.logging import get_logger

logger = get_logger(__name__)


class PermissionChecker:
    """权限检查器"""
    
    # 权限定义
    PERMISSIONS = {
        # 任务权限
        "task:create": "创建任务",
        "task:read": "读取任务",
        "task:read:public": "读取公开任务",
        "task:update": "更新任务",
        "task:update:own": "仅更新自己的任务",
        "task:delete": "删除任务",
        
        # 项目权限
        "project:create": "创建项目",
        "project:read": "读取项目",
        "project:read:public": "读取公开项目",
        "project:update": "更新项目",
        "project:delete": "删除项目",
        
        # 知识库权限
        "knowledge:create": "创建知识",
        "knowledge:read": "读取知识",
        "knowledge:update": "更新知识",
        "knowledge:delete": "删除知识",
        
        # 监控权限
        "monitor:read": "读取监控",
        "monitor:read:own": "仅读取自己的监控数据",
        
        # 用户权限
        "user:read": "读取用户",
        "user:create": "创建用户",
        "user:update": "更新用户",
        "user:delete": "删除用户",
    }
    
    # 角色权限映射
    ROLE_PERMISSIONS = {
        "admin": list(PERMISSIONS.keys()),  # 管理员拥有所有权限
        "manager": [
            "task:create", "task:read", "task:update",
            "project:create", "project:read", "project:update",
            "knowledge:create", "knowledge:read", "knowledge:update",
            "monitor:read", "user:read",
        ],
        "employee": [
            "task:read", "task:update:own",
            "project:read",
            "knowledge:read",
            "monitor:read:own",
        ],
        "guest": [
            "task:read:public",
            "project:read:public",
            "knowledge:read",
        ],
    }
    
    @classmethod
    def has_permission(cls, user, permission: str) -> bool:
        """检查用户是否有指定权限"""
        user_role = getattr(user, 'role', None) if hasattr(user, 'role') else None
        user_permissions = cls.ROLE_PERMISSIONS.get(user_role, [])
        
        # 完全匹配
        if permission in user_permissions:
            return True
        
        # 通配符 (*)
        if "*" in user_permissions:
            return True
        
        # 前缀匹配 (如 task:* 匹配 task:read)
        base_permission = permission.split(":")[0]
        if f"{base_permission}:*" in user_permissions:
            return True
        
        return False
    
    @classmethod
    def check_permission(cls, user, permission: str):
        """检查权限，不通过则抛出异常"""
        if not cls.has_permission(user, permission):
            user_id = getattr(user, 'id', None)
            user_role = getattr(user, 'role', None)
            logger.warning(
                "permission_denied",
                user_id=user_id,
                user_role=user_role,
                required_permission=permission,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"权限不足: 需要 {permission}",
            )
    
    @classmethod
    def filter_by_permission(
        cls,
        user,
        items: List,
        permission: str,
        owner_field: str = "user_id",
    ) -> List:
        """根据权限过滤列表（数据权限纵深防御）"""
        if cls.has_permission(user, permission):
            return items
        
        # 检查 :own 权限
        if permission.endswith(":own"):
            base_permission = permission.replace(":own", "")
            if cls.has_permission(user, base_permission):
                return [item for item in items if getattr(item, owner_field, None) == user.id]
        
        # 无权限返回空
        return []
    
    @classmethod
    def can_access_data(cls, user, data_owner_id: int, data_is_public: bool = False) -> bool:
        """检查用户是否可以访问数据"""
        user_role = getattr(user, 'role', None)
        
        # 管理员可以访问所有数据
        if user_role == "admin":
            return True
        
        # 公开数据
        if data_is_public:
            return True
        
        # 自己创建的数据
        if data_owner_id == user.id:
            return True
        
        return False
