"""
中间件配置
"""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import time
from typing import Callable

from app.core.logging import get_logger

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """请求日志中间件"""
    
    async def dispatch(self, request: Request, call_next: Callable):
        request_id = request.headers.get("X-Request-ID", "")
        start_time = time.time()
        
        # 记录请求
        logger.info(
            "request_started",
            method=request.method,
            path=request.url.path,
            request_id=request_id,
            client=request.client.host if request.client else None,
        )
        
        try:
            response = await call_next(request)
            
            # 记录响应
            duration = time.time() - start_time
            logger.info(
                "request_completed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=round(duration * 1000, 2),
                request_id=request_id,
            )
            
            response.headers["X-Request-ID"] = request_id
            return response
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                "request_failed",
                method=request.method,
                path=request.url.path,
                error=str(e),
                duration_ms=round(duration * 1000, 2),
                request_id=request_id,
            )
            raise


class TokenBudgetMiddleware(BaseHTTPMiddleware):
    """Token预算中间件"""
    
    async def dispatch(self, request: Request, call_next: Callable):
        # 检查Token预算
        from app.services.cost_monitor import check_token_budget
        
        budget_status = await check_token_budget()
        
        if budget_status.get("level") == "critical":
            return JSONResponse(
                status_code=503,
                content={
                    "error": "Service temporarily unavailable",
                    "message": "Token budget exceeded. Non-critical requests are being degraded.",
                    "retry_after": budget_status.get("retry_after", 60),
                }
            )
        
        return await call_next(request)


def setup_middleware(app: FastAPI):
    """设置中间件"""
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(TokenBudgetMiddleware)
