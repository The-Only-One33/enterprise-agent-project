"""
监控API
"""
from fastapi import APIRouter
from app.services.cost_monitor import get_cost_monitor

router = APIRouter()


@router.get("/token-budget")
async def get_token_budget():
    monitor = await get_cost_monitor()
    return await monitor.check_token_budget()


@router.get("/usage-report")
async def get_usage_report(days: int = 7):
    monitor = await get_cost_monitor()
    return await monitor.get_usage_report(days=days)


@router.get("/cost-distribution")
async def get_cost_distribution(days: int = 7):
    monitor = await get_cost_monitor()
    return await monitor.get_cost_distribution(days=days)


@router.get("/recent-activity")
async def get_recent_activity(limit: int = 20):
    monitor = await get_cost_monitor()
    return {"items": await monitor.get_recent_activity(limit=limit)}
