"""
知识库模型
"""
from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey, JSON, Float
from sqlalchemy.orm import relationship
from datetime import datetime

from app.core.database import Base


class KnowledgeDocument(Base):
    """知识文档表"""
    __tablename__ = "knowledge_documents"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text)
    
    # 来源
    source_type = Column(String(50))  # manual, task, project, import
    source_id = Column(String(100))
    
    # 元数据
    doc_metadata = Column(JSON, default={})
    tags = Column(JSON, default=[])
    
    # 状态
    is_active = Column(Integer, default=1)
    embedding_status = Column(String(20), default="pending")
    
    # 统计
    chunk_count = Column(Integer, default=0)
    access_count = Column(Integer, default=0)
    
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    chunks = relationship("KnowledgeChunk", back_populates="document")


class KnowledgeChunk(Base):
    """知识片段表 (用于RAG)"""
    __tablename__ = "knowledge_chunks"
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("knowledge_documents.id"), nullable=False)
    
    # 内容
    content = Column(Text, nullable=False)
    chunk_index = Column(Integer)  # 在文档中的顺序
    
    # 向量ID (Chroma)
    vector_id = Column(String(100))
    
    # 向量metadata (用于过滤)
    chunk_metadata = Column(JSON, default={})
    
    # 统计
    access_count = Column(Integer, default=0)
    similarity_score = Column(Float, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 关系
    document = relationship("KnowledgeDocument", back_populates="chunks")
