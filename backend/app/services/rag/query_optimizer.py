"""
Query 优化模块 - 提升 RAG 检索效果

包含以下优化策略：
1. Query Rewriting: 口语化转正式表述
2. Query Expansion: 多路召回扩展
3. HyDE: 假设文档增强检索
"""
from typing import List, Dict, Any, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class QueryOptimizer:
    """
    Query 优化器 - 提供多种查询优化策略
    """

    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url or None,
            temperature=0.3,  # 适度随机，保持创造性
        )
        self._setup_prompts()

    def _setup_prompts(self):
        """设置提示模板"""

        # 1. Query Rewriting: 口语化转正式表述
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
- "那个OKR是啥意思来着" → "OKR目标管理 定义"
- "怎么给任务打分来着" → "任务评分标准 打分规则"
"""),
            ("human", "用户输入: {user_input}"),
        ])
        self.rewrite_chain = self.rewrite_prompt | self.llm

        # 2. Query Expansion: 多路召回扩展
        self.expand_prompt = ChatPromptTemplate.from_messages([
            ("system", """你是一个企业知识库检索专家。
根据用户查询，生成3-5个相关检索词，用于多路召回。

要求：
1. 保留原始查询意图
2. 生成不同角度的变体（同义词、上下位词、简称等）
3. 每个扩展词控制在10字以内
4. 输出JSON数组格式

示例：
输入: "如何创建任务"
输出: ["任务创建", "新建任务步骤", "任务创建流程", "新建任务方法", "创建任务指南"]
"""),
            ("human", "查询: {query}"),
        ])
        self.expand_chain = self.expand_prompt | self.llm

        # 3. HyDE: 假设文档生成
        self.hyde_prompt = ChatPromptTemplate.from_messages([
            ("system", """你是一个企业知识库文档撰写专家。
根据用户问题，生成一个假设的知识库文档片段。

要求：
1. 模拟真实的知识文档风格（制度文件、操作指南、FAQ等）
2. 内容准确、格式规范
3. 长度控制在100字左右
4. 不需要完整的答案，只需生成可能被检索到的文档片段

示例：
输入: "任务评分标准是什么"
输出: "【任务评分标准】优秀(90-100分)：工作成果超出预期...良好(80-89分)：按时按质完成...合格(60-79分)：基本达到要求..."
"""),
            ("human", "用户问题: {question}"),
        ])
        self.hyde_chain = self.hyde_prompt | self.llm

    async def rewrite(self, query: str) -> str:
        """
        Query Rewriting: 口语化转正式表述

        Args:
            query: 原始用户输入

        Returns:
            优化后的检索查询
        """
        try:
            response = await self.rewrite_chain.ainvoke({"user_input": query})
            rewritten = response.content.strip()
            logger.info("query_rewrite", original=query[:30], rewritten=rewritten[:30])
            return rewritten
        except Exception as e:
            logger.warning(f"Query rewrite failed, using original: {e}")
            return query

    async def expand(self, query: str, num_expansions: int = 5) -> List[str]:
        """
        Query Expansion: 多路召回扩展

        Args:
            query: 原始查询或已改写的查询
            num_expansions: 扩展数量

        Returns:
            扩展后的查询列表
        """
        try:
            response = await self.expand_chain.ainvoke({"query": query})

            # 解析 JSON 数组
            import json
            import re
            json_match = re.search(r'\[.*\]', response.content, re.DOTALL)
            if json_match:
                expansions = json.loads(json_match.group())
                # 限制数量
                expansions = expansions[:num_expansions]
                logger.info("query_expand", original=query[:20], expansions_count=len(expansions))
                return expansions
            else:
                # 兜底：按逗号分割
                expansions = [q.strip() for q in response.content.split(',') if q.strip()]
                return expansions[:num_expansions]
        except Exception as e:
            logger.warning(f"Query expand failed, using original: {e}")
            return [query]

    async def generate_hypothetical_document(self, question: str) -> str:
        """
        HyDE: 生成假设文档

        Args:
            question: 用户问题

        Returns:
            假设的文档片段
        """
        try:
            response = await self.hyde_chain.ainvoke({"question": question})
            hyde_doc = response.content.strip()
            logger.info("hyde_generated", question=question[:30], doc_length=len(hyde_doc))
            return hyde_doc
        except Exception as e:
            logger.warning(f"HyDE generation failed: {e}")
            return question

    async def optimize(
        self,
        query: str,
        strategy: str = "full",
    ) -> Dict[str, Any]:
        """
        综合优化 - 应用多种策略

        Args:
            query: 原始查询
            strategy: 优化策略
                - "rewrite": 仅改写
                - "expand": 改写+扩展
                - "hyde": 改写+HyDE
                - "full": 全部策略

        Returns:
            {
                "rewritten": 改写后的查询,
                "expanded": 扩展查询列表,
                "hyde_doc": 假设文档,
                "final_queries": 最终检索用的查询列表
            }
        """
        result = {
            "original": query,
            "rewritten": query,
            "expanded": [],
            "hyde_doc": "",
            "final_queries": [query],
        }

        if strategy in ["rewrite", "expand", "full"]:
            result["rewritten"] = await self.rewrite(query)

        if strategy in ["expand", "full"]:
            result["expanded"] = await self.expand(result["rewritten"])
            # 最终查询 = 改写 + 扩展
            result["final_queries"] = [result["rewritten"]] + result["expanded"]

        if strategy in ["hyde", "full"]:
            result["hyde_doc"] = await self.generate_hypothetical_document(query)
            # HyDE 查询 = 原查询 + 假设文档
            result["final_queries"].append(result["hyde_doc"])

        logger.info("query_optimized", strategy=strategy, final_count=len(result["final_queries"]))
        return result


# 单例
_optimizer: Optional[QueryOptimizer] = None


def get_query_optimizer() -> QueryOptimizer:
    """获取 Query 优化器单例"""
    global _optimizer
    if _optimizer is None:
        _optimizer = QueryOptimizer()
    return _optimizer
