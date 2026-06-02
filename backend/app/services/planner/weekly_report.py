"""周报导出与 LLM 提示构建。"""
from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Tuple


def current_week_range(today: date | None = None) -> Tuple[str, str]:
    """自然周周一至周日。"""
    today = today or date.today()
    start = today - timedelta(days=today.weekday())
    end = start + timedelta(days=6)
    return start.isoformat(), end.isoformat()


def last_week_range(today: date | None = None) -> Tuple[str, str]:
    today = today or date.today()
    this_start = today - timedelta(days=today.weekday())
    last_end = this_start - timedelta(days=1)
    last_start = last_end - timedelta(days=6)
    return last_start.isoformat(), last_end.isoformat()


def resolve_week_range(entities: Dict[str, Any]) -> Tuple[str, str]:
    if entities.get("widen_range") in ("近两周", "two_weeks", "2weeks"):
        end = date.today()
        start = end - timedelta(days=13)
        return start.isoformat(), end.isoformat()
    if entities.get("widen_range") in ("上周", "last_week"):
        return last_week_range()
    if entities.get("week_start") and entities.get("week_end"):
        return str(entities["week_start"]), str(entities["week_end"])
    return current_week_range()


def build_weekly_llm_system_prompt() -> str:
    return """你是企业周报撰写助手。请严格按【周报撰写规范】的 6 个章节输出 Markdown 周报：
1. 本周工作概述
2. 本周完成任务
3. 执行内容明细（必填，按任务分组）
4. 进行中与待办
5. 问题与所需支持
6. 下周工作计划

要求：
- 基于【业务数据】中的任务与执行内容，勿编造不存在的数据
- 若执行内容较少，按规范说明各分工项推进状态
- 语气专业、条目清晰，使用中文
- 直接输出完整 Markdown，不要额外解释"""


def build_weekly_llm_human_prompt(
    *,
    week_start: str,
    week_end: str,
    rag_chunks: List[str],
    weekly_data: Dict[str, Any],
    user_name: str = "",
) -> str:
    rag_text = "\n".join(f"- {c[:400]}" for c in rag_chunks[:6]) or "（无检索结果，按通用 6 章结构）"
    data_text = _format_weekly_data(weekly_data)
    name = user_name or "员工"
    return f"""请为 {name} 生成 {week_start} 至 {week_end} 的工作周报。

【周报撰写规范摘录】
{rag_text}

【业务数据】
{data_text}

请输出完整 Markdown 周报。"""


def _format_weekly_data(data: Dict[str, Any]) -> str:
    if not data:
        return "（无业务数据）"
    lines: List[str] = []
    lines.append(f"任务数: {data.get('task_count', 0)}，执行内容数: {data.get('execution_count', 0)}")
    for t in data.get("tasks") or []:
        proj = t.get("project_name") or t.get("project") or ""
        lines.append(
            f"- 任务#{t.get('id')} {t.get('title')} | 项目:{proj} | 状态:{t.get('status')}"
        )
    for e in data.get("executions") or []:
        lines.append(
            f"  · 执行:{e.get('title')} | 任务:{e.get('task_title')} | "
            f"状态:{e.get('status')} | 产出:{e.get('deliverable', '-')}"
        )
    return "\n".join(lines)


def export_markdown(
    content: str,
    *,
    employ_code: str,
    week_start: str,
    week_end: str,
) -> str:
    """写入 backend/data/exports/，返回相对路径。"""
    base = Path(__file__).resolve().parents[3] / "data" / "exports"
    base.mkdir(parents=True, exist_ok=True)
    safe_code = re.sub(r"[^\w\-]", "_", employ_code or "user")
    filename = f"weekly_{safe_code}_{week_start}_{week_end}.md"
    path = base / filename
    path.write_text(content.strip() + "\n", encoding="utf-8")
    return str(path.relative_to(base.parent.parent))


def parse_scope_from_message(message: str) -> Dict[str, Any]:
    """从澄清回复解析 report_scope / widen_range。"""
    msg = (message or "").strip()
    patch: Dict[str, Any] = {}
    if "全部项目" in msg or "总周报" in msg:
        patch["report_scope"] = "all_projects"
    elif msg.startswith("单项目") or msg.startswith("单项目：") or msg.startswith("单项目:"):
        name = re.sub(r"^单项目[:：]\s*", "", msg).strip()
        if name:
            patch["report_scope"] = "single_project"
            patch["project_name"] = name
    if "上周" in msg:
        patch["widen_range"] = "上周"
    elif "近两周" in msg:
        patch["widen_range"] = "近两周"
    return patch
