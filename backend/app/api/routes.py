"""
API路由
"""
from fastapi import APIRouter

from . import agent, chat, tasks, projects, knowledge, monitor

api_router = APIRouter()

api_router.include_router(agent.router, prefix="/agent", tags=["Agent"])
api_router.include_router(chat.router, prefix="/chat", tags=["Chat"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["Tasks"])
api_router.include_router(projects.router, prefix="/projects", tags=["Projects"])
api_router.include_router(knowledge.router, prefix="/knowledge", tags=["Knowledge"])
api_router.include_router(monitor.router, prefix="/monitor", tags=["Monitor"])
