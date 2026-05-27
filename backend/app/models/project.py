"""
项目模型
"""
from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey, Float
from sqlalchemy.orm import relationship
from datetime import datetime

from app.core.database import Base


class Project(Base):
    """项目表"""
    __tablename__ = "projects"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # 目标
    goal = Column(Text)
    key_results = Column(Text)  # OKR
    
    # 状态
    status = Column(String(50), default="active")  # active, completed, archived
    progress = Column(Float, default=0.0)  # 0-100
    
    # 时间
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 元数据
    is_public = Column(Integer, default=0)
    department = Column(String(100))
    
    # 关系
    owner = relationship("User", back_populates="owned_projects")
    tasks = relationship("Task", back_populates="project")
