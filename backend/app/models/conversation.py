"""
对话模型
"""
from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime

from app.core.database import Base


class Conversation(Base):
    """对话表"""
    __tablename__ = "conversations"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(200), default="新对话")
    
    # 配置
    config = Column(JSON, default={})  # 使用的模型、Agent类型等
    
    # 统计
    message_count = Column(Integer, default=0)
    token_usage = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", order_by="Message.created_at")


class Message(Base):
    """消息表"""
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    
    # 角色
    role = Column(String(20), nullable=False)  # user, assistant, system, tool
    
    # 内容
    content = Column(Text)
    
    # 工具调用 (Agent推理过程)
    tool_calls = Column(JSON, nullable=True)
    tool_results = Column(JSON, nullable=True)
    
    # Token统计
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    
    # 执行信息
    latency_ms = Column(Integer, nullable=True)
    model_used = Column(String(50))
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 关系
    conversation = relationship("Conversation", back_populates="messages")
