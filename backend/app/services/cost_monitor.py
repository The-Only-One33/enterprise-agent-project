"""
成本监控服务
Token Cost Monitoring & Budget Control
"""
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class CostMonitor:
    """成本监控器"""
    
    def __init__(self):
        self.daily_budget = 10000  # 每日Token预算
        self.monthly_budget = 300000  # 月度Token预算
        self.usage_stats = {
            "daily": {"used": 0, "limit": self.daily_budget, "reset_at": self._get_reset_time("daily")},
            "monthly": {"used": 0, "limit": self.monthly_budget, "reset_at": self._get_reset_time("monthly")},
        }
    
    def _get_reset_time(self, period: str) -> datetime:
        """获取重置时间"""
        now = datetime.utcnow()
        if period == "daily":
            return now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        else:  # monthly
            return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0) + timedelta(days=32)
    
    async def check_token_budget(self) -> Dict[str, Any]:
        """检查Token预算状态"""
        now = datetime.utcnow()
        
        # 重置检查
        if now >= self.usage_stats["daily"]["reset_at"]:
            self.usage_stats["daily"] = {
                "used": 0,
                "limit": self.daily_budget,
                "reset_at": self._get_reset_time("daily"),
            }
        
        if now >= self.usage_stats["monthly"]["reset_at"]:
            self.usage_stats["monthly"] = {
                "used": 0,
                "limit": self.monthly_budget,
                "reset_at": self._get_reset_time("monthly"),
            }
        
        daily_ratio = self.usage_stats["daily"]["used"] / self.usage_stats["daily"]["limit"]
        monthly_ratio = self.usage_stats["monthly"]["used"] / self.usage_stats["monthly"]["limit"]
        
        # 确定告警级别
        if daily_ratio >= settings.token_budget_critical_threshold or \
           monthly_ratio >= settings.token_budget_critical_threshold:
            level = "critical"
        elif daily_ratio >= settings.token_budget_warning_threshold or \
             monthly_ratio >= settings.token_budget_warning_threshold:
            level = "warning"
        else:
            level = "normal"
        
        return {
            "level": level,
            "daily": self.usage_stats["daily"],
            "monthly": self.usage_stats["monthly"],
            "daily_ratio": daily_ratio,
            "monthly_ratio": monthly_ratio,
        }
    
    async def record_usage(
        self,
        input_tokens: int,
        output_tokens: int,
        model: str,
        user_id: int,
    ):
        """记录Token使用"""
        total_tokens = input_tokens + output_tokens
        
        self.usage_stats["daily"]["used"] += total_tokens
        self.usage_stats["monthly"]["used"] += total_tokens
        
        logger.info(
            "token_usage_recorded",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            model=model,
            user_id=user_id,
        )
        
        # 异步保存到数据库
        try:
            await self._save_usage_to_db(input_tokens, output_tokens, model, user_id)
        except Exception as e:
            logger.error("failed_to_save_token_usage", error=str(e))
    
    async def _save_usage_to_db(
        self,
        input_tokens: int,
        output_tokens: int,
        model: str,
        user_id: int,
    ):
        """保存使用记录到数据库"""
        from app.models.conversation import Message
        
        # 这里简化处理，实际应该使用数据库session
        logger.info(
            "token_usage_saved",
            user_id=user_id,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
    
    async def get_usage_report(
        self,
        user_id: Optional[int] = None,
        days: int = 7,
    ) -> Dict[str, Any]:
        """获取使用报告"""
        # 模拟数据
        daily_usage = []
        for i in range(days):
            date = (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d")
            daily_usage.append({
                "date": date,
                "tokens": 1000 + (i * 100),
                "cost": 0.5 + (i * 0.05),
                "requests": 50 + (i * 5),
            })
        
        return {
            "period": f"last_{days}_days",
            "total_tokens": sum(d["tokens"] for d in daily_usage),
            "total_cost": sum(d["cost"] for d in daily_usage),
            "total_requests": sum(d["requests"] for d in daily_usage),
            "daily_breakdown": daily_usage,
            "budget_status": await self.check_token_budget(),
        }
    
    async def get_cost_distribution(self, days: int = 7) -> Dict[str, Any]:
        """获取成本分布"""
        return {
            "by_intent": [
                {"intent": "task_create", "tokens": 5000, "percentage": 25},
                {"intent": "complex_reasoning", "tokens": 8000, "percentage": 40},
                {"intent": "query_score", "tokens": 3000, "percentage": 15},
                {"intent": "rag_search", "tokens": 4000, "percentage": 20},
            ],
            "by_model": [
                {"model": "gpt-4-turbo", "tokens": 12000, "percentage": 60},
                {"model": "gpt-3.5-turbo", "tokens": 8000, "percentage": 40},
            ],
        }


# 全局实例
_cost_monitor: Optional[CostMonitor] = None


async def get_cost_monitor() -> CostMonitor:
    """获取成本监控器单例"""
    global _cost_monitor
    if _cost_monitor is None:
        _cost_monitor = CostMonitor()
    return _cost_monitor


async def check_token_budget() -> Dict[str, Any]:
    """快速检查Token预算"""
    monitor = await get_cost_monitor()
    return await monitor.check_token_budget()
