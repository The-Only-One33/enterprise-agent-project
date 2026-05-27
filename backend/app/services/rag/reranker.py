"""
检索结果重排 - 在 Hybrid 粗排后对候选集精排

- cross_encoder：BGE Cross-Encoder 语义精排（默认）
- lexical：粗排分 + jieba 词面重叠（无 torch 时的回退）
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Protocol, Tuple
import re

import jieba
from langchain_core.documents import Document

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

RERANK_VECTOR_WEIGHT = 0.7
RERANK_LEXICAL_WEIGHT = 0.3

_USER_DICT_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "rag" / "enterprise_userdict.txt"
)
_USER_DICT_LOADED = False

_STOPWORDS = frozenset({
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一", "一个",
    "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好",
    "自己", "这", "那", "什么", "怎么", "如何", "吗", "呢", "啊", "吧", "呀", "嘛",
    "一下", "一下子", "请问", "能不能", "可以", "想", "查", "有没有", "关于",
})


class Reranker(Protocol):
    def rerank(
        self,
        query: str,
        candidates: List[Tuple[Document, float]],
        top_k: int,
    ) -> List[Tuple[Document, float]]: ...


def _ensure_userdict() -> None:
    global _USER_DICT_LOADED
    if _USER_DICT_LOADED:
        return
    if _USER_DICT_PATH.is_file():
        jieba.load_userdict(str(_USER_DICT_PATH))
        logger.debug("jieba_userdict_loaded", path=str(_USER_DICT_PATH))
    else:
        logger.warning("jieba_userdict_missing", path=str(_USER_DICT_PATH))
    _USER_DICT_LOADED = True


def _is_valid_token(token: str) -> bool:
    if not token or token in _STOPWORDS:
        return False
    if re.fullmatch(r"[\u4e00-\u9fff]", token):
        return False
    if re.search(r"[\u4e00-\u9fff]", token):
        return len(token) >= 2
    if re.fullmatch(r"[a-zA-Z]+", token):
        return len(token) >= 2
    if re.fullmatch(r"\d+", token):
        return True
    return len(token) >= 2


def _tokenize(text: str) -> set:
    """jieba 分词 + 英文/数字补充，用于词面重叠计算。"""
    _ensure_userdict()
    text = text.lower().strip()
    if not text:
        return set()

    tokens: set[str] = set()
    for word in jieba.lcut(text):
        word = word.strip()
        if _is_valid_token(word):
            tokens.add(word)

    for word in re.findall(r"[a-zA-Z]{2,}|\d+", text):
        if _is_valid_token(word):
            tokens.add(word)

    return tokens


class LexicalCandidateReranker:
    """轻量精排：归一化粗排分 + jieba 词面重叠。"""

    def rerank(
        self,
        query: str,
        candidates: List[Tuple[Document, float]],
        top_k: int,
    ) -> List[Tuple[Document, float]]:
        if not candidates:
            return []

        query_tokens = _tokenize(query)
        if not query_tokens:
            return candidates[:top_k]

        max_orig = max(s for _, s in candidates) or 1.0
        scored: List[Tuple[Document, float]] = []

        for doc, orig_score in candidates:
            doc_tokens = _tokenize(doc.page_content)
            overlap = (
                len(query_tokens & doc_tokens) / len(query_tokens)
                if doc_tokens
                else 0.0
            )
            norm_orig = orig_score / max_orig if max_orig else 0.0
            final = RERANK_VECTOR_WEIGHT * norm_orig + RERANK_LEXICAL_WEIGHT * overlap
            scored.append((doc, final))

        scored.sort(key=lambda x: x[1], reverse=True)
        logger.debug(
            "lexical_rerank_completed",
            input_count=len(candidates),
            output_count=min(top_k, len(scored)),
        )
        return scored[:top_k]


class CrossEncoderCandidateReranker:
    """Cross-Encoder 语义精排；加载或推理失败时回退 lexical。"""

    def __init__(self) -> None:
        self._lexical = LexicalCandidateReranker()
        self._model: Optional[object] = None
        self._load_failed = False

    def _get_model(self) -> Optional[object]:
        if self._load_failed:
            return None
        if self._model is not None:
            return self._model

        try:
            from sentence_transformers import CrossEncoder

            settings = get_settings()
            logger.info("cross_encoder_loading", model=settings.rag_reranker_model)
            self._model = CrossEncoder(settings.rag_reranker_model)
            logger.info("cross_encoder_loaded", model=settings.rag_reranker_model)
            return self._model
        except Exception as e:
            self._load_failed = True
            logger.warning("cross_encoder_load_failed", error=str(e))
            return None

    def rerank(
        self,
        query: str,
        candidates: List[Tuple[Document, float]],
        top_k: int,
    ) -> List[Tuple[Document, float]]:
        if not candidates:
            return []

        model = self._get_model()
        if model is None:
            return self._lexical.rerank(query, candidates, top_k)

        settings = get_settings()
        max_chars = settings.rag_reranker_max_doc_chars

        try:
            pairs = [(query, doc.page_content[:max_chars]) for doc, _ in candidates]
            raw_scores = model.predict(pairs, show_progress_bar=False)
            scored = [
                (candidates[i][0], float(raw_scores[i]))
                for i in range(len(candidates))
            ]
            scored.sort(key=lambda x: x[1], reverse=True)
            logger.debug(
                "cross_encoder_rerank_completed",
                input_count=len(candidates),
                output_count=min(top_k, len(scored)),
            )
            return scored[:top_k]
        except Exception as e:
            logger.warning("cross_encoder_rerank_failed", error=str(e))
            return self._lexical.rerank(query, candidates, top_k)


# 兼容旧名
CandidateReranker = LexicalCandidateReranker

_reranker: Optional[Reranker] = None


def get_reranker() -> Reranker:
    global _reranker
    if _reranker is None:
        settings = get_settings()
        backend = settings.effective_rag_reranker_backend()
        if backend == "cross_encoder":
            _reranker = CrossEncoderCandidateReranker()
        else:
            _reranker = LexicalCandidateReranker()
        logger.info(
            "reranker_initialized",
            backend=backend,
            environment=settings.environment,
            configured=settings.rag_reranker_backend,
        )
    return _reranker
