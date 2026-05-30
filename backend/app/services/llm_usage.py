"""从 LangChain LLM 响应解析 token 用量"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from langchain_core.messages import BaseMessage

MODEL_USD_PER_1M: Dict[str, Dict[str, float]] = {
    "gpt-4-turbo-preview": {"input": 10.0, "output": 30.0},
    "gpt-4-turbo": {"input": 10.0, "output": 30.0},
    "gpt-3.5-turbo": {"input": 0.5, "output": 1.5},
    "qwen-plus": {"input": 0.8, "output": 2.0},
    "qwen-turbo": {"input": 0.3, "output": 0.6},
    "gpt-4o": {"input": 2.5, "output": 10.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.6},
    "default": {"input": 2.0, "output": 8.0},
}


def _pick_int(data: Dict[str, Any], *keys: str) -> int:
    for key in keys:
        val = data.get(key)
        if val is not None:
            try:
                return int(val)
            except (TypeError, ValueError):
                continue
    return 0


def normalize_usage(raw: Optional[Dict[str, Any]]) -> Dict[str, int]:
    if not raw:
        return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    nested = raw.get("token_usage") if isinstance(raw.get("token_usage"), dict) else raw
    input_tokens = _pick_int(nested, "input_tokens", "prompt_tokens", "input")
    output_tokens = _pick_int(nested, "output_tokens", "completion_tokens", "output")
    total_tokens = _pick_int(nested, "total_tokens", "total")
    if total_tokens <= 0:
        total_tokens = input_tokens + output_tokens
    if input_tokens <= 0 and total_tokens > output_tokens:
        input_tokens = total_tokens - output_tokens

    return {
        "input_tokens": max(0, input_tokens),
        "output_tokens": max(0, output_tokens),
        "total_tokens": max(0, total_tokens),
    }


def extract_usage_from_llm_message(message: Any) -> Dict[str, int]:
    usage_meta = getattr(message, "usage_metadata", None)
    if usage_meta:
        return normalize_usage(usage_meta if isinstance(usage_meta, dict) else dict(usage_meta))

    response_meta = getattr(message, "response_metadata", None) or {}
    if isinstance(response_meta, dict):
        return normalize_usage(response_meta.get("token_usage") or response_meta)

    return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}


def estimate_tokens_from_text(*parts: str) -> int:
    text = "".join(p for p in parts if p)
    if not text:
        return 0
    return max(1, len(text) // 2)


def build_usage_for_llm_call(
    provider_usage: Dict[str, int],
    *,
    prompt_messages: List[BaseMessage],
    completion_text: str,
) -> Dict[str, int]:
    if provider_usage.get("total_tokens", 0) > 0:
        return provider_usage

    prompt_text = "\n".join(str(getattr(m, "content", "") or "") for m in prompt_messages)
    input_tokens = estimate_tokens_from_text(prompt_text)
    output_tokens = estimate_tokens_from_text(completion_text)
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
    }


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    prices = MODEL_USD_PER_1M.get(model) or MODEL_USD_PER_1M["default"]
    cost = (input_tokens / 1_000_000) * prices["input"] + (output_tokens / 1_000_000) * prices["output"]
    return round(cost, 6)


def build_llm_usage_record(
    message: Any,
    *,
    stage: str,
    model: str,
    prompt_text: str = "",
    completion_text: str = "",
) -> Optional[Dict[str, Any]]:
    """从单次 LLM 响应构造一条可落库的 usage 记录；无有效 token 时返回 None。"""
    provider = extract_usage_from_llm_message(message)
    completion = completion_text or str(getattr(message, "content", "") or "")

    if provider.get("total_tokens", 0) > 0:
        usage = provider
    else:
        input_tokens = estimate_tokens_from_text(prompt_text)
        output_tokens = estimate_tokens_from_text(completion)
        usage = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        }

    if usage.get("total_tokens", 0) <= 0:
        return None

    return {
        "stage": stage,
        "input_tokens": usage["input_tokens"],
        "output_tokens": usage["output_tokens"],
        "model": model,
    }

