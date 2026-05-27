"""
应用初始化
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import os

from app.config import get_settings
from app.api.routes import api_router
from app.core.logging import setup_logging
from app.core.middleware import setup_middleware
from app.core.observability import setup_observability


# 获取静态文件目录
STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    settings = get_settings()
    setup_logging(settings.log_level)
    
    # 启动时初始化
    from app.core.database import init_databases
    await init_databases()
    
    yield
    
    # 关闭时清理
    from app.core.database import close_databases
    await close_databases()


def create_app() -> FastAPI:
    """创建应用实例"""
    settings = get_settings()
    
    app = FastAPI(
        title="智能任务协同Agent系统",
        description="基于 LangGraph + LangChain 的企业级智能协同平台",
        version="1.0.0",
        lifespan=lifespan,
    )
    
    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 中间件
    setup_middleware(app)
    
    # 可观测性
    if settings.enable_tracing:
        setup_observability(app)
    
    # 路由
    app.include_router(api_router, prefix="/api/v1")
    
    # 挂载前端构建产物（/assets 目录）
    assets_dir = os.path.join(STATIC_DIR, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
    
    # SPA 路由支持：所有非 API、非静态资源路径返回 index.html
    @app.get("/{path:path}", include_in_schema=False)
    async def serve_spa(path: str):
        # 排除 API 和静态资源请求
        if path.startswith("api/") or path.startswith("assets/"):
            return {"message": "Not Found"}
        index_path = os.path.join(STATIC_DIR, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        return {"message": "Frontend not found"}

    return app


app = create_app()
