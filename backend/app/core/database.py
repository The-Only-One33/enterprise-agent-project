"""
数据库连接管理
"""
from neo4j import AsyncGraphDatabase
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from typing import AsyncGenerator
import structlog

from app.config import get_settings

settings = get_settings()
logger = structlog.get_logger()

# SQLAlchemy Base
Base = declarative_base()

# Neo4j 驱动
neo4j_driver = None

# SQLAlchemy 引擎
engine = create_async_engine(
    f"mysql+aiomysql://{settings.mysql_user}:{settings.mysql_password}@"
    f"{settings.mysql_host}:{settings.mysql_port}/{settings.mysql_database}",
    echo=settings.environment == "development",
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_databases():
    """初始化数据库连接"""
    global neo4j_driver
    
    # 初始化 Neo4j (可选)
    try:
        neo4j_driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_username, settings.neo4j_password),
        )
        await neo4j_driver.verify_connectivity()
        logger.info("Neo4j connected successfully")
    except Exception as e:
        logger.warning("Neo4j connection failed, running without graph database", error=str(e))
        neo4j_driver = None
    
    # 初始化 MySQL 表 (可选)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("MySQL connected successfully")
    except Exception as e:
        logger.warning("MySQL connection failed, running in demo mode", error=str(e))


async def close_databases():
    """关闭数据库连接"""
    global neo4j_driver
    
    if neo4j_driver:
        await neo4j_driver.close()
    
    await engine.dispose()


async def get_neo4j_session() -> AsyncGenerator:
    """获取 Neo4j 会话"""
    global neo4j_driver
    if neo4j_driver is None:
        raise RuntimeError("Neo4j is not available")
    async with neo4j_driver.session() as session:
        yield session


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话"""
    try:
        async with AsyncSessionLocal() as session:
            try:
                yield session
            finally:
                await session.close()
    except Exception as e:
        logger.error("Database session error", error=str(e))
        raise RuntimeError("Database is not available")
