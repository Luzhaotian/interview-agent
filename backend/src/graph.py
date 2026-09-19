from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from src.kb import load_index, retrieve
from src.llm import get_llm, question_count
from src.resume import read_resume

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "output" / "questions.md"
LABELS = {
    "frontend": "前端",
    "agent": "Agent",
    "backend": "后端",
    "easy": "简单",
    "medium": "中等",
    "hard": "困难",
}


class InterviewState(TypedDict, total=False):
    resume_path: str
    resume_text: str
    profile: dict
    candidates: list
    selected: list
    report: str
    report_path: str
    question_count: int


def scan_resume(state: InterviewState) -> dict:
    text = read_resume(Path(state["resume_path"]))
    return {"resume_text": text[:12000]}


def parse_profile(state: InterviewState) -> dict:
    llm = get_llm()
    prompt = f"""从下面简历中抽取面试画像，只返回 JSON 对象，不要其他文字。
字段：
- years: 工作年限，看不出来就写“未知”
- focus: 只能是 frontend、backend、agent 之一。前端技术栈明显时选 frontend
- skills: 技能关键词数组，用简历里出现的技术名词，8 到 20 个
- projects: 项目或业务方向数组，最多 6 个
- summary: 两句话概括这个人适合被问什么

简历：
{state["resume_text"]}
"""
    raw = llm.invoke(prompt).content
    profile = _load_json(str(raw))
    if not isinstance(profile, dict):
        raise SystemExit("模型没有返回简历画像 JSON")
    focus = profile.get("focus")
    if focus not in {"frontend", "backend", "agent"}:
        profile["focus"] = "frontend"
    profile["skills"] = [str(item) for item in profile.get("skills") or []]
    profile["projects"] = [str(item) for item in profile.get("projects") or []]
    profile["years"] = str(profile.get("years") or "未知")
    profile["summary"] = str(profile.get("summary") or "")
    return {"profile": profile}


def retrieve_kb(state: InterviewState) -> dict:
    questions = load_index()
    candidates = retrieve(state["profile"], questions, limit=40)
    if len(candidates) < 10:
        raise SystemExit("知识库候选题不足 10 道，请先运行 python main.py ingest")
    return {"candidates": candidates}


def select_questions(state: InterviewState) -> dict:
    count = state.get("question_count") or question_count()
    llm = get_llm()
    brief = [
        {
            "id": item["id"],
            "category": item["category"],
            "topic": item["topic"],
            "difficulty": item["difficulty"],
            "tags": item["tags"],
            "question": item["question"],
        }
        for item in state["candidates"]
    ]
    prompt = f"""你是面试官。只能从候选题里选题，禁止编造新题，禁止改写题干。
候选人画像：
{json.dumps(state["profile"], ensure_ascii=False)}

候选题：
{json.dumps(brief, ensure_ascii=False)}

选出恰好 {count} 道。方向是 frontend 时，前端题应占大多数，只有简历明显涉及后端或 Agent 时才配对应题目。
只返回 JSON 数组，每项格式：{{"id": "题目id", "reason": "为什么和这份简历相关，一句话"}}
"""
    raw = llm.invoke(prompt).content
    picked = _load_json(str(raw))
    by_id = {item["id"]: item for item in state["candidates"]}
    selected: list[dict] = []
    used: set[str] = set()
    if isinstance(picked, list):
        for item in picked:
            if not isinstance(item, dict):
                continue
            qid = str(item.get("id", ""))
            if qid not in by_id or qid in used:
                continue
            used.add(qid)
            selected.append({**by_id[qid], "reason": str(item.get("reason") or "与简历技能匹配")})
            if len(selected) >= count:
                break

    for item in state["candidates"]:
        if len(selected) >= count:
            break
        if item["id"] in used:
            continue
        selected.append({**item, "reason": "检索结果与简历技能标签匹配"})
    if len(selected) < 10:
        raise SystemExit("有效题目不足 10 道，请检查模型是否返回了候选题 id")
    return {"selected": selected[:20]}


def write_report(state: InterviewState) -> dict:
    profile = state["profile"]
    lines = [
        "# 面试题推荐",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## 简历画像",
        "",
        f"- 方向：{LABELS.get(profile['focus'], profile['focus'])}",
        f"- 年限：{profile['years']}",
        f"- 技能：{'、'.join(profile['skills']) or '未识别'}",
        f"- 项目：{'、'.join(profile['projects']) or '未识别'}",
        f"- 摘要：{profile['summary'] or '无'}",
        "",
        "## 题目",
        "",
    ]
    for index, item in enumerate(state["selected"], start=1):
        lines.extend(
            [
                f"### {index}. [{LABELS.get(item['category'], item['category'])} / {item['topic']} / {LABELS.get(item['difficulty'], item['difficulty'])}] {item['question']}",
                "",
                f"**为什么问：** {item['reason']}",
                "",
                f"**答题要点：** {item['answer_outline']}",
                "",
            ]
        )
    report = "\n".join(lines).rstrip() + "\n"
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(report, encoding="utf-8")
    return {"report": report, "report_path": str(OUTPUT_PATH)}


def build_graph():
    graph = StateGraph(InterviewState)
    graph.add_node("scan_resume", scan_resume)
    graph.add_node("parse_profile", parse_profile)
    graph.add_node("retrieve_kb", retrieve_kb)
    graph.add_node("select_questions", select_questions)
    graph.add_node("write_report", write_report)
    graph.add_edge(START, "scan_resume")
    graph.add_edge("scan_resume", "parse_profile")
    graph.add_edge("parse_profile", "retrieve_kb")
    graph.add_edge("retrieve_kb", "select_questions")
    graph.add_edge("select_questions", "write_report")
    graph.add_edge("write_report", END)
    return graph.compile()


def _load_json(text: str):
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fenced:
        text = fenced.group(1)
    start_candidates = [index for index in (text.find("["), text.find("{")) if index >= 0]
    if not start_candidates:
        raise SystemExit(f"模型没有返回 JSON：{text[:300]}")
    start = min(start_candidates)
    end = max(text.rfind("]"), text.rfind("}"))
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise SystemExit(f"模型返回的 JSON 无法解析：{exc}") from exc
