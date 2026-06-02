"""
应用配置管理
"""
from pydantic_settings import BaseSettings
from typing import Optional
from functools import lru_cache

# 视为线上环境，默认启用 Cross-Encoder 精排
_PROD_ENV_NAMES = frozenset({"production", "prod", "staging"})


class Settings(BaseSettings):
    """应用配置"""
    
    # 环境
    environment: str = "development"
    
    # LLM
    openai_api_key: str
    openai_model: str = "gpt-4-turbo-preview"
    openai_base_url: Optional[str] = None  # 如使用 qwen 等需设置 DashScope 地址
    openai_embedding_model: str = "text-embedding-3-small"
    
    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_username: str = "neo4j"
    neo4j_password: str = ""
    
    # MySQL
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = ""
    mysql_database: str = "enterprise_agent"

    # Redis（P3：跨请求澄清 pending，多实例共享）
    redis_url: Optional[str] = None
    clarification_state_backend: str = "auto"  # auto | redis | memory
    clarification_state_ttl_seconds: int = 86400
    redis_connect_timeout_seconds: float = 2.0

    # LangGraph Checkpointer（P4）
    graph_checkpoint_backend: str = "auto"  # auto | redis | memory
    
    # Chroma
    chroma_host: str = "localhost"
    chroma_port: int = 8000
    
    # JWT
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # 监控
    log_level: str = "INFO"
    enable_tracing: bool = True
    token_budget_warning_threshold: float = 0.8
    token_budget_critical_threshold: float = 0.95

    # RAG 精排：cross_encoder | lexical；留空则按 environment 自动选择
    rag_reranker_backend: Optional[str] = None
    rag_reranker_model: str = "BAAI/bge-reranker-base"
    rag_reranker_max_doc_chars: int = 1500

    def effective_rag_reranker_backend(self) -> str:
        """
        解析实际精排后端。
        - 显式设置 RAG_RERANKER_BACKEND 时优先使用
        - 否则 development → lexical；production/staging → cross_encoder
        """
        if self.rag_reranker_backend:
            return self.rag_reranker_backend.lower().strip()
        if self.environment.lower().strip() in _PROD_ENV_NAMES:
            return "cross_encoder"
        return "lexical"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()
