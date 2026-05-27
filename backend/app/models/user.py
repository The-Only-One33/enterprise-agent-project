"""
用户模型
"""
from sqlalchemy import Column, String, Integer, DateTime, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.core.database import Base


class UserRole(str, enum.Enum):
    """用户角色"""
    ADMIN = "admin"
    MANAGER = "manager"
    EMPLOYEE = "employee"
    GUEST = "guest"


class User(Base):
    """用户表"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100))
    role = Column(SQLEnum(UserRole), default=UserRole.EMPLOYEE)
    department = Column(String(100))
    position = Column(String(100))
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    tasks = relationship("Task", back_populates="assignee", foreign_keys="Task.assignee_id")
    owned_projects = relationship("Project", back_populates="owner")
    conversations = relationship("Conversation", back_populates="user")
    
    def get_permissions(self) -> list[str]:
        """获取用户权限"""
        permissions_map = {
            UserRole.ADMIN: ["*"],
            UserRole.MANAGER: [
                "task:create", "task:read", "task:update", "task:delete",
                "project:create", "project:read", "project:update",
                "knowledge:create", "knowledge:read", "knowledge:update",
                "monitor:read", "user:read"
            ],
            UserRole.EMPLOYEE: [
                "task:read", "task:update:own",
                "project:read",
                "knowledge:read",
                "monitor:read:own"
            ],
            UserRole.GUEST: [
                "task:read:public",
                "project:read:public",
                "knowledge:read:public"
            ]
        }
        return permissions_map.get(self.role, [])
