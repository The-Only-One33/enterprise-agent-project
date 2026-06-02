"""
Agent API

权限说明：
- 用户身份由网关校验（employCode, tenantCode, token）
- Agent 项目仅接收已校验的用户上下文
- 租户隔离：RAG 和业务服务都需携带 tenant_id
"""
import json
from typing import Any, AsyncIterator, Dict, List, Literal, Optional, Tuple, Union

from fastapi import APIRouter, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agent import astream_llm_tokens, get_agent_graph, get_agent_prepare_graph
from app.agent.graph import AgentState, append_llm_reasoning_step, maybe_export_weekly_report
from app.agent.runner import (
    clear_graph_thread,
    invoke_agent_graph,
    invoke_prepare_graph,
)
from app.services.conversation_service import get_conversation_service

router = APIRouter()

ChatOutcomeKind = Literal["clarification", "agent", "ready"]


class AgentRequest(BaseModel):
    """Agent请求"""
    message: str
    conversation_id: Optional[int] = None  # 会话ID，用于多轮对话


class ClarificationResponse(BaseModel):
    """澄清响应 - 当需要用户确认意图或补充参数时返回"""
    type: str = "clarification"
    clarification_question: str
    conversation_id: int
    reasoning_steps: List[Dict[str, Any]]
    clarification_type: str = "intent"  # intent | slot | plan
    missing_slots: Optional[List[str]] = None


class AgentResponse(BaseModel):
    """Agent响应"""
    type: str = "agent"
    response: str
    intent: str
    confidence: float
    routing_target: str
    reasoning_steps: List[Dict[str, Any]]
    sources: Optional[List[Dict[str, Any]]] = None
    conversation_id: Optional[int] = None
    export_path: Optional[str] = None


async def _ensure_conversation(
    conversation_id: Optional[int],
    user_context: Dict[str, Any],
    message: str,
) -> int:
    """确保会话存在于 MySQL，无 conversation_id 时自动创建。"""
    conv_svc = get_conversation_service()
    conv_id = await conv_svc.ensure_conversation(
        conversation_id,
        tenant_id=str(user_context.get("tenant_id") or "TENANT_DEFAULT"),
        user_key=str(user_context.get("employ_code") or "E_DEFAULT"),
        title=message if not conversation_id else None,
    )
    user_context["conversation_id"] = conv_id
    return conv_id


async def _build_initial_state(
    message: str,
    user_context: Dict[str, Any],
) -> AgentState:
    """构建 Agent 初始 state，从 MySQL 注入历史（不含当前句）。"""
    conversation_id = user_context.get("conversation_id")
    conv_svc = get_conversation_service()

    messages: List[Dict[str, Any]] = []
    if conversation_id:
        for turn in await conv_svc.get_history(conversation_id, limit=20):
            msg_type = "human" if turn["role"] == "user" else "ai"
            item: Dict[str, Any] = {
                "type": msg_type,
                "data": {"content": turn["content"]},
            }
            if turn.get("pinned"):
                item["pinned"] = True
            messages.append(item)

    messages.append({"type": "human", "data": {"content": message}})

    return {
        "messages": messages,
        "intent": "",
        "confidence": 0.0,
        "entities": {},
        "routing_target": "",
        "needs_clarification": False,
        "clarification_question": None,
        "clarification_type": "",
        "missing_slots": [],
        "rag_results": [],
        "graph_results": [],
        "db_results": {},
        "final_response": "",
        "token_usage": {},
        "reasoning_steps": [],
        "resolved_query": "",
        "plan_steps": [],
        "plan_current_step": 0,
        "plan_observations": {},
        "weekly_report_mode": False,
        "weekly_export_pending": False,
        "export_path": "",
        "user_context": user_context,
    }


async def _record_clarification_turn(
    conversation_id: int,
    user_message: str,
    clarification_question: str,
) -> None:
    conv_svc = get_conversation_service()
    await conv_svc.append_message(conversation_id, "user", user_message)
    await conv_svc.append_message(
        conversation_id,
        "assistant",
        clarification_question,
        pinned=True,
    )


async def _record_agent_turn(
    conversation_id: Optional[int],
    user_message: str,
    assistant_message: str,
) -> None:
    if not conversation_id:
        return
    conv_svc = get_conversation_service()
    await conv_svc.append_message(conversation_id, "user", user_message)
    await conv_svc.append_message(conversation_id, "assistant", assistant_message)


async def _run_agent_chat(
    message: str,
    conversation_id: Optional[int],
    user_context: Dict[str, Any],
) -> Tuple[ChatOutcomeKind, Dict[str, Any]]:
    """执行 Agent 对话，返回 (结果类型, 载荷)。"""
    agent_graph = get_agent_graph()
    conv_id = await _ensure_conversation(conversation_id, user_context, message)

    kind, result = await invoke_agent_graph(
        agent_graph,
        message=message,
        initial_state=await _build_initial_state(message, user_context),
        conversation_id=conv_id,
    )

    if kind == "clarification":
        await _record_clarification_turn(
            conv_id,
            message,
            result.get("clarification_question", "您具体想做什么？"),
        )
        return "clarification", result

    await _record_agent_turn(
        conv_id,
        message,
        result.get("final_response", ""),
    )

    return "agent", {
        "response": result.get("final_response", ""),
        "intent": result.get("intent", ""),
        "confidence": result.get("confidence", 0.0),
        "routing_target": result.get("routing_target", ""),
        "reasoning_steps": result.get("reasoning_steps", []),
        "conversation_id": conv_id,
        "export_path": result.get("export_path") or None,
    }


def _sse(event: str, data: Dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _prepare_agent_for_stream(
    message: str,
    conversation_id: Optional[int],
    user_context: Dict[str, Any],
) -> Tuple[ChatOutcomeKind, Union[Dict[str, Any], AgentState]]:
    """
    执行 Agent 前置流程（意图/RAG/图谱/DB），在 LLM 节点前停止。
    返回 clarification 载荷，或可供 astream 的 AgentState。
    """
    conv_id = await _ensure_conversation(conversation_id, user_context, message)

    prepare_graph = get_agent_prepare_graph()
    kind, payload = await invoke_prepare_graph(
        prepare_graph,
        message=message,
        initial_state=await _build_initial_state(message, user_context),
        conversation_id=conv_id,
    )

    if kind == "clarification":
        await _record_clarification_turn(
            conv_id,
            message,
            payload.get("clarification_question", "您具体想做什么？"),
        )
        return "clarification", payload

    return "ready", payload  # type: ignore[return-value]


def _get_user_context(
    tenant_code: Optional[str] = Header(None, alias="X-Tenant-Code"),
    employ_code: Optional[str] = Header(None, alias="X-Employ-Code"),
) -> Dict[str, Any]:
    """
    从请求头获取用户上下文

    说明：
    - 这些值由统一网关校验后注入
    - 如果没有网关，此方法也可以从前端请求体获取
    """
    return {
        "tenant_id": tenant_code or "TENANT_DEFAULT",  # 租户ID
        "employ_code": employ_code or "E_DEFAULT",    # 员工工号
    }


@router.post("/chat")
async def chat_with_agent(
    request: AgentRequest,
    tenant_code: Optional[str] = Header(None, alias="X-Tenant-Code"),
    employ_code: Optional[str] = Header(None, alias="X-Employ-Code"),
):
    """
    与Agent对话

    权限说明：
    - tenant_code: 租户编码，用于租户数据隔离
    - employ_code: 员工工号，用于日志追踪

    流程：
    1. 获取用户上下文（租户、员工）
    2. 检查是否有待处理的澄清
    3. 执行 Agent Graph
    4. 如果需要澄清，保存状态并返回澄清问题
    """
    user_context = {
        "tenant_id": tenant_code or "TENANT_DEFAULT",
        "employ_code": employ_code or "E_DEFAULT",
        "conversation_id": request.conversation_id,
    }

    kind, payload = await _run_agent_chat(
        request.message, request.conversation_id, user_context
    )

    if kind == "clarification":
        return ClarificationResponse(**payload)

    return AgentResponse(type="agent", **payload)


@router.post("/chat/stream")
async def chat_with_agent_stream(
    request: AgentRequest,
    tenant_code: Optional[str] = Header(None, alias="X-Tenant-Code"),
    employ_code: Optional[str] = Header(None, alias="X-Employ-Code"),
):
    """
    流式对话（SSE）。

    流程：Agent 前置节点（意图/RAG/图谱/DB）→ LLM astream 真 token → meta/done。

    事件类型：
    - token: {"delta": "..."}  LLM 真实 token 片段
    - clarification: 需用户澄清
    - meta: reasoning_steps 等元数据（在正文 token 之后）
    - done: 流结束
    - error: 错误信息
    """
    user_context = {
        "tenant_id": tenant_code or "TENANT_DEFAULT",
        "employ_code": employ_code or "E_DEFAULT",
        "conversation_id": request.conversation_id,
    }

    async def event_generator() -> AsyncIterator[str]:
        conv_id = request.conversation_id
        try:
            kind, payload = await _prepare_agent_for_stream(
                request.message, request.conversation_id, user_context
            )
            conv_id = int(user_context["conversation_id"])

            if kind == "clarification":
                yield _sse("clarification", payload)  # type: ignore[arg-type]
                yield _sse("done", {})
                return

            state: AgentState = payload  # type: ignore[assignment]
            full_response: List[str] = []

            async for delta in astream_llm_tokens(state):
                full_response.append(delta)
                yield _sse("token", {"delta": delta})

            state["final_response"] = "".join(full_response)
            append_llm_reasoning_step(state, streamed=True)
            state["final_response"] = maybe_export_weekly_report(
                state, state["final_response"]
            )

            from app.services.token_usage_service import persist_token_usage_from_state

            await persist_token_usage_from_state(state, conversation_id=conv_id)

            yield _sse(
                "meta",
                {
                    "intent": state.get("intent", ""),
                    "confidence": state.get("confidence", 0.0),
                    "routing_target": state.get("routing_target", ""),
                    "reasoning_steps": state.get("reasoning_steps", []),
                    "conversation_id": conv_id,
                    "resolved_query": state.get("resolved_query", ""),
                    "export_path": state.get("export_path") or None,
                },
            )
            await _record_agent_turn(
                conv_id,
                request.message,
                state.get("final_response", ""),
            )
            yield _sse("done", {})
        except Exception as exc:
            yield _sse("error", {"message": str(exc)})
            yield _sse("done", {})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/intents")
async def list_intents():
    """获取支持的意图类型"""
    from app.services.intent_router import IntentType

    return {
        "intents": [
            {"value": i.value, "description": i.name.replace("_", " ")}
            for i in IntentType
        ]
    }


@router.delete("/conversation/{conversation_id}/clarification")
async def clear_clarification(conversation_id: int):
    """清除会话的澄清状态（checkpointer thread + 旧版 Redis pending）。"""
    from app.services.session_manager import get_session_state

    session_state = get_session_state()
    session_state.clear_state(conversation_id)
    await clear_graph_thread(get_agent_graph(), conversation_id)
    await clear_graph_thread(get_agent_prepare_graph(), conversation_id)
    return {
        "status": "ok",
        "message": "澄清状态已清除",
        "clarification_backend": session_state.backend_name,
    }


@router.get("/session/backend")
async def get_session_backend():
    """查看澄清 pending 与 LangGraph checkpoint 存储后端。"""
    from app.agent.checkpointer import get_checkpoint_backend_name
    from app.services.session_manager import get_session_state

    session_state = get_session_state()
    return {
        "clarification_backend": session_state.backend_name,
        "graph_checkpoint_backend": get_checkpoint_backend_name(),
    }


@router.get("/exports/{filename}")
async def download_weekly_export(filename: str):
    """下载 Planner 导出的周报 Markdown。"""
    from pathlib import Path

    from fastapi.responses import FileResponse

    base = Path(__file__).resolve().parents[2] / "data" / "exports"
    path = (base / filename).resolve()
    if not str(path).startswith(str(base.resolve())):
        return {"error": "invalid path"}
    if not path.is_file():
        return {"error": "file not found"}
    return FileResponse(path, media_type="text/markdown", filename=filename)
