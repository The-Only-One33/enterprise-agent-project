"""
Query 优化模块 - 提升 RAG 检索效果

包含：
1. Contextualize: 多轮 → standalone query（意图/RAG 共用）
2. Query Rewriting: 口语化 → 检索表述
3. Query Expansion / HyDE
"""
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from app.config import get_settings
from app.core.logging import get_logger
from app.services.conversation_context import (
    HistoryTurn,
    format_history_for_prompt,
    should_contextualize,
    trim_for_rag,
)

logger = get_logger(__name__)
settings = get_settings()


class QueryOptimizer:
    """Query 优化器"""

    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url or None,
            temperature=0.2,
        )
        self._setup_prompts()

    def _setup_prompts(self):
        self.contextualize_prompt = ChatPromptTemplate.from_messages([
            ("system", """你是企业 Agent 的「查询上下文解析」专家。
根据对话历史，将用户「当前输入」改写成一条**可独立理解**的完整表述（standalone query）。

要求：
1. 必须结合历史补全指代（「那/这/它/处理一下/继续」等）
2. 保留用户真实意图，不要臆造未提及的业务对象
3. 输出一条简洁中文陈述句，30字以内，不要 JSON、不要解释
4. 若当前输入已完整清晰，可轻微规范化后原样输出

示例：
历史: 用户: 任务创建流程是什么？  助手: （介绍了创建步骤）
当前: 那帮我处理一下
输出: 帮我在系统中创建任务

历史: 用户: 张三的项目进度  助手: ...
当前: 继续查他的任务
输出: 查询张三负责的任务列表
"""),
            ("human", """对话历史：
{conversation_history}

当前用户输入：{current_input}

请输出 standalone query："""),
        ])
        self.contextualize_chain = self.contextualize_prompt | self.llm

        self.rewrite_prompt = ChatPromptTemplate.from_messages([
            ("system", """你是一个企业知识库查询优化专家。
将用户的口语化表达转换为正式的知识库检索查询。

要求：
1. 提取核心意图，删除口语化填充词
2. 转换为关键词组合，便于向量检索
3. 保持语义完整，不改变原意
4. 输出简洁，控制在20字以内

示例：
- "我想查一下怎么创建任务" → "任务创建流程 操作指南"
- "有没有关于项目管理的规定啊" → "项目管理规范 制度文件"
"""),
            ("human", "用户输入: {user_input}"),
        ])
        self.rewrite_chain = self.rewrite_prompt | self.llm

        self.expand_prompt = ChatPromptTemplate.from_messages([
            ("system", """你是一个企业知识库检索专家。
根据用户查询，生成3-5个相关检索词，用于多路召回。
输出 JSON 数组格式，每个扩展词10字以内。

示例：
输入: "如何创建任务"
输出: ["任务创建", "新建任务步骤", "任务创建流程", "新建任务方法", "创建任务指南"]
"""),
            ("human", "查询: {query}"),
        ])
        self.expand_chain = self.expand_prompt | self.llm

        self.hyde_prompt = ChatPromptTemplate.from_messages([
            ("system", """根据用户问题，生成一个假设的知识库文档片段（约100字）。"""),
            ("human", "用户问题: {question}"),
        ])
        self.hyde_chain = self.hyde_prompt | self.llm

    async def contextualize(
        self,
        current_input: str,
        history: Optional[List[HistoryTurn]] = None,
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        """
        多轮上下文 → standalone query。
        无历史或无需解析时直接返回原句。
        """
        trimmed = trim_for_rag(history or [])
        if not should_contextualize(current_input, trimmed):
            return current_input.strip(), None

        try:
            from app.services.llm_usage import build_llm_usage_record

            response = await self.contextualize_chain.ainvoke({
                "conversation_history": format_history_for_prompt(trimmed),
                "current_input": current_input.strip(),
            })
            resolved = (response.content or "").strip().strip('"').strip("'")
            if not resolved:
                return current_input.strip(), None

            usage = build_llm_usage_record(
                response,
                stage="query_contextualize",
                model=settings.openai_model,
                prompt_text=current_input,
                completion_text=resolved,
            )
            logger.info(
                "query_contextualized",
                original=current_input[:40],
                resolved=resolved[:40],
            )
            return resolved, usage
        except Exception as e:
            logger.warning(f"Query contextualize failed, using original: {e}")
            return current_input.strip(), None

    async def rewrite(self, query: str) -> str:
        try:
            response = await self.rewrite_chain.ainvoke({"user_input": query})
            rewritten = response.content.strip()
            logger.info("query_rewrite", original=query[:30], rewritten=rewritten[:30])
            return rewritten
        except Exception as e:
            logger.warning(f"Query rewrite failed, using original: {e}")
            return query

    async def expand(self, query: str, num_expansions: int = 5) -> List[str]:
        try:
            import json
            import re

            response = await self.expand_chain.ainvoke({"query": query})
            json_match = re.search(r"\[.*\]", response.content, re.DOTALL)
            if json_match:
                expansions = json.loads(json_match.group())
                return expansions[:num_expansions]
            return [q.strip() for q in response.content.split(",") if q.strip()][
                :num_expansions
            ]
        except Exception as e:
            logger.warning(f"Query expand failed, using original: {e}")
            return [query]

    async def generate_hypothetical_document(self, question: str) -> str:
        try:
            response = await self.hyde_chain.ainvoke({"question": question})
            return response.content.strip()
        except Exception as e:
            logger.warning(f"HyDE generation failed: {e}")
            return question

    async def optimize(
        self,
        query: str,
        strategy: str = "full",
        history: Optional[List[HistoryTurn]] = None,
        *,
        resolved_query: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        综合优化。
        resolved_query: 若意图阶段已 contextualize，传入以避免重复 LLM。
        """
        result: Dict[str, Any] = {
            "original": query,
            "resolved": query,
            "rewritten": query,
            "expanded": [],
            "hyde_doc": "",
            "final_queries": [query],
        }

        base = resolved_query
        if not base and history:
            base, _ = await self.contextualize(query, history)
        elif not base:
            base = query.strip()

        result["resolved"] = base

        if strategy in ["rewrite", "expand", "full"]:
            result["rewritten"] = await self.rewrite(base)

        if strategy in ["expand", "full"]:
            result["expanded"] = await self.expand(result["rewritten"])
            result["final_queries"] = [result["rewritten"]] + result["expanded"]

        if strategy in ["hyde", "full"]:
            result["hyde_doc"] = await self.generate_hypothetical_document(base)
            result["final_queries"].append(result["hyde_doc"])

        logger.info(
            "query_optimized",
            strategy=strategy,
            resolved=result["resolved"][:30],
            final_count=len(result["final_queries"]),
        )
        return result


_optimizer: Optional[QueryOptimizer] = None


def get_query_optimizer() -> QueryOptimizer:
    global _optimizer
    if _optimizer is None:
        _optimizer = QueryOptimizer()
    return _optimizer
