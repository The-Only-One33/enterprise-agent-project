"""
多轮对话上下文工具：裁剪历史、格式化 prompt、指代检测。

生产常见策略：
- 全量 Message 存 DB；进模型/RAG 只用 Working Memory（窗口 + 截断）
- user / assistant 分角色截断；澄清轮 pin 防挤掉
- 字符 + 估算 token 双预算；不同用途用不同 TrimProfile
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, TypedDict


class HistoryTurn(TypedDict, total=False):
    role: str
    content: str
    pinned: bool


# 续问/指代常见模式（中英）
_CONTEXTUAL_PATTERNS = re.compile(
    r"(那|这|它|他|她|上面|刚才|之前|继续|然后呢|还有吗|帮我处理|处理一下|"
    r"同上|一样|也是|怎么说|什么意思|再.*一下|接着|对吧|是吗|"
    r"this|that|it|continue|same as|what about|handle it|go on)",
    re.IGNORECASE,
)

# Working Memory 默认预算
DEFAULT_MAX_TURNS = 6
DEFAULT_MAX_CHARS = 2400
DEFAULT_MAX_TOKENS = 900
DEFAULT_ASSISTANT_MAX_CHARS = 280
DEFAULT_USER_MAX_CHARS = 800
# 超长 user（粘贴）用 head + tail，避免只留开头丢关键约束
DEFAULT_USER_LONG_THRESHOLD = 400
DEFAULT_USER_HEAD_CHARS = 320
DEFAULT_USER_TAIL_CHARS = 120


@dataclass(frozen=True)
class TrimProfile:
    """进 prompt 前的 Working Memory 预算（按用途分层）。"""

    max_turns: int = DEFAULT_MAX_TURNS
    max_chars: int = DEFAULT_MAX_CHARS
    max_tokens: int = DEFAULT_MAX_TOKENS
    assistant_max_chars: int = DEFAULT_ASSISTANT_MAX_CHARS
    user_max_chars: int = DEFAULT_USER_MAX_CHARS
    user_long_threshold: int = DEFAULT_USER_LONG_THRESHOLD
    user_head_chars: int = DEFAULT_USER_HEAD_CHARS
    user_tail_chars: int = DEFAULT_USER_TAIL_CHARS


# intent / entity / contextualize 共用较紧预算
TRIM_FOR_INTENT = TrimProfile(
    max_turns=6,
    max_chars=2400,
    max_tokens=900,
    assistant_max_chars=280,
    user_max_chars=800,
)

# RAG rewrite 通常只需 resolved query；历史更短即可
TRIM_FOR_RAG = TrimProfile(
    max_turns=4,
    max_chars=1600,
    max_tokens=600,
    assistant_max_chars=200,
    user_max_chars=600,
)


def extract_message_content(message: Any) -> str:
    """从 AgentState.messages 的单条记录提取文本。"""
    if isinstance(message, dict):
        if "content" in message and message["content"]:
            return str(message["content"])
        data = message.get("data")
        if isinstance(data, dict) and data.get("content"):
            return str(data["content"])
        if message.get("type") == "human" and "data" in message:
            inner = message["data"]
            if isinstance(inner, dict):
                return str(inner.get("content", ""))
        return str(message)
    return str(getattr(message, "content", message) or "")


def extract_message_role(message: Any) -> str:
    if isinstance(message, dict):
        if message.get("role") in ("user", "assistant", "system"):
            return str(message["role"])
        msg_type = message.get("type", "")
        if msg_type in ("human", "user"):
            return "user"
        if msg_type in ("ai", "assistant"):
            return "assistant"
        if message.get("type") == "clarification":
            return "assistant"
    role = getattr(message, "type", None) or getattr(message, "role", None)
    if role in ("human", "user"):
        return "user"
    return "assistant"


def agent_messages_to_history(
    messages: Sequence[Any],
    *,
    exclude_last: bool = False,
) -> List[HistoryTurn]:
    """AgentState.messages → [{role, content}, ...]"""
    items = list(messages)
    if exclude_last and items:
        items = items[:-1]
    history: List[HistoryTurn] = []
    for msg in items:
        content = extract_message_content(msg).strip()
        if not content:
            continue
        turn: HistoryTurn = {"role": extract_message_role(msg), "content": content}
        if isinstance(msg, dict) and msg.get("pinned"):
            turn["pinned"] = True
        history.append(turn)
    return history


def estimate_tokens(text: str) -> int:
    """
    轻量 token 估算（无 tiktoken 依赖）。
    CJK 约 1.5 char/token，拉丁约 4 char/token；混合取 2.5 保守估计。
    """
    if not text:
        return 0
    cjk = len(re.findall(r"[\u4e00-\u9fff]", text))
    other = max(len(text) - cjk, 0)
    return max(1, int(cjk / 1.5 + other / 4))


def truncate_content(
    content: str,
    *,
    role: str,
    profile: TrimProfile,
) -> str:
    """按角色截断单条消息。"""
    if role == "assistant":
        limit = profile.assistant_max_chars
        if len(content) <= limit:
            return content
        return content[:limit] + "…"

    # user
    if len(content) <= profile.user_max_chars:
        return content

    if len(content) > profile.user_long_threshold:
        head = profile.user_head_chars
        tail = profile.user_tail_chars
        if head + tail + 3 >= profile.user_max_chars:
            return content[: profile.user_max_chars] + "…"
        return content[:head] + "…" + content[-tail:]

    return content[: profile.user_max_chars] + "…"


def _turn_budget(content: str, role: str) -> tuple[int, int]:
    overhead = len(role) + 8
    return len(content) + overhead, estimate_tokens(content) + overhead // 2


def trim_conversation_history(
    history: List[HistoryTurn],
    *,
    profile: TrimProfile | None = None,
    max_turns: int | None = None,
    max_chars: int | None = None,
    max_tokens: int | None = None,
    assistant_max_chars: int | None = None,
    user_max_chars: int | None = None,
) -> List[HistoryTurn]:
    """
    Working Memory 裁剪：
    - 最近 max_turns 条为候选窗口
    - pinned 澄清轮始终保留（可略超预算）
    - user / assistant 分角色截断；超长 user 用 head+tail
    - 总字符 + 估算 token 双预算，从新往旧累加
    """
    if not history:
        return []

    p = profile or TrimProfile()
    turns_limit = max_turns if max_turns is not None else p.max_turns
    chars_limit = max_chars if max_chars is not None else p.max_chars
    tokens_limit = max_tokens if max_tokens is not None else p.max_tokens
    effective = TrimProfile(
        max_turns=turns_limit,
        max_chars=chars_limit,
        max_tokens=tokens_limit,
        assistant_max_chars=(
            assistant_max_chars
            if assistant_max_chars is not None
            else p.assistant_max_chars
        ),
        user_max_chars=(
            user_max_chars if user_max_chars is not None else p.user_max_chars
        ),
        user_long_threshold=p.user_long_threshold,
        user_head_chars=p.user_head_chars,
        user_tail_chars=p.user_tail_chars,
    )

    recent = history[-turns_limit:]
    trimmed: List[HistoryTurn] = []
    total_chars = 0
    total_tokens = 0

    for turn in reversed(recent):
        content = truncate_content(
            turn["content"],
            role=turn["role"],
            profile=effective,
        )
        char_cost, token_cost = _turn_budget(content, turn["role"])
        is_pinned = bool(turn.get("pinned"))

        if not is_pinned and trimmed:
            if total_chars + char_cost > chars_limit:
                break
            if total_tokens + token_cost > tokens_limit:
                break

        item: HistoryTurn = {"role": turn["role"], "content": content}
        if is_pinned:
            item["pinned"] = True
        trimmed.append(item)
        total_chars += char_cost
        total_tokens += token_cost

    trimmed.reverse()
    return trimmed


def trim_for_intent(history: List[HistoryTurn]) -> List[HistoryTurn]:
    return trim_conversation_history(history, profile=TRIM_FOR_INTENT)


def trim_for_rag(history: List[HistoryTurn]) -> List[HistoryTurn]:
    return trim_conversation_history(history, profile=TRIM_FOR_RAG)


def needs_contextual_resolution(text: str) -> bool:
    """当前句是否可能依赖上下文（指代/续问/过短）。"""
    stripped = text.strip()
    if not stripped:
        return False
    if len(stripped) <= 12:
        return True
    return bool(_CONTEXTUAL_PATTERNS.search(stripped))


def should_contextualize(current_input: str, history: Optional[List[HistoryTurn]]) -> bool:
    """是否值得做一次 standalone query 解析（有历史且指代/过短）。"""
    if not history:
        return False
    return needs_contextual_resolution(current_input)


def format_history_for_prompt(
    history: List[HistoryTurn],
    *,
    user_label: str = "用户",
    assistant_label: str = "助手",
) -> str:
    if not history:
        return "（无）"
    lines = []
    for turn in history:
        label = user_label if turn["role"] == "user" else assistant_label
        lines.append(f"{label}: {turn['content']}")
    return "\n".join(lines)
