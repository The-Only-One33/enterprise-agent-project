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
    rag_results: list
    graph_results: list
    db_results: dict
    final_response: str
    token_usage: dict
    reasoning_steps: list  # ReAct推理步骤
    # 用户上下文 - 租户隔离
    user_context: dict  # {"tenant_id": "xxx", "employ_code": "xxx"}


# ==================== Agent Nodes ====================

async def intent_recognition_node(state: AgentState) -> AgentState:
    """意图识别节点"""
    from app.services.intent_router import get_intent_router
    
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
    
    intent_result = await router.recognize(last_message)
    
    
    state["intent"] = intent_result.intent.value
    state["confidence"] = intent_result.confidence
    state["entities"] = intent_result.entities
    state["routing_target"] = intent_result.routing_target
    state["needs_clarification"] = intent_result.needs_clarification
    state["clarification_question"] = intent_result.clarification_question
    state["reasoning_steps"].append({
        "step": "intent_recognition",
        "thought": f"识别到意图: {intent_result.intent.value}, 置信度: {intent_result.confidence}",
        "action": f"路由目标: {intent_result.routing_target}, 需要澄清: {intent_result.needs_clarification}",
    })
    
    return state


async def clarification_node(state: AgentState) -> AgentState:
    """意图澄清节点 - 当置信度低时返回澄清问题给用户"""
    if not state.get("needs_clarification"):
        # 不需要澄清，直接返回
        return state
    
    clarification_question = state.get("clarification_question", "您具体想做什么？")
    
    # 添加助手消息，询问用户确认意图
    state["messages"] = list(state["messages"])  # 复制列表
    state["messages"].append({
        "role": "assistant",
        "content": clarification_question,
        "type": "clarification",
    })
    
    state["reasoning_steps"].append({
        "step": "clarification",
        "thought": "置信度较低，需要用户确认意图",
        "action": f"发送澄清问题: {clarification_question}",
    })
    
    # 注意：流程会在这里暂停，等待用户回复
    # 用户回复后会重新进入意图识别节点
    return state


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
    last_msg = state["messages"][-1]
    query = last_msg.get("content", "") if isinstance(last_msg, dict) else last_msg.content

    # 获取租户上下文
    user_context = state.get("user_context", {})
    tenant_id = user_context.get("tenant_id", "TENANT_DEFAULT")

    results = await rag_service.similarity_search(
        query=query,
        tenant_id=tenant_id,  # 租户隔离
        top_k=5,
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
    
    if state["routing_target"] != "graph" and state["routing_target"] != "llm":
        return state
    
    graph_service = await get_graph_service()
    entities = state["entities"]
    
    results = []
    
    # 根据实体类型执行不同查询
    if "employee_id" in entities:
        employee_id = entities["employee_id"]
        tasks = await graph_service.find_employee_tasks(employee_id)
        projects = await graph_service.find_employee_projects(employee_id)
        results = {"tasks": tasks, "projects": projects}
    
    state["graph_results"] = results
    state["reasoning_steps"].append({
        "step": "graph_traverse",
        "thought": f"执行图谱查询，找到相关实体",
        "action": "Neo4j多跳查询完成",
    })
    
    return state


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

    # 调用业务服务代理
    from app.services.business_service_proxy import get_business_service_proxy
    business_proxy = get_business_service_proxy()

    try:
        result = await business_proxy.execute(intent, entities, user_context)
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
    llm = get_chat_llm()
    response = await llm.ainvoke(build_llm_prompt_messages(state))
    return _extract_chunk_text(response.content)


async def astream_llm_tokens(state: AgentState) -> AsyncIterator[str]:
    """流式：按 LLM 真实 token 产出文本增量。"""
    llm = get_chat_llm()
    async for chunk in llm.astream(build_llm_prompt_messages(state)):
        text = _extract_chunk_text(chunk.content)
        if text:
            yield text


def append_llm_reasoning_step(state: AgentState, *, streamed: bool = False) -> None:
    """记录 LLM 推理步骤（流式/非流式共用）。"""
    state["reasoning_steps"].append({
        "step": "llm_reasoning",
        "thought": "基于所有上下文进行LLM推理生成回答",
        "action": "流式回答生成完成" if streamed else "回答生成完成",
    })


async def llm_reasoning_node(state: AgentState) -> AgentState:
    """LLM推理节点（非流式路径）"""
    state["final_response"] = await ainvoke_llm_response(state)
    append_llm_reasoning_step(state, streamed=False)
    return state


# ==================== Agent Graph ====================

def create_agent_graph(*, interrupt_before_llm: bool = False):
    """创建 Agent 工作流图。

    interrupt_before_llm=True 时在进入 llm_reasoning 前停止，
    供 SSE 接口先跑完 RAG/图谱/DB，再单独 astream LLM。
    """
    workflow = StateGraph(AgentState)
    
    # 添加节点
    workflow.add_node("intent_recognition", intent_recognition_node)
    workflow.add_node("clarification", clarification_node)
    workflow.add_node("rag_search", rag_search_node)
    workflow.add_node("graph_traverse", graph_traverse_node)
    workflow.add_node("db_query", db_query_node)
    workflow.add_node("llm_reasoning", llm_reasoning_node)
    
    # 设置入口
    workflow.set_entry_point("intent_recognition")
    
    # 条件路由
    def route_after_intent(state: AgentState) -> str:
        """意图识别后的路由"""
        # 首先检查是否需要澄清
        if state.get("needs_clarification"):
            return "clarification"
        
        routing_target = state.get("routing_target", "llm")
        
        if routing_target == "rag":
            return "rag_search"
        elif routing_target == "graph":
            return "graph_traverse"
        elif routing_target in ("db", "create", "update"):
            return "db_query"
        else:
            return "llm_reasoning"
    
    # 添加边
    workflow.add_conditional_edges(
        "intent_recognition",
        route_after_intent,
        {
            "clarification": "clarification",
            "rag_search": "rag_search",
            "graph_traverse": "graph_traverse",
            "db_query": "db_query",
            "llm_reasoning": "llm_reasoning",
        }
    )
    
    # 澄清节点 → 结束，等待用户下次请求
    workflow.add_edge("clarification", END)
    
    # RAG和图谱结果汇总到LLM
    workflow.add_edge("rag_search", "llm_reasoning")
    workflow.add_edge("graph_traverse", "llm_reasoning")
    workflow.add_edge("db_query", "llm_reasoning")
    
    # 结束
    workflow.add_edge("llm_reasoning", END)

    if interrupt_before_llm:
        return workflow.compile(interrupt_before=["llm_reasoning"])
    return workflow.compile()


@lru_cache()
def get_agent_graph():
    """获取完整 Agent 图（含 LLM 节点，用于非流式 /chat）。"""
    return create_agent_graph(interrupt_before_llm=False)


@lru_cache()
def get_agent_prepare_graph():
    """获取预处理图（在 LLM 节点前中断，用于 /chat/stream）。"""
    return create_agent_graph(interrupt_before_llm=True)
