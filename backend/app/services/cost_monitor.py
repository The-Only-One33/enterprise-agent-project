"""
成本监控服务 — Token 用量写入 MySQL，报表从库聚合
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.database import AsyncSessionLocal
from app.core.logging import get_logger
from app.models.token_usage import TokenUsageLog
from app.services.llm_usage import estimate_cost_usd

logger = get_logger(__name__)
settings = get_settings()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _start_of_day(dt: datetime) -> datetime:
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def _start_of_month(dt: datetime) -> datetime:
    return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


class CostMonitor:
    def __init__(self):
        self.daily_budget = 10000
        self.monthly_budget = 300000
        self._db_available = True
        self.usage_stats = {
            "daily": {"used": 0, "limit": self.daily_budget, "reset_at": self._get_reset_time("daily")},
            "monthly": {"used": 0, "limit": self.monthly_budget, "reset_at": self._get_reset_time("monthly")},
        }

    def _get_reset_time(self, period: str) -> datetime:
        now = _utc_now()
        if period == "daily":
            return _start_of_day(now) + timedelta(days=1)
        return _start_of_month(now) + timedelta(days=32)

    async def _sum_tokens_since(self, session: AsyncSession, since: datetime) -> int:
        result = await session.execute(
            select(func.coalesce(func.sum(TokenUsageLog.total_tokens), 0)).where(
                TokenUsageLog.created_at >= since
            )
        )
        return int(result.scalar() or 0)

    async def _refresh_usage_stats_from_db(self) -> bool:
        try:
            async with AsyncSessionLocal() as session:
                now = _utc_now()
                daily_used = await self._sum_tokens_since(session, _start_of_day(now))
                monthly_used = await self._sum_tokens_since(session, _start_of_month(now))
            self.usage_stats["daily"]["used"] = daily_used
            self.usage_stats["monthly"]["used"] = monthly_used
            self.usage_stats["daily"]["reset_at"] = self._get_reset_time("daily")
            self.usage_stats["monthly"]["reset_at"] = self._get_reset_time("monthly")
            self._db_available = True
            return True
        except Exception as e:
            self._db_available = False
            logger.warning("token_budget_db_unavailable", error=str(e))
            return False

    async def check_token_budget(self) -> Dict[str, Any]:
        if not await self._refresh_usage_stats_from_db():
            now = _utc_now()
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

        daily_ratio = self.usage_stats["daily"]["used"] / max(self.daily_budget, 1)
        monthly_ratio = self.usage_stats["monthly"]["used"] / max(self.monthly_budget, 1)

        if daily_ratio >= settings.token_budget_critical_threshold or monthly_ratio >= settings.token_budget_critical_threshold:
            level = "critical"
        elif daily_ratio >= settings.token_budget_warning_threshold or monthly_ratio >= settings.token_budget_warning_threshold:
            level = "warning"
        else:
            level = "normal"

        return {
            "level": level,
            "daily": self.usage_stats["daily"],
            "monthly": self.usage_stats["monthly"],
            "daily_ratio": daily_ratio,
            "monthly_ratio": monthly_ratio,
            "db_available": self._db_available,
        }

    async def record_usage(
        self,
        input_tokens: int,
        output_tokens: int,
        model: str,
        *,
        tenant_id: Optional[str] = None,
        user_key: Optional[str] = None,
        conversation_id: Optional[int] = None,
        intent: Optional[str] = None,
        stage: str = "answer",
    ) -> None:
        total_tokens = input_tokens + output_tokens
        if total_tokens <= 0:
            return

        cost_usd = estimate_cost_usd(model, input_tokens, output_tokens)
        self.usage_stats["daily"]["used"] += total_tokens
        self.usage_stats["monthly"]["used"] += total_tokens

        logger.info(
            "token_usage_recorded",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            model=model,
            tenant_id=tenant_id,
            intent=intent,
            stage=stage,
        )

        try:
            async with AsyncSessionLocal() as session:
                session.add(
                    TokenUsageLog(
                        tenant_id=tenant_id,
                        user_key=user_key,
                        conversation_id=conversation_id,
                        intent=intent,
                        stage=stage,
                        model=model,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        total_tokens=total_tokens,
                        cost_usd=cost_usd,
                    )
                )
                await session.commit()
            self._db_available = True
        except Exception as e:
            self._db_available = False
            logger.error("failed_to_save_token_usage", error=str(e))

    async def get_usage_report(self, user_id: Optional[int] = None, days: int = 7) -> Dict[str, Any]:
        days = max(1, min(days, 90))
        try:
            async with AsyncSessionLocal() as session:
                since = _start_of_day(_utc_now() - timedelta(days=days - 1))
                day_expr = func.date(TokenUsageLog.created_at)
                stmt = (
                    select(
                        day_expr.label("day"),
                        func.coalesce(func.sum(TokenUsageLog.total_tokens), 0).label("tokens"),
                        func.coalesce(func.sum(TokenUsageLog.cost_usd), 0).label("cost"),
                        func.count(TokenUsageLog.id).label("requests"),
                    )
                    .where(TokenUsageLog.created_at >= since)
                    .group_by(day_expr)
                    .order_by(day_expr)
                )
                rows = (await session.execute(stmt)).all()
                daily_usage = []
                for row in rows:
                    day_val = row.day
                    date_str = day_val.isoformat() if hasattr(day_val, "isoformat") else str(day_val)
                    daily_usage.append({
                        "date": date_str,
                        "tokens": int(row.tokens or 0),
                        "cost": float(row.cost or 0),
                        "requests": int(row.requests or 0),
                    })
                if not daily_usage:
                    daily_usage = self._empty_daily_breakdown(days)

                return {
                    "period": f"last_{days}_days",
                    "total_tokens": sum(d["tokens"] for d in daily_usage),
                    "total_cost": round(sum(d["cost"] for d in daily_usage), 4),
                    "total_requests": sum(d["requests"] for d in daily_usage),
                    "daily_breakdown": daily_usage,
                    "budget_status": await self.check_token_budget(),
                    "data_source": "mysql",
                }
        except Exception as e:
            logger.warning("usage_report_fallback", error=str(e))
            return await self._empty_usage_report(days)

    def _empty_daily_breakdown(self, days: int) -> List[Dict[str, Any]]:
        items = []
        for i in range(days - 1, -1, -1):
            date = (_utc_now() - timedelta(days=i)).strftime("%Y-%m-%d")
            items.append({"date": date, "tokens": 0, "cost": 0.0, "requests": 0})
        return items

    async def _empty_usage_report(self, days: int) -> Dict[str, Any]:
        daily_usage = self._empty_daily_breakdown(days)
        return {
            "period": f"last_{days}_days",
            "total_tokens": 0,
            "total_cost": 0.0,
            "total_requests": 0,
            "daily_breakdown": daily_usage,
            "budget_status": await self.check_token_budget(),
            "data_source": "unavailable",
        }

    async def get_cost_distribution(self, days: int = 7) -> Dict[str, Any]:
        days = max(1, min(days, 90))
        try:
            async with AsyncSessionLocal() as session:
                since = _utc_now() - timedelta(days=days)
                intent_rows = (
                    await session.execute(
                        select(
                            TokenUsageLog.intent,
                            func.coalesce(func.sum(TokenUsageLog.total_tokens), 0).label("tokens"),
                        )
                        .where(TokenUsageLog.created_at >= since)
                        .where(TokenUsageLog.intent.isnot(None))
                        .group_by(TokenUsageLog.intent)
                    )
                ).all()
                intent_total = sum(int(r.tokens or 0) for r in intent_rows) or 1

                model_rows = (
                    await session.execute(
                        select(
                            TokenUsageLog.model,
                            func.coalesce(func.sum(TokenUsageLog.total_tokens), 0).label("tokens"),
                        )
                        .where(TokenUsageLog.created_at >= since)
                        .group_by(TokenUsageLog.model)
                    )
                ).all()
                model_total = sum(int(r.tokens or 0) for r in model_rows) or 1

                return {
                    "by_intent": [
                        {
                            "intent": r.intent or "unknown",
                            "tokens": int(r.tokens or 0),
                            "percentage": round(int(r.tokens or 0) / intent_total * 100, 1),
                        }
                        for r in intent_rows
                    ],
                    "by_model": [
                        {
                            "model": r.model,
                            "tokens": int(r.tokens or 0),
                            "percentage": round(int(r.tokens or 0) / model_total * 100, 1),
                        }
                        for r in model_rows
                    ],
                    "data_source": "mysql",
                }
        except Exception as e:
            logger.warning("cost_distribution_fallback", error=str(e))
            return {"by_intent": [], "by_model": [], "data_source": "unavailable"}

    async def get_recent_activity(self, limit: int = 20) -> List[Dict[str, Any]]:
        limit = max(1, min(limit, 100))
        try:
            async with AsyncSessionLocal() as session:
                rows = (
                    await session.execute(
                        select(TokenUsageLog).order_by(TokenUsageLog.created_at.desc()).limit(limit)
                    )
                ).scalars().all()
                items = []
                for row in rows:
                    ts = row.created_at
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    items.append({
                        "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
                        "level": "INFO",
                        "service": "agent",
                        "message": (
                            f"[{row.stage}] intent={row.intent or '-'} "
                            f"tokens={row.total_tokens} model={row.model}"
                        ),
                        "intent": row.intent,
                        "stage": row.stage,
                        "model": row.model,
                        "total_tokens": row.total_tokens,
                    })
                return items
        except Exception as e:
            logger.warning("recent_activity_unavailable", error=str(e))
            return []


_cost_monitor: Optional[CostMonitor] = None


async def get_cost_monitor() -> CostMonitor:
    global _cost_monitor
    if _cost_monitor is None:
        _cost_monitor = CostMonitor()
    return _cost_monitor


async def check_token_budget() -> Dict[str, Any]:
    monitor = await get_cost_monitor()
    return await monitor.check_token_budget()
