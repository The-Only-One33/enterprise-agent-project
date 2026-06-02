"""
意图识别与路由服务

支持多层级匹配：
1. 关键词精确匹配（最高优先级）
2. 实体提取辅助识别
3. LLM 语义识别（兜底）

支持意图澄清和调试模式
"""
from typing import Dict, List, Optional, Any, Tuple
from functools import lru_cache
import re
from pydantic import BaseModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from app.config import get_settings
from app.core.logging import get_logger
from app.services.intent.base import (
    IntentType,
    IntentResult,
    IntentPattern,
    RoutingTarget,
    INTENT_PATTERNS,
    IntentPriority,
)

logger = get_logger(__name__)
settings = get_settings()


# 意图模式权重配置
MATCH_WEIGHTS = {
    IntentPriority.KEYWORD: 0.5,   # 关键词匹配权重
    IntentPriority.ENTITY: 0.3,   # 实体提取权重
    IntentPriority.LLM: 0.2,      # LLM识别权重
}

# 置信度阈值
CONFIDENCE_THRESHOLD_HIGH = 0.8   # 高置信度，直接使用
CONFIDENCE_THRESHOLD_LOW = 0.5     # 低置信度，需要澄清

# 意图中文名（澄清提示用）
INTENT_DISPLAY_NAMES: Dict[str, str] = {
    "create_task": "创建任务",
    "update_task": "更新任务",
    "delete_task": "删除任务",
    "complete_task": "完成任务",
    "query_task_list": "查询任务列表",
    "query_my_tasks": "查看我的任务",
    "query_task_status": "按状态查询任务",
    "query_task_detail": "查看任务详情",
    "query_task_progress": "查看任务进度",
    "create_project": "创建项目",
    "query_project_list": "查询项目列表",
    "general_chat": "普通对话",
}

# 高置信度规则：优先于 LLM，避免「帮我创建一个任务」等被误判为查询
HIGH_CONFIDENCE_RULES: List[Tuple[str, IntentType, float]] = [
    # 创建（动作词前不能紧跟其它汉字，避免「最近创建的任务」误判）
    (
        r"(?:^|(?<![\u4e00-\u9fff]))(?:帮我|请|麻烦)?(?:创建|新建|添加|建立)(?:一个|个)?任务",
        IntentType.CREATE_TASK,
        0.96,
    ),
    (
        r"(?:^|(?<![\u4e00-\u9fff]))(?:帮我|请)?(?:创建|新建|添加)(?:一个|个)?项目",
        IntentType.CREATE_PROJECT,
        0.96,
    ),
    (r"(?:删除|移除|取消)(?:一个|个)?任务", IntentType.DELETE_TASK, 0.94),
    (r"(?:更新|修改|编辑)(?:一个|个)?任务", IntentType.UPDATE_TASK, 0.94),
    (r"(?:完成|结束)(?:一个|个)?任务", IntentType.COMPLETE_TASK, 0.94),
    (
        r"(?:查询|查看|查|看看|有哪些|有什么|我的|待办).{0,16}任务",
        IntentType.QUERY_TASK_LIST,
        0.92,
    ),
    (
        r"任务.{0,8}(?:列表|有哪些|有什么)",
        IntentType.QUERY_TASK_LIST,
        0.9,
    ),
    (r"(?:生成|导出|写|整理|输出).{0,8}周报", IntentType.WEEKLY_SUMMARY, 0.95),
    (r"本周.{0,6}(?:周报|工作总结|工作汇总)", IntentType.WEEKLY_SUMMARY, 0.93),
]


class IntentRouter:
    """意图路由器 - 支持多层级匹配"""

    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url or None,
            temperature=0,
        )
        self._setup_prompts()

    def _setup_prompts(self):
        """设置提示模板"""
        # 意图识别提示
        self.intent_prompt = ChatPromptTemplate.from_messages([
            ("system", """你是一个企业任务协同系统的意图识别专家。
根据用户输入，识别意图并提取关键实体。

## 支持的意图类型：
{template_types}

## 实体类型定义：
- task_id: 任务ID（数字）
- task_title: 任务标题/名称
- task_status: 任务状态 (pending/in_progress/completed/review)
- priority: 优先级 (low/medium/high/urgent)
- date_range: 日期范围 (今天/本周/本月/具体日期)
- project_id: 项目ID
- project_name: 项目名称
- employee_id: 员工ID
- employee_name: 员工姓名
- score_value: 评分值 (1-100)
- execution_id: 执行分工ID
- execution_title: 执行分工名称
- evaluation_content: 评价内容
- action: 操作类型 (创建/编辑/删除/查询/添加)

## 识别要点（务必区分）：
- 「创建/新建/添加 + 任务」→ create_task（例如：帮我创建一个任务、新建任务）
- 「查询/查看/有哪些 + 任务」→ query_task_list（例如：我有哪些任务）
- 「最近创建的任务」是查询（按时间筛选），不是 create_task

## 输出格式（JSON）：
{{"intent": "意图类型", "confidence": 0.0-1.0, "entities": {{"实体类型": "实体值"}}, "reasoning": "识别理由"}}

若提供了对话历史，必须结合历史理解当前句的真实意图（指代/续问）。
"""),
            ("human", """{history_section}当前用户输入: {user_input}
{resolved_hint}"""),
        ])
        self.intent_chain = self.intent_prompt | self.llm

        # 实体提取提示
        self.entity_prompt = ChatPromptTemplate.from_messages([
            ("system", """从用户输入中提取关键实体。若提供对话历史，结合历史补全省略的主语/对象。

## 实体类型：
- task_id, task_title, task_status, priority, date, project_name, person_name, score_value, execution_id, execution_title, evaluation_content

## 输出格式（JSON数组）：
[{{"type": "实体类型", "value": "实体值", "position": 0}}]
"""),
            ("human", """{history_section}用户输入: {user_input}"""),
        ])
        self.entity_chain = self.entity_prompt | self.llm

    def _keyword_match(self, user_input: str) -> Dict[str, float]:
        """关键词匹配"""
        matches = {}
        user_input_lower = user_input.lower()

        for pattern in INTENT_PATTERNS:
            score = 0
            matched_keywords = []

            excluded = False
            if pattern.exclude_keywords:
                for exclude_kw in pattern.exclude_keywords:
                    if re.search(exclude_kw, user_input):
                        excluded = True
                        break

            if not excluded:
                for keyword in pattern.keywords:
                    if re.search(keyword, user_input, re.IGNORECASE):
                        score += 1
                        matched_keywords.append(keyword)

            if score > 0:
                # 归一化分数：匹配数 / 总关键词数 * 优先级加权
                normalized_score = (score / len(pattern.keywords)) * (1 + pattern.priority / 10)
                matches[pattern.intent.value] = {
                    "score": normalized_score,
                    "matched_keywords": matched_keywords,
                    "pattern": pattern,
                }

        # 归一化到 0-1
        if matches:
            max_score = max(m["score"] for m in matches.values())
            for intent, data in matches.items():
                data["score"] = data["score"] / max_score if max_score > 0 else 0

        return matches

    def _history_prompt_section(self, history: Optional[List[Dict[str, str]]]) -> str:
        from app.services.conversation_context import format_history_for_prompt, trim_for_intent

        trimmed = trim_for_intent(history or [])
        if not trimmed:
            return ""
        return f"对话历史：\n{format_history_for_prompt(trimmed)}\n\n"

    async def _extract_entities(
        self,
        user_input: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
        """LLM 实体提取，返回 (entities, usage_record|None)。"""
        from app.services.llm_usage import build_llm_usage_record

        try:
            response = await self.entity_chain.ainvoke({
                "user_input": user_input,
                "history_section": self._history_prompt_section(history),
            })
            import json
            result = json.loads(response.content)
            entities = {}
            for item in result:
                entities[item["type"]] = item["value"]
            usage = build_llm_usage_record(
                response,
                stage="entity_extraction",
                model=settings.openai_model,
                prompt_text=user_input,
                completion_text=str(response.content or ""),
            )
            return entities, usage
        except Exception as e:
            logger.warning(f"Entity extraction failed: {e}")
            return {}, None

    async def _llm_recognize(
        self,
        user_input: str,
        context: Optional[Dict] = None,
        *,
        history: Optional[List[Dict[str, str]]] = None,
        resolved_hint: str = "",
    ) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
        """LLM 语义识别，返回 (result_dict, usage_record|None)。"""
        from app.services.llm_usage import build_llm_usage_record

        try:
            intent_types = [p.intent.value for p in INTENT_PATTERNS]
            template = "\n".join([f"- {i}" for i in intent_types])
            hint_line = ""
            if resolved_hint and resolved_hint.strip() != user_input.strip():
                hint_line = f"结合历史后的完整表述参考: {resolved_hint.strip()}\n"

            response = await self.intent_chain.ainvoke({
                "user_input": user_input,
                "template_types": template,
                "history_section": self._history_prompt_section(history),
                "resolved_hint": hint_line,
            })

            import json
            import re
            json_match = re.search(r'\{.*\}', response.content, re.DOTALL)
            usage = build_llm_usage_record(
                response,
                stage="intent_recognition",
                model=settings.openai_model,
                prompt_text=user_input,
                completion_text=str(response.content or ""),
            )
            if json_match:
                result = json.loads(json_match.group())
                return {
                    "intent": result.get("intent", "general_chat"),
                    "confidence": float(result.get("confidence", 0.5)),
                    "entities": result.get("entities", {}),
                    "reasoning": result.get("reasoning", ""),
                }, usage
        except Exception as e:
            logger.warning(f"LLM recognition failed: {e}")
        return {"intent": "general_chat", "confidence": 0.5, "entities": {}, "reasoning": ""}, None

    def _intent_label(self, intent_key: str) -> str:
        return INTENT_DISPLAY_NAMES.get(intent_key, intent_key.replace("_", " "))

    def _try_rule_based_match(self, user_input: str) -> Optional[IntentResult]:
        """规则优先匹配：覆盖 LLM 单独误判的场景。"""
        text = user_input.strip()
        if not text:
            return None

        for pattern, intent, confidence in HIGH_CONFIDENCE_RULES:
            if re.search(pattern, text, re.IGNORECASE):
                routing_target = self._get_routing_target(intent)
                suggested_model = self._get_suggested_model(intent)
                return IntentResult(
                    intent=intent,
                    confidence=confidence,
                    entities={},
                    routing_target=routing_target,
                    suggested_model=suggested_model,
                    reasoning=f"规则匹配: {pattern}",
                    needs_clarification=False,
                    clarification_question="",
                    candidate_intents=[intent.value],
                    confidence_breakdown={"strategy": "rule_based", "pattern": pattern},
                )
        return None

    def _generate_clarification_question(
        self,
        candidates: List[Tuple[str, float]]
    ) -> str:
        """生成澄清问题"""
        intent_names = [self._intent_label(c[0]) for c in candidates]
        if len(intent_names) == 2:
            return f"您是想「{intent_names[0]}」还是「{intent_names[1]}」？"
        options = "、".join(f"「{name}」" for name in intent_names[:3])
        return f"您是想{options}，还是其他？请明确告诉我您想做什么。"

    def _build_reasoning(
        self,
        final_intent: IntentType,
        candidates: Dict[str, Dict]
    ) -> str:
        """构建推理过程说明"""
        if not candidates or final_intent.value not in candidates:
            return "无法确定意图"

        best = candidates[final_intent.value]
        kw = best.get("keyword_score", 0)
        llm = best.get("llm_score", 0)
        strategy = best.get("strategy", "")

        parts = []
        if strategy == "both_support":
            parts.append(f"关键词({kw:.2f})和LLM({llm:.2f})都支持")
        elif strategy == "keyword_only":
            parts.append(f"仅关键词支持({kw:.2f})")
        elif strategy == "llm_only":
            parts.append(f"仅LLM支持({llm:.2f})")

        parts.append(f"综合得分={best.get('combined_score', 0):.2f}")
        return ", ".join(parts)

    async def recognize(
        self,
        user_input: str,
        context: Optional[Dict] = None,
        debug: bool = False,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> IntentResult:
        """
        识别用户意图

        Args:
            user_input: 当前轮用户输入
            context: 额外上下文
            debug: 是否返回调试信息
            history: 多轮对话 [{role, content}, ...]，不含当前句
        """
        logger.info("intent_recognition_started", user_input=user_input[:100])

        llm_usages: List[Dict[str, Any]] = []
        resolved_query = user_input.strip()

        # ===== Step 0: 多轮 contextualize（指代/续问 → standalone query） =====
        from app.services.conversation_context import trim_for_intent
        from app.services.rag.query_optimizer import get_query_optimizer

        trimmed_history = trim_for_intent(history or [])
        if trimmed_history:
            optimizer = get_query_optimizer()
            resolved_query, ctx_usage = await optimizer.contextualize(
                user_input, trimmed_history
            )
            if ctx_usage:
                llm_usages.append(ctx_usage)

        working_input = resolved_query or user_input.strip()

        # ===== Step 1: 高置信度规则（对 standalone query） =====
        rule_result = self._try_rule_based_match(working_input)
        if rule_result is not None:
            rule_result.resolved_query = working_input
            rule_result.llm_usages = llm_usages
            logger.info(
                "intent_recognition_rule_matched",
                intent=rule_result.intent.value,
                confidence=rule_result.confidence,
                resolved=working_input[:50],
            )
            return rule_result

        # ===== Step 2: 关键词匹配 =====
        keyword_matches = self._keyword_match(working_input)

        # ===== Step 3: 实体提取 =====
        entities, entity_usage = await self._extract_entities(working_input, trimmed_history)
        if entity_usage:
            llm_usages.append(entity_usage)

        # ===== Step 4: LLM 语义识别（带历史 + resolved 提示） =====
        llm_result, intent_usage = await self._llm_recognize(
            user_input,
            context,
            history=trimmed_history,
            resolved_hint=working_input,
        )
        if intent_usage:
            llm_usages.append(intent_usage)

        # ===== Step 5: 综合评分 =====
        confidence_breakdown = {}

        # Step 4.1: 构建意图候选列表
        candidates = {}

        logger.info(f"keyword_matches: {keyword_matches}")

        # 添加关键词候选
        for intent_str, match_data in keyword_matches.items():
            candidates[intent_str] = {
                "keyword_score": match_data["score"],
                "llm_score": 0.0,
                "keyword_support": True,
                "llm_support": False,
            }
        logger.info(f"candidates: {candidates}")

        # 添加 LLM 候选（如果不在预定义意图中则忽略）
        llm_intent_str = llm_result["intent"]
        
        logger.info(f"llm_intent_str: {llm_intent_str}")

        if llm_intent_str in candidates:
            # LLM 意图在关键词候选中
            candidates[llm_intent_str]["llm_score"] = llm_result["confidence"]
            candidates[llm_intent_str]["llm_support"] = True
        elif llm_intent_str != "general_chat":
            # LLM 意图不在关键词候选中，但有效意图
            candidates[llm_intent_str] = {
                "keyword_score": 0.0,
                "llm_score": llm_result["confidence"],
                "keyword_support": False,
                "llm_support": True,
            }

        # Step 4.2: 计算每个候选的综合得分
        for intent_str, scores in candidates.items():
            kw_score = scores["keyword_score"]
            llm_score = scores["llm_score"]
            kw_support = scores["keyword_support"]
            llm_support = scores["llm_support"]

            if kw_support and llm_support:
                # 两个信号都支持：加权平均
                scores["combined_score"] = kw_score * 0.7 + llm_score * 0.3
                scores["strategy"] = "both_support"
            elif kw_support:
                # 只有关键词支持
                scores["combined_score"] = kw_score * 0.8
                scores["strategy"] = "keyword_only"
            elif llm_support:
                # 只有 LLM 支持（降低权重）
                scores["combined_score"] = llm_score * 0.5
                scores["strategy"] = "llm_only"
            else:
                scores["combined_score"] = 0.0

        # Step 4.3: 取综合得分最高的意图
        if candidates:
            best_candidate = max(candidates.items(), key=lambda x: x[1]["combined_score"])
            final_intent = IntentType(best_candidate[0])
            final_confidence = best_candidate[1]["combined_score"]

            # 记录调试信息（按得分排序，最多5个）
            confidence_breakdown["candidates"] = {
                intent: {
                    "keyword_score": data["keyword_score"],
                    "llm_score": data["llm_score"],
                    "combined_score": data["combined_score"],
                    "strategy": data["strategy"],
                }
                for intent, data in sorted(
                    candidates.items(),
                    key=lambda x: x[1]["combined_score"],
                    reverse=True
                )[:5]
            }
        else:
            # 兜底：通用对话
            final_intent = IntentType.GENERAL_CHAT
            final_confidence = 0.0
            confidence_breakdown["candidates"] = {}

        # 合并实体
        all_entities = {**entities, **llm_result.get("entities", {})}

        # ===== Step 5: 确定路由目标 =====
        routing_target = self._get_routing_target(final_intent)

        # ===== Step 6: 选择模型 =====
        suggested_model = self._get_suggested_model(final_intent)

        # ===== Step 7: 成本控制 =====
        from app.services.cost_monitor import check_token_budget
        budget_status = await check_token_budget()
        if budget_status.get("level") in ["warning", "critical"] and "gpt-4" in suggested_model:
            suggested_model = "gpt-3.5-turbo"

        # ===== Step 8: 置信度检查 =====
        needs_clarification = False
        clarification_question = ""

        best_strategy = (
            candidates.get(final_intent.value, {}).get("strategy", "")
            if candidates
            else ""
        )
        keyword_strong = (
            best_strategy in ("keyword_only", "both_support")
            and candidates.get(final_intent.value, {}).get("keyword_score", 0) >= 0.6
        )

        if final_confidence < CONFIDENCE_THRESHOLD_LOW and not keyword_strong:
            needs_clarification = True
            top_candidates = [
                (intent, data["combined_score"])
                for intent, data in sorted(
                    candidates.items(),
                    key=lambda x: x[1]["combined_score"],
                    reverse=True,
                )[:3]
                if data["combined_score"] > 0
            ]
            logger.info(f"top_candidates: {top_candidates}")
            if top_candidates:
                clarification_question = self._generate_clarification_question(
                    top_candidates
                )
            else:
                clarification_question = (
                    "抱歉，我没太理解您的意思，请再具体描述一下您想做什么？"
                )

        # 构建结果
        result = IntentResult(
            intent=final_intent,
            confidence=final_confidence,
            entities=all_entities,
            routing_target=routing_target,
            suggested_model=suggested_model,
            reasoning=self._build_reasoning(final_intent, candidates),
            needs_clarification=needs_clarification,
            clarification_question=clarification_question,
            candidate_intents=list(keyword_matches.keys())[:5],
            confidence_breakdown=confidence_breakdown,
            llm_usages=llm_usages,
            resolved_query=working_input,
        )

        logger.info(
            "intent_recognition_completed",
            intent=final_intent.value,
            confidence=final_confidence,
            routing_target=routing_target.value,
            resolved=working_input[:50],
        )

        return result

    def _get_routing_target(self, intent: IntentType) -> RoutingTarget:
        """获取路由目标"""
        for pattern in INTENT_PATTERNS:
            if pattern.intent == intent:
                return pattern.routing_target
        return RoutingTarget.LLM

    def _get_suggested_model(self, intent: IntentType) -> str:
        """获取建议模型"""
        for pattern in INTENT_PATTERNS:
            if pattern.intent == intent:
                return pattern.suggested_model
        return "gpt-3.5-turbo"

    def route(self, intent_result: IntentResult) -> str:
        """根据意图结果进行路由"""
        return intent_result.routing_target.value


@lru_cache()
def get_intent_router() -> IntentRouter:
    """获取意图路由器单例"""
    return IntentRouter()
