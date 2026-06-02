"""
LangGraph Agent 定义
"""
import logging
from functools import lru_cache
from typing import Annotated, AsyncIterator, List, Sequence, TypedDict

import operator
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.types import interrupt

from app.services.intent_router import IntentType

logger = logging.getLogger(__name__)


# ==================== Agent State ====================

class AgentState(TypedDict):
    """Agent状态"""
    messages: Annotated[Sequence[dict], operator.add]
    intent: str
    confidence: float
    entities: dict
    routing_target: str
    needs_clarification: bool
    clarification_question: str
    clarification_type: str  # intent | slot | ""
    missing_slots: list
    rag_results: list
    graph_results: list
    db_results: dict
    final_response: str
    token_usage: dict
    reasoning_steps: list  # ReAct推理步骤
    resolved_query: str  # 结合历史解析后的 standalone query（意图/RAG 共用）
    # Planner / 周报
    plan_steps: list
    plan_current_step: int
    plan_observations: dict
    weekly_report_mode: bool
    weekly_export_pending: bool
    export_path: str
    # 用户上下文 - 租户隔离
    user_context: dict  # {"tenant_id": "xxx", "employ_code": "xxx"}


# ==================== Agent Nodes ====================

async def _apply_clarification_resume(
    state: AgentState,
    user_reply: str,
    clar_type: str,
) -> AgentState:
    """interrupt resume 后：按澄清类型合并用户回复并继续下游。"""
    from app.services.conversation_context import agent_messages_to_history
    from app.services.intent_router import get_intent_router
    from app.services.slot_validation import (
        apply_slot_fill_fallback,
        merge_entities,
        normalize_entities,
    )

    question = state.get("clarification_question") or "您具体想做什么？"
    state["messages"] = list(state["messages"])
    state["messages"].append({
        "role": "assistant",
        "content": question,
        "type": "clarification",
    })
    state["messages"].append({"type": "human", "data": {"content": user_reply}})

    history = agent_messages_to_history(state["messages"], exclude_last=True)
    router = get_intent_router()

    if clar_type == "slot":
        new_entities, _ = await router._extract_entities(user_reply, history)
        merged = merge_entities(state.get("entities"), new_entities)
        merged = apply_slot_fill_fallback(
            merged,
            state.get("missing_slots") or [],
            user_reply,
        )
        state["entities"] = normalize_entities(merged)
        state["needs_clarification"] = False
        state["clarification_question"] = ""
        state["clarification_type"] = ""
        state["missing_slots"] = []
        state["reasoning_steps"].append({
            "step": "slot_resume",
            "thought": f"Checkpointer 续聊：继续补全参数，意图保持 {state.get('intent')}",
            "action": f"已合并实体: {list(state['entities'].keys())}",
        })
        return state

    if clar_type == "plan":
        from app.services.planner.weekly_report import parse_scope_from_message

        patch = parse_scope_from_message(user_reply)
        state["entities"] = normalize_entities(
            merge_entities(state.get("entities"), patch)
        )
        state["needs_clarification"] = False
        state["clarification_question"] = ""
        state["clarification_type"] = ""
        state["reasoning_steps"].append({
            "step": "plan_resume",
            "thought": "Checkpointer 续聊：继续周报 Planner",
            "action": f"实体: {list(state['entities'].keys())}",
        })
        return state

    intent_result = await router.recognize(user_reply, history=history)
    routing = intent_result.routing_target
    routing_str = routing.value if hasattr(routing, "value") else str(routing)
    state["intent"] = intent_result.intent.value
    state["confidence"] = intent_result.confidence
    state["entities"] = normalize_entities(intent_result.entities)
    state["routing_target"] = routing_str
    state["needs_clarification"] = intent_result.needs_clarification
    state["clarification_question"] = intent_result.clarification_question
    state["clarification_type"] = (
        "intent" if intent_result.needs_clarification else ""
    )
    state["missing_slots"] = []
    state["resolved_query"] = intent_result.resolved_query or user_reply
    state["reasoning_steps"].append({
        "step": "intent_clarification_resume",
        "thought": f"意图澄清续聊 → {intent_result.intent.value}",
        "action": f"置信度: {intent_result.confidence}",
    })
    return state


async def intent_recognition_node(state: AgentState) -> AgentState:
    """意图识别节点（澄清续聊由 clarification interrupt + checkpointer 处理）。"""
    from app.services.conversation_context import agent_messages_to_history
    from app.services.intent_router import get_intent_router
    from app.services.slot_validation import normalize_entities

    router = get_intent_router()
    last_message_data = state["messages"][-1]
    if isinstance(last_message_data, dict):
        if "content" in last_message_data:
            last_message = last_message_data["content"]
        elif "data" in last_message_data and isinstance(last_message_data["data"], dict):
            last_message = last_message_data["data"].get("content", "")
        else:
            last_message = str(last_message_data)
    else:
        last_message = getattr(last_message_data, "content", str(last_message_data))

    history = agent_messages_to_history(state["messages"], exclude_last=True)

    intent_result = await router.recognize(last_message, history=history)

    from app.services.token_usage_service import persist_intent_llm_usages

    await persist_intent_llm_usages(
        state,
        intent_result.llm_usages,
        recognized_intent=intent_result.intent.value,
    )

    routing = intent_result.routing_target
    routing_str = routing.value if hasattr(routing, "value") else str(routing)

    state["intent"] = intent_result.intent.value
    state["confidence"] = intent_result.confidence
    state["entities"] = normalize_entities(intent_result.entities)
    state["routing_target"] = routing_str
    state["needs_clarification"] = intent_result.needs_clarification
    state["clarification_question"] = intent_result.clarification_question
    state["clarification_type"] = (
        "intent" if intent_result.needs_clarification else ""
    )
    state["missing_slots"] = []
    state["resolved_query"] = intent_result.resolved_query or last_message
    state["reasoning_steps"].append({
        "step": "intent_recognition",
        "thought": f"识别到意图: {intent_result.intent.value}, 置信度: {intent_result.confidence}",
        "action": (
            f"路由目标: {routing_str}, "
            f"standalone: {state['resolved_query'][:40]}, "
            f"需要澄清: {intent_result.needs_clarification}"
        ),
    })

    return state


async def slot_validate_node(state: AgentState) -> AgentState:
    """路由前槽位校验：DB/CREATE/UPDATE/GRAPH 缺参则追问用户。"""
    from app.services.slot_validation import normalize_entities, validate_slots

    if state.get("needs_clarification"):
        return state

    intent = state.get("intent") or ""
    routing_target = state.get("routing_target") or "llm"
    entities = normalize_entities(state.get("entities"))

    passed, missing, question = validate_slots(intent, routing_target, entities)
    if passed:
        state["entities"] = entities
        state["missing_slots"] = []
        state["clarification_type"] = ""
        return state

    state["entities"] = entities
    state["needs_clarification"] = True
    state["clarification_type"] = "slot"
    state["missing_slots"] = missing
    state["clarification_question"] = question
    state["reasoning_steps"].append({
        "step": "slot_validate",
        "thought": f"意图 {intent} 缺少必要参数: {missing}",
        "action": f"追问用户: {question[:80]}",
    })
    return state


async def clarification_node(state: AgentState) -> AgentState:
    """澄清节点：interrupt 暂停，Command(resume=...) 后继续（P4 checkpointer）。"""
    if not state.get("needs_clarification"):
        return state

    clarification_question = state.get("clarification_question", "您具体想做什么？")
    clar_type = state.get("clarification_type") or "intent"
    conversation_id = (state.get("user_context") or {}).get("conversation_id")

    user_reply = interrupt({
        "clarification_question": clarification_question,
        "clarification_type": clar_type,
        "missing_slots": state.get("missing_slots") or [],
        "conversation_id": conversation_id,
    })

    state["reasoning_steps"].append({
        "step": "clarification_interrupt",
        "thought": "图 interrupt 暂停，等待用户回复",
        "action": f"[{clar_type}] {clarification_question[:80]}",
    })

    return await _apply_clarification_resume(state, str(user_reply), clar_type)


async def plan_executor_node(state: AgentState) -> AgentState:
    """周报 Planner：RAG 规范 → 查数 → ReAct → 准备 LLM 生成。"""
    rt = state.get("routing_target", "")
    if rt != "planner" or state.get("intent") != "weekly_summary":
        return state
    if state.get("needs_clarification"):
        return state
    if state.get("weekly_report_mode"):
        return state

    from app.services.planner.plan_executor import execute_weekly_plan
    from app.services.planner.task_planner import build_weekly_plan

    if not state.get("plan_steps"):
        state["plan_steps"] = build_weekly_plan(state.get("entities"))
    if state.get("plan_observations") is None:
        state["plan_observations"] = {}

    resume_step = "query_data" if state.get("plan_current_step", 0) > 0 else "rag_guide"
    if state.get("plan_observations", {}).get("rag_count"):
        resume_step = "query_data"

    await execute_weekly_plan(state, from_step=resume_step)
    return state


def maybe_export_weekly_report(state: AgentState, content: str) -> str:
    """LLM 完成后导出 Markdown，并在回复末尾附上路径说明。"""
    if not state.get("weekly_report_mode") and not state.get("weekly_export_pending"):
        return content

    from app.services.planner.weekly_report import export_markdown

    obs = state.get("plan_observations") or {}
    week_start = obs.get("week_start") or ""
    week_end = obs.get("week_end") or ""
    user_context = state.get("user_context") or {}
    rel_path = export_markdown(
        content,
        employ_code=str(user_context.get("employ_code") or "user"),
        week_start=week_start,
        week_end=week_end,
    )
    state["export_path"] = rel_path
    state["weekly_export_pending"] = False
    state["reasoning_steps"].append({
        "step": "plan_export",
        "thought": "Planner: 导出 Markdown 周报",
        "action": rel_path,
    })
    suffix = f"\n\n---\n📄 周报已导出：`{rel_path}`"
    return content + suffix


async def rag_search_node(state: AgentState) -> AgentState:
    """
    RAG检索节点 - 知识文档检索

    说明：
    - 只检索知识文档（操作指南、FAQ、制度文件）
    - 权限：租户隔离（tenant_id）
    """
    from app.services.rag_service import get_rag_service

    if state["routing_target"] != "rag":
        return state

    rag_service = get_rag_service()
    from app.services.conversation_context import agent_messages_to_history

    search_query = state.get("resolved_query") or ""
    if not search_query:
        last_msg = state["messages"][-1]
        search_query = (
            last_msg.get("content", "")
            if isinstance(last_msg, dict)
            else last_msg.content
        )

    history = agent_messages_to_history(state["messages"], exclude_last=True)

    # 获取租户上下文
    user_context = state.get("user_context", {})
    tenant_id = user_context.get("tenant_id", "TENANT_DEFAULT")

    results = await rag_service.similarity_search(
        query=search_query,
        tenant_id=tenant_id,
        history=history,
        resolved_query=state.get("resolved_query") or None,
    )

    state["rag_results"] = results
    logger.info(f"RAG检索结果: {results}")
    state["reasoning_steps"].append({
        "step": "rag_search",
        "thought": f"执行知识文档检索，找到 {len(results)} 条相关结果",
        "action": f"租户: {tenant_id}, 向量相似度检索完成",
    })



    return state


async def graph_traverse_node(state: AgentState) -> AgentState:
    """图谱遍历节点"""
    from app.services.graph_service import get_graph_service
    from app.services.slot_validation import (
        apply_clarification_to_state,
        normalize_entities,
        validate_slots,
    )

    routing = state.get("routing_target", "llm")
    rt = routing.value if hasattr(routing, "value") else str(routing)
    if rt not in ("graph", "llm"):
        return state

    intent = state.get("intent") or ""
    entities = normalize_entities(state.get("entities"))

    if rt == "graph":
        passed, missing, question = validate_slots(intent, rt, entities)
        if not passed:
            state["entities"] = entities
            apply_clarification_to_state(
                state,
                missing_slots=missing,
                clarification_question=question,
                source_step="graph_validate",
            )
            return state

    graph_service = await get_graph_service()
    results: dict = {}

    person = entities.get("employee_id") or entities.get("person_name")
    if person and rt == "graph":
        tasks = await graph_service.find_employee_tasks(person)
        projects = await graph_service.find_employee_projects(person)
        results = {"tasks": tasks, "projects": projects, "employee_ref": person}

    state["graph_results"] = results
    state["reasoning_steps"].append({
        "step": "graph_traverse",
        "thought": "执行图谱查询" if results else "图谱查询无匹配实体或未执行",
        "action": f"employee_ref={person or 'N/A'}",
    })

    return state


def _handle_service_clarification(
    state: AgentState,
    result: dict,
    *,
    source_step: str,
) -> bool:
    """业务层缺参 → 写入 state 并返回 True。"""
    from app.services.slot_validation import (
        apply_clarification_to_state,
        clarification_from_service_result,
        result_needs_clarification,
    )

    if not result_needs_clarification(result):
        return False

    missing, question = clarification_from_service_result(result)
    apply_clarification_to_state(
        state,
        missing_slots=missing,
        clarification_question=question,
        source_step=source_step,
    )
    state["db_results"] = result
    return True


async def db_query_node(state: AgentState) -> AgentState:
    """
    业务服务节点

    根据识别的意图和实体，调用对应的业务微服务
    Agent 本身不执行业务逻辑，只负责 AI 能力

    权限说明：
    - 租户隔离由微服务内部处理
    - 此处传递 tenant_id 和 employ_code
    """
    if state.get("routing_target") not in ("db", "create", "update"):
        return state

    intent = state["intent"]
    entities = state["entities"]
    user_context = state.get("user_context", {})

    from app.services.business_service_proxy import get_business_service_proxy

    business_proxy = get_business_service_proxy()

    try:
        result = await business_proxy.execute(
            intent,
            entities,
            user_context,
            routing_target=state.get("routing_target"),
        )
        if _handle_service_clarification(state, result, source_step="db_validate"):
            return state

        state["db_results"] = result
        state["reasoning_steps"].append({
            "step": "db_query",
            "thought": f"调用业务服务: {result.get('service', 'unknown')}.{result.get('operation', '')}",
            "action": f"租户: {user_context.get('tenant_id', 'N/A')}, 结果: {result.get('message', '执行成功')}",
        })
    except Exception as e:
        logger.error(f"业务服务调用失败: {e}")
        state["db_results"] = {
            "success": False,
            "error": str(e),
            "message": "业务服务调用失败"
        }
        state["reasoning_steps"].append({
            "step": "db_query",
            "thought": "业务服务调用失败",
            "action": f"错误: {str(e)}",
        })

    return state


# ==================== LLM 推理（共享：ainvoke / astream） ====================

_LLM_SYSTEM_PROMPT = """你是一个企业任务协同助手，负责帮助用户完成以下任务：
- 任务管理（创建、查询、更新）
- 项目协作
- 知识问答

请根据用户问题和上下文信息，给出专业、准确的回答。
如果涉及具体数据，请以友好、易懂的方式呈现。

注意：
- 如果上下文信息中有业务执行结果，请直接展示给用户
- 如果操作成功，用鼓励的语气回复
- 如果操作失败，用关心的语气说明问题并给出建议
"""


def _get_last_user_message(state: AgentState) -> str:
    """从 messages 中取最近一条用户问题文本。"""
    for msg in reversed(state["messages"]):
        if isinstance(msg, dict):
            if msg.get("type") == "clarification" or msg.get("role") == "assistant":
                continue
            if "content" in msg:
                return str(msg["content"])
            if "data" in msg and isinstance(msg["data"], dict):
                return str(msg["data"].get("content", ""))
        else:
            content = getattr(msg, "content", None)
            if content:
                return str(content)
    return ""


def _build_llm_context(state: AgentState) -> str:
    context_parts: List[str] = []

    if state.get("rag_results"):
        rag_hits = [
            r for r in state["rag_results"]
            if r.get("type") != "optimization_info"
        ]
        rag_lines = []
        for r in rag_hits:
            title = r.get("parent_title") or (r.get("metadata") or {}).get("title", "")
            prefix = f"[{title}] " if title else ""
            rag_lines.append(f"- {prefix}{r.get('content', '')[:300]}")
        rag_text = "\n".join(rag_lines)
        if rag_text:
            context_parts.append(f"【RAG检索结果】\n{rag_text}")

    if state.get("graph_results"):
        context_parts.append(f"【图谱查询结果】\n{state['graph_results']}")

    if state.get("db_results"):
        context_parts.append(f"【业务服务结果】\n{state['db_results']}")

    return "\n\n".join(context_parts) if context_parts else "无额外上下文"


def build_llm_prompt_messages(state: AgentState) -> List[BaseMessage]:
    """构建送入 Chat 模型的消息列表。"""
    if state.get("weekly_report_mode"):
        from app.services.planner.weekly_report import (
            build_weekly_llm_human_prompt,
            build_weekly_llm_system_prompt,
        )

        obs = state.get("plan_observations") or {}
        rag_hits = [
            r for r in (state.get("rag_results") or [])
            if r.get("type") != "optimization_info"
        ]
        rag_chunks = [r.get("content", "") for r in rag_hits]
        weekly_data = obs.get("weekly_data") or (state.get("db_results") or {}).get("data") or {}
        user_context = state.get("user_context") or {}
        human = build_weekly_llm_human_prompt(
            week_start=obs.get("week_start") or "",
            week_end=obs.get("week_end") or "",
            rag_chunks=rag_chunks,
            weekly_data=weekly_data,
            user_name=str(user_context.get("employ_code") or ""),
        )
        return [
            SystemMessage(content=build_weekly_llm_system_prompt()),
            HumanMessage(content=human),
        ]

    context = _build_llm_context(state)
    user_question = _get_last_user_message(state)
    human_prompt = f"""用户问题: {user_question}

上下文信息:
{context}

请回答用户问题。"""
    return [
        SystemMessage(content=_LLM_SYSTEM_PROMPT),
        HumanMessage(content=human_prompt),
    ]


@lru_cache()
def get_chat_llm() -> ChatOpenAI:
    from app.config import get_settings

    settings = get_settings()
    return ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url or None,
        temperature=0.7,
    )


def _extract_chunk_text(content: object) -> str:
    """从 LangChain AIMessageChunk 中取出文本增量。"""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "".join(parts)
    return str(content)


async def ainvoke_llm_response(state: AgentState) -> str:
    """非流式：一次性生成完整回复。"""
    from app.config import get_settings
    from app.services.llm_usage import build_usage_for_llm_call, extract_usage_from_llm_message

    settings = get_settings()
    messages = build_llm_prompt_messages(state)
    llm = get_chat_llm()
    response = await llm.ainvoke(messages)
    text = _extract_chunk_text(response.content)
    usage = build_usage_for_llm_call(
        extract_usage_from_llm_message(response),
        prompt_messages=messages,
        completion_text=text,
    )
    state["token_usage"] = {**usage, "model": settings.openai_model}
    return text


async def astream_llm_tokens(state: AgentState) -> AsyncIterator[str]:
    """流式：按 LLM 真实 token 产出文本增量。"""
    from app.config import get_settings
    from app.services.llm_usage import build_usage_for_llm_call, extract_usage_from_llm_message

    settings = get_settings()
    messages = build_llm_prompt_messages(state)
    llm = get_chat_llm()
    provider_usage: dict = {}
    parts: List[str] = []

    async for chunk in llm.astream(messages):
        chunk_usage = extract_usage_from_llm_message(chunk)
        if chunk_usage.get("total_tokens", 0) > 0:
            provider_usage = chunk_usage
        text = _extract_chunk_text(chunk.content)
        if text:
            parts.append(text)
            yield text

    usage = build_usage_for_llm_call(
        provider_usage,
        prompt_messages=messages,
        completion_text="".join(parts),
    )
    state["token_usage"] = {**usage, "model": settings.openai_model}


def append_llm_reasoning_step(state: AgentState, *, streamed: bool = False) -> None:
    """记录 LLM 推理步骤（流式/非流式共用）。"""
    state["reasoning_steps"].append({
        "step": "llm_reasoning",
        "thought": "基于所有上下文进行LLM推理生成回答",
        "action": "流式回答生成完成" if streamed else "回答生成完成",
    })


async def llm_reasoning_node(state: AgentState) -> AgentState:
    """LLM推理节点（非流式路径）"""
    from app.services.token_usage_service import persist_token_usage_from_state

    state["final_response"] = maybe_export_weekly_report(
        state, await ainvoke_llm_response(state)
    )
    append_llm_reasoning_step(state, streamed=False)
    await persist_token_usage_from_state(state)
    return state


# ==================== Agent Graph ====================

def create_agent_graph(*, interrupt_before_llm: bool = False, checkpointer=None):
    """创建 Agent 工作流图。

    interrupt_before_llm=True 时在进入 llm_reasoning 前停止，
    供 SSE 接口先跑完 RAG/图谱/DB，再单独 astream LLM。
    澄清使用 clarification 节点内 interrupt() + checkpointer。
    """
    if checkpointer is None:
        from app.agent.checkpointer import ensure_checkpointer
        checkpointer = ensure_checkpointer()

    workflow = StateGraph(AgentState)
    
    # 添加节点
    workflow.add_node("intent_recognition", intent_recognition_node)
    workflow.add_node("slot_validate", slot_validate_node)
    workflow.add_node("clarification", clarification_node)
    workflow.add_node("rag_search", rag_search_node)
    workflow.add_node("graph_traverse", graph_traverse_node)
    workflow.add_node("db_query", db_query_node)
    workflow.add_node("plan_executor", plan_executor_node)
    workflow.add_node("llm_reasoning", llm_reasoning_node)
    
    # 设置入口
    workflow.set_entry_point("intent_recognition")
    
    # 条件路由
    def route_after_intent(state: AgentState) -> str:
        """意图识别后：意图澄清 或 进入槽位校验。"""
        if state.get("needs_clarification"):
            return "clarification"
        return "slot_validate"

    def route_after_slot_validate(state: AgentState) -> str:
        """槽位校验后：参数澄清 或 进入业务路由。"""
        if state.get("needs_clarification"):
            return "clarification"

        routing_target = state.get("routing_target", "llm")
        rt = (
            routing_target.value
            if hasattr(routing_target, "value")
            else str(routing_target)
        )

        if rt == "rag":
            return "rag_search"
        if rt == "planner":
            return "plan_executor"
        if rt == "graph":
            return "graph_traverse"
        if rt in ("db", "create", "update"):
            return "db_query"
        return "llm_reasoning"

    workflow.add_conditional_edges(
        "intent_recognition",
        route_after_intent,
        {
            "clarification": "clarification",
            "slot_validate": "slot_validate",
        },
    )

    workflow.add_conditional_edges(
        "slot_validate",
        route_after_slot_validate,
        {
            "clarification": "clarification",
            "rag_search": "rag_search",
            "plan_executor": "plan_executor",
            "graph_traverse": "graph_traverse",
            "db_query": "db_query",
            "llm_reasoning": "llm_reasoning",
        },
    )
    
    # 澄清 resume 后 → 槽位校验（plan/slot/intent 已在上游节点合并）
    workflow.add_edge("clarification", "slot_validate")

    def route_after_plan(state: AgentState) -> str:
        if state.get("needs_clarification"):
            return "clarification"
        return "llm_reasoning"

    workflow.add_conditional_edges(
        "plan_executor",
        route_after_plan,
        {"clarification": "clarification", "llm_reasoning": "llm_reasoning"},
    )

    def route_after_rag(state: AgentState) -> str:
        if state.get("needs_clarification"):
            return "clarification"
        return "llm_reasoning"

    def route_after_graph(state: AgentState) -> str:
        if state.get("needs_clarification"):
            return "clarification"
        return "llm_reasoning"

    def route_after_db(state: AgentState) -> str:
        if state.get("needs_clarification"):
            return "clarification"
        return "llm_reasoning"

    workflow.add_conditional_edges(
        "rag_search",
        route_after_rag,
        {"clarification": "clarification", "llm_reasoning": "llm_reasoning"},
    )
    workflow.add_conditional_edges(
        "graph_traverse",
        route_after_graph,
        {"clarification": "clarification", "llm_reasoning": "llm_reasoning"},
    )
    workflow.add_conditional_edges(
        "db_query",
        route_after_db,
        {"clarification": "clarification", "llm_reasoning": "llm_reasoning"},
    )

    workflow.add_edge("llm_reasoning", END)

    compile_kwargs: dict = {"checkpointer": checkpointer}
    if interrupt_before_llm:
        compile_kwargs["interrupt_before"] = ["llm_reasoning"]
    return workflow.compile(**compile_kwargs)


_agent_graph = None
_agent_prepare_graph = None


def init_agent_graphs() -> None:
    """lifespan 内 checkpointer 就绪后编译图（替代 lru_cache）。"""
    global _agent_graph, _agent_prepare_graph
    from app.agent.checkpointer import get_checkpointer

    cp = get_checkpointer()
    _agent_graph = create_agent_graph(interrupt_before_llm=False, checkpointer=cp)
    _agent_prepare_graph = create_agent_graph(
        interrupt_before_llm=True, checkpointer=cp
    )


def get_agent_graph():
    """获取完整 Agent 图（含 LLM 节点，用于非流式 /chat）。"""
    global _agent_graph
    if _agent_graph is None:
        init_agent_graphs()
    return _agent_graph


def get_agent_prepare_graph():
    """获取预处理图（在 LLM 节点前中断，用于 /chat/stream）。"""
    global _agent_prepare_graph
    if _agent_prepare_graph is None:
        init_agent_graphs()
    return _agent_prepare_graph
