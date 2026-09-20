from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterator, TypedDict

from langgraph.graph import END, START, StateGraph

from src.kb import find_skill_gaps, load_index, retrieve
from src.llm import bind_reasoning, complete_text, iter_model, question_count, unbind_reasoning
from src.resume import read_resume
from src.rules import gate_playbook, playbook_block
from src.web_questions import search_interview_questions_payload

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "output" / "questions.md"
LABELS = {
    "frontend": "前端",
    "agent": "Agent",
    "backend": "后端",
    "easy": "简单",
    "medium": "中等",
    "hard": "困难",
    "foundation": "基础",
    "framework": "框架",
    "architecture": "架构经验",
    "experience": "过往经历",
}
STAGES = ("foundation", "framework", "architecture", "experience")
STAGE_RANK = {name: index for index, name in enumerate(STAGES)}
FRAMEWORK_HINTS = ("vue", "react", "pinia", "hooks", "typescript", "vite", "webpack", "langgraph", "langchain")
ARCHITECTURE_HINTS = (
    "性能",
    "工程化",
    "架构",
    "缓存",
    "分布式",
    "一致性",
    "监控",
    "部署",
    "安全",
    "ssr",
    "微前端",
    "可观测",
    "熔断",
    "消息队列",
)


class InterviewState(TypedDict, total=False):
    resume_path: str
    resume_text: str
    profile: dict
    candidates: list
    kb_gaps: list
    web_candidates: list
    selected: list
    report: str
    report_path: str
    question_count: int


def scan_resume(state: InterviewState) -> dict:
    text = read_resume(Path(state["resume_path"]))
    return {"resume_text": text[:12000]}


def parse_profile(state: InterviewState) -> dict:
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
    raw = complete_text(prompt)
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
    gaps = find_skill_gaps(state["profile"], questions, max_gaps=3)
    return {"candidates": candidates, "kb_gaps": gaps}


def fill_gaps_via_mcp(state: InterviewState) -> dict:
    """知识库缺口时调用与 MCP 同一套联网检索，补候选题。"""
    gaps = list(state.get("kb_gaps") or [])
    if not gaps:
        return {"web_candidates": []}

    focus = (state.get("profile") or {}).get("focus") or "frontend"
    web_candidates: list[dict] = []
    seen_questions: set[str] = set()
    for topic in gaps:
        payload = search_interview_questions_payload(topic, limit=4)
        for index, item in enumerate(payload.get("questions") or []):
            question = str(item.get("question") or "").strip()
            key = re.sub(r"\s+", "", question)
            if len(question) < 8 or key in seen_questions:
                continue
            seen_questions.add(key)
            source_title = str(item.get("title") or "公开网页")
            source_url = str(item.get("url") or "")
            qid = f"web-{re.sub(r'[^a-zA-Z0-9]+', '-', topic.lower()).strip('-')}-{index + 1}"
            web_candidates.append(
                {
                    "id": qid[:64],
                    "category": focus,
                    "topic": topic,
                    "tags": [topic, "web", "mcp"],
                    "difficulty": "medium",
                    "question": question,
                    "answer_outline": (
                        f"结合公开资料「{source_title}」与项目经验作答。"
                        + (f" 参考：{source_url}" if source_url else "")
                    ),
                    "source": "web",
                    "source_title": source_title,
                    "source_url": source_url,
                }
            )
            if sum(1 for item in web_candidates if item["topic"] == topic) >= 2:
                break

    merged = list(state.get("candidates") or [])
    existing = {item["id"] for item in merged}
    for item in web_candidates:
        if item["id"] not in existing:
            merged.append(item)
            existing.add(item["id"])
    return {"web_candidates": web_candidates, "candidates": merged}


def select_questions(state: InterviewState) -> dict:
    count = state.get("question_count") or question_count()
    profile = state["profile"]
    years = _parse_years(str(profile.get("years") or ""))
    junior = years is None or years <= 5
    quotas = _stage_quotas(count, junior)
    brief = [
        {
            "id": item["id"],
            "category": item["category"],
            "topic": item["topic"],
            "difficulty": item["difficulty"],
            "tags": item["tags"],
            "question": item["question"],
            "source": item.get("source") or "kb",
        }
        for item in state["candidates"]
    ]
    mix = (
        "工作年限 5 年及以下（或未知）：foundation 明显多于 framework。"
        if junior
        else "工作年限超过 5 年：framework 明显多于 foundation。"
    )
    prompt = f"""你是面试官。只能从候选题里选题，禁止编造新题，禁止改写题干。
候选人画像：
{json.dumps(profile, ensure_ascii=False)}

候选题：
{json.dumps(brief, ensure_ascii=False)}

不要选过往经历题，经历题会另根据简历生成。
只覆盖三个阶段，目标数量：
- foundation：{quotas["foundation"]}。前端基础优先 CSS，其次 JavaScript，再 HTML，然后才是其他基础。
- framework：{quotas["framework"]}。Vue、React、框架与常用库。
- architecture：{quotas["architecture"]}。性能、工程化、系统设计、稳定性。

{mix}
优先选知识库题；source=web 的联网补题只在正好覆盖知识库缺口时少量选用。
只返回 JSON 数组，每项格式：
{{"id": "题目id", "stage": "foundation|framework|architecture", "reason": "为什么和这份简历相关，一句话", "answer_direction": "候选人应如何组织回答，两到三句"}}
{playbook_block("suggestions", "选题时同时遵守这些建议：")}"""
    raw = complete_text(prompt)
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
            base = by_id[qid]
            stage = _normalize_stage(item.get("stage"), base, str(item.get("reason") or ""))
            if stage == "experience":
                stage = _infer_stage(base, str(item.get("reason") or ""))
            selected.append(
                {
                    **base,
                    "stage": stage,
                    "reason": str(item.get("reason") or "与简历技能匹配"),
                    "answer_direction": str(item.get("answer_direction") or "").strip()
                    or _default_direction(base, stage),
                    "reference_answer": base["answer_outline"],
                }
            )

    for item in state["candidates"]:
        if item["id"] in used:
            continue
        stage = _infer_stage(item, "")
        selected.append(
            {
                **item,
                "stage": stage,
                "reason": "检索结果与简历技能标签匹配",
                "answer_direction": _default_direction(item, stage),
                "reference_answer": item["answer_outline"],
            }
        )
    kb_selected = [item for item in selected if item.get("stage") != "experience"]
    if len(kb_selected) < 8:
        raise SystemExit("有效题目不足，请检查模型是否返回了候选题 id")

    balanced = _balance_and_sort(kb_selected, quotas, str(profile.get("focus") or "frontend"), junior)
    experience = _draft_experience_questions(
        profile,
        state.get("resume_text") or "",
        quotas["experience"],
    )
    ordered = _order_selected([*balanced, *experience], str(profile.get("focus") or "frontend"))
    return {"selected": ordered[:count]}


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
        "## 题目（由浅到深）",
        "",
    ]
    for index, item in enumerate(state["selected"], start=1):
        stage = LABELS.get(item.get("stage", ""), item.get("stage", ""))
        lines.extend(
            [
                f"### {index}. [{stage} / {LABELS.get(item['category'], item['category'])} / {item['topic']} / {LABELS.get(item['difficulty'], item['difficulty'])}] {item['question']}",
                "",
                f"**为什么问：** {item['reason']}",
                "",
                f"**回答方向：** {item.get('answer_direction') or _default_direction(item, item.get('stage', 'foundation'))}",
                "",
                f"**参考答案：** {item.get('reference_answer') or item['answer_outline']}",
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
    graph.add_node("fill_gaps_via_mcp", fill_gaps_via_mcp)
    graph.add_node("select_questions", select_questions)
    graph.add_node("write_report", write_report)
    graph.add_edge(START, "scan_resume")
    graph.add_edge("scan_resume", "parse_profile")
    graph.add_edge("parse_profile", "retrieve_kb")
    graph.add_edge("retrieve_kb", "fill_gaps_via_mcp")
    graph.add_edge("fill_gaps_via_mcp", "select_questions")
    graph.add_edge("select_questions", "write_report")
    graph.add_edge("write_report", END)
    return graph.compile()


def run_recommend_stream(
    resume_path: str,
    count: int,
    on_event: Callable[[dict], None] | None = None,
) -> dict:
    """按步骤执行选题，并通过 on_event 推送 thinking / profile / question。"""

    def emit(payload: dict) -> None:
        if on_event:
            on_event(payload)

    state: InterviewState = {
        "resume_path": resume_path,
        "question_count": question_count(count),
    }
    token = bind_reasoning(lambda text: emit({"type": "thinking", "text": text, "append": True}))
    try:
        state.update(scan_resume(state))
        state.update(parse_profile(state))
        emit({"type": "profile", "profile": state["profile"]})

        state.update(retrieve_kb(state))
        gaps = list(state.get("kb_gaps") or [])
        emit(
            {
                "type": "thinking",
                "text": f"知识库候选 {len(state['candidates'])} 道。"
                + (f" 发现缺口技能：{'、'.join(gaps)}。" if gaps else " 暂无明显知识库缺口。"),
            }
        )

        if gaps:
            state.update(fill_gaps_via_mcp(state))
            web_count = len(state.get("web_candidates") or [])
            emit(
                {
                    "type": "thinking",
                    "text": f"MCP 联网补入 {web_count} 道候选。"
                    if web_count
                    else "MCP 联网未拿到可用题目，仍以知识库候选继续。",
                }
            )
        else:
            state.update({"web_candidates": []})

        state.update(select_questions(state))
        for item in state["selected"]:
            emit({"type": "question", "question": _public_selected(item)})
        state.update(write_report(state))
        return state
    finally:
        unbind_reasoning(token)


def stream_intro_tokens(profile: dict, questions: list[dict]) -> Iterator[str]:
    stage_counts = {stage: 0 for stage in STAGES}
    for item in questions:
        stage_counts[item.get("stage", "foundation")] = stage_counts.get(item.get("stage", "foundation"), 0) + 1
    prompt = f"""你是面试官助手。根据简历画像和已选题，写一段简短开场说明，80 到 140 字。
说明题目已按「基础 → 框架 → 架构经验 → 过往经历」排布，并点出和候选人最相关的一两点。
不要列出题目正文，不要输出 JSON。

画像：{json.dumps(profile, ensure_ascii=False)}
阶段分布：{json.dumps(stage_counts, ensure_ascii=False)}
题量：{len(questions)}
{playbook_block("suggestions", "开场说明同时遵守这些建议：")}"""
    yield from iter_model([{"role": "user", "content": prompt}])


def stream_chat_tokens(messages: list, context: str) -> Iterator[str]:
    system = (
        "你是面试准备助手。用中文回答。"
        "若用户追问某一道题，先给「回答方向」，再给「参考答案」要点，最后可补一句容易踩的坑。"
        "如果下面有已选题上下文，只能围绕这些题和简历画像展开，不要另编知识库里没有的题号。"
        "如果上下文是「（无）」，可以回答面试准备的一般问题，并提醒用户先上传简历。"
        "不要用纯 Markdown 列表批量罗列新面试题；需要出题时由系统用结构化卡片展示。"
        f"{playbook_block('suggestions', '回答时同时遵守这些建议：')}"
        f"\n\n已选题上下文：\n{context}"
    )
    payload = [{"role": "system", "content": system}]
    for role, text in messages:
        payload.append({"role": role, "content": text})
    yield from iter_model(payload)


def iter_chat_events(
    messages: list,
    context: str,
    profile: dict | None = None,
    selected_ids: list[str] | None = None,
    count: int = 5,
) -> Iterator[dict]:
    """追问流：出题类请求返回与首次出题相同的 question 卡片事件。"""
    last = ""
    for role, text in reversed(messages):
        if role == "user":
            last = text
            break
    intent = _classify_chat_intent(last)
    excluded = {str(item) for item in (selected_ids or []) if item}
    persona = _normalize_profile(profile)

    if intent == "interview_gate":
        material = "\n".join(
            part
            for part in (
                context,
                f"画像：{json.dumps(persona, ensure_ascii=False)}",
                last,
            )
            if part and part.strip() and part.strip() != "（无）"
        )
        if len(material) < 40:
            yield {"type": "token", "text": "请先上传简历，再判断是否进入可约面试环节。"}
            yield {"type": "done"}
            return
        decision = _decide_interview(material, persona)
        yield {"type": "decision", "decision": decision}
        yield {
            "type": "token",
            "text": "推荐面试。" if decision["recommend"] else "不推荐面试。",
        }
        yield {"type": "done"}
        return

    if intent == "more_questions":
        packed = _select_more_questions(persona, excluded, max(3, min(8, count)))
        if not packed:
            for token in stream_chat_tokens(messages, context):
                yield {"type": "token", "text": token}
            yield {"type": "done"}
            return
        for item in packed:
            yield {"type": "question", "question": _public_selected(item)}
        for token in _stream_more_intro(persona, packed):
            yield {"type": "token", "text": token}
        yield {"type": "done"}
        return

    if intent == "probe_questions":
        packed = _draft_probe_questions(persona, context, last, max(3, min(8, count)))
        if not packed:
            for token in stream_chat_tokens(messages, context):
                yield {"type": "token", "text": token}
            yield {"type": "done"}
            return
        for item in packed:
            yield {"type": "question", "question": _public_selected(item)}
        for token in _stream_more_intro(persona, packed, probe=True):
            yield {"type": "token", "text": token}
        yield {"type": "done"}
        return

    for token in stream_chat_tokens(messages, context):
        yield {"type": "token", "text": token}
    yield {"type": "done"}


def _decide_interview(material: str, profile: dict) -> dict:
    prompt = f"""你在执行「是否可约面试」判断。只根据下面材料，不要靠想象补经历。
按下面规则和建议判断。规则里没写到的，不要自行加码。缺一条规则则 recommend 为 false。

{gate_playbook()}

只返回 JSON 对象，不要其他文字：
{{"recommend": true 或 false, "reasons": ["每条对应一条标准，并引用简历依据；不满足或材料不足也要写清楚"]}}

画像：
{json.dumps(profile, ensure_ascii=False)}

材料：
{material[:12000]}
"""
    try:
        parsed = _load_json(complete_text(prompt))
    except Exception:
        parsed = {}
    if not isinstance(parsed, dict):
        parsed = {}
    reasons = [str(item).strip() for item in (parsed.get("reasons") or []) if str(item).strip()]
    recommend = bool(parsed.get("recommend")) and len(reasons) > 0
    if not reasons:
        recommend = False
        reasons = ["简历材料不足，无法确认前端基础、AI 熟悉程度，以及是否至少有一个企业级 AI 项目。"]
    return {"recommend": recommend, "reasons": reasons[:6]}


def run_screen_stream(
    resume_path: str,
    on_event: Callable[[dict], None] | None = None,
) -> dict:
    """按面试门槛判断是否可约，并推送模型思考与结论。"""

    def emit(payload: dict) -> None:
        if on_event:
            on_event(payload)

    token = bind_reasoning(lambda text: emit({"type": "thinking", "text": text, "append": True}))
    try:
        state: InterviewState = {"resume_path": resume_path}
        state.update(scan_resume(state))
        state.update(parse_profile(state))
        emit({"type": "profile", "profile": state["profile"]})
        decision = _decide_interview(state.get("resume_text") or "", state["profile"])
        emit({"type": "decision", "decision": decision})
        emit(
            {
                "type": "token",
                "text": "推荐面试。" if decision["recommend"] else "不推荐面试。",
            }
        )
        return {**state, "decision": decision}
    finally:
        unbind_reasoning(token)


def _classify_chat_intent(text: str) -> str:
    value = (text or "").strip()
    more_hints = (
        "再来",
        "再出",
        "补充",
        "更多题",
        "一部分",
        "继续出",
        "再给",
        "加几道",
        "再推荐",
        "再来几",
        "继续推荐",
        "再挑",
        "再选",
        "出几道",
        "来几道",
    )
    probe_hints = ("追问", "围绕", "深挖", "展开问", "继续问", "怎么追问", "面试官追问")
    if any(hint in value for hint in ("可约面试", "是否可以面试", "是否进入", "推荐面试", "不推荐面试")):
        return "interview_gate"
    if any(hint in value for hint in more_hints):
        return "more_questions"
    if any(hint in value for hint in probe_hints):
        return "probe_questions"
    return "chat"


def _normalize_profile(profile: dict | None) -> dict:
    data = profile if isinstance(profile, dict) else {}
    focus = data.get("focus")
    if focus not in {"frontend", "backend", "agent"}:
        focus = "frontend"
    return {
        "years": str(data.get("years") or "未知"),
        "focus": focus,
        "skills": [str(item) for item in (data.get("skills") or []) if str(item).strip()],
        "projects": [str(item) for item in (data.get("projects") or []) if str(item).strip()],
        "summary": str(data.get("summary") or ""),
    }


def _select_more_questions(profile: dict, excluded: set[str], count: int) -> list[dict]:
    try:
        bank = load_index()
    except SystemExit:
        return []
    candidates = [
        item
        for item in retrieve(profile, bank, limit=50)
        if item["id"] not in excluded and not str(item["id"]).startswith("web-")
    ]
    if len(candidates) < 3:
        return []
    years = _parse_years(str(profile.get("years") or ""))
    junior = years is None or years <= 5
    # 补充题不含经历配额，经历仍按简历另出
    quotas = _stage_quotas(count + 2, junior)
    experience_n = min(2, quotas.get("experience", 0))
    kb_quotas = {
        "foundation": quotas["foundation"],
        "framework": quotas["framework"],
        "architecture": quotas["architecture"],
        "experience": 0,
    }
    brief = [
        {
            "id": item["id"],
            "category": item["category"],
            "topic": item["topic"],
            "difficulty": item["difficulty"],
            "tags": item["tags"],
            "question": item["question"],
        }
        for item in candidates[:36]
    ]
    prompt = f"""你是面试官。只能从候选题里选题，禁止编造新题。
这是补充题，请避开用户已经问过的题。
画像：{json.dumps(profile, ensure_ascii=False)}
目标数量约 {count} 道：foundation {kb_quotas['foundation']}，framework {kb_quotas['framework']}，architecture {kb_quotas['architecture']}。
前端基础优先 CSS → JavaScript → HTML。
只返回 JSON 数组：
{{"id":"题目id","stage":"foundation|framework|architecture","reason":"一句话","answer_direction":"两到三句"}}

候选题：
{json.dumps(brief, ensure_ascii=False)}
{playbook_block("suggestions", "补充选题时同时遵守这些建议：")}"""
    selected: list[dict] = []
    used: set[str] = set()
    by_id = {item["id"]: item for item in candidates}
    try:
        picked = _load_json(complete_text(prompt))
    except Exception:
        picked = []
    if isinstance(picked, list):
        for item in picked:
            if not isinstance(item, dict):
                continue
            qid = str(item.get("id", ""))
            if qid not in by_id or qid in used:
                continue
            used.add(qid)
            base = by_id[qid]
            stage = _normalize_stage(item.get("stage"), base, str(item.get("reason") or ""))
            if stage == "experience":
                stage = _infer_stage(base, "")
            selected.append(
                {
                    **base,
                    "stage": stage,
                    "reason": str(item.get("reason") or "补充与简历相关的题目"),
                    "answer_direction": str(item.get("answer_direction") or "").strip()
                    or _default_direction(base, stage),
                    "reference_answer": base["answer_outline"],
                    "source": base.get("source") or "kb",
                }
            )
            if len(selected) >= count:
                break
    for item in candidates:
        if len(selected) >= count:
            break
        if item["id"] in used:
            continue
        stage = _infer_stage(item, "")
        selected.append(
            {
                **item,
                "stage": stage,
                "reason": "补充题库中与简历匹配的题目",
                "answer_direction": _default_direction(item, stage),
                "reference_answer": item["answer_outline"],
                "source": item.get("source") or "kb",
            }
        )
    balanced = _balance_and_sort(selected, kb_quotas, str(profile.get("focus") or "frontend"), junior)
    experience = _draft_experience_questions(profile, "", experience_n) if experience_n else []
    # 经历题 id 避开已用
    for index, item in enumerate(experience, start=1):
        item["id"] = f"resume-exp-more-{index}"
    return _order_selected([*balanced, *experience], str(profile.get("focus") or "frontend"))[:count]


def _draft_probe_questions(profile: dict, context: str, user_text: str, count: int) -> list[dict]:
    prompt = f"""根据已选题上下文，为面试官写恰好 {count} 道「追问」题。
每道必须对应已选题或简历项目，带回答方向和参考答案要点。
只返回 JSON 数组，不要其他文字。每项：
{{"stage":"foundation|framework|architecture|experience","topic":"主题","difficulty":"easy|medium|hard","question":"追问题干","reason":"对应哪道已选题/简历点","answer_direction":"两到三句","reference_answer":"参考要点"}}

用户请求：{user_text}
画像：{json.dumps(profile, ensure_ascii=False)}
已选题上下文：
{context[:8000]}
{playbook_block("suggestions", "追问时同时遵守这些建议：")}"""
    try:
        parsed = _load_json(complete_text(prompt))
    except Exception:
        return []
    if not isinstance(parsed, list):
        return []
    focus = profile.get("focus") or "frontend"
    packed: list[dict] = []
    for index, item in enumerate(parsed, start=1):
        if not isinstance(item, dict):
            continue
        question = str(item.get("question") or "").strip()
        if len(question) < 8:
            continue
        stage = str(item.get("stage") or "framework").strip().lower()
        if stage not in STAGE_RANK:
            stage = "framework"
        difficulty = str(item.get("difficulty") or "medium")
        if difficulty not in {"easy", "medium", "hard"}:
            difficulty = "medium"
        reference = str(item.get("reference_answer") or "").strip() or "结合已选题上下文作答。"
        packed.append(
            {
                "id": f"probe-{index}",
                "category": focus,
                "topic": str(item.get("topic") or "追问").strip() or "追问",
                "tags": ["probe"],
                "difficulty": difficulty,
                "question": question,
                "answer_outline": reference,
                "stage": stage,
                "reason": str(item.get("reason") or "围绕已选题继续追问").strip(),
                "answer_direction": str(item.get("answer_direction") or "").strip()
                or _default_direction({"topic": "追问"}, stage),
                "reference_answer": reference,
                "source": "probe",
            }
        )
        if len(packed) >= count:
            break
    return _order_selected(packed, focus)


def _stream_more_intro(profile: dict, questions: list[dict], probe: bool = False) -> Iterator[str]:
    stage_counts = {stage: 0 for stage in STAGES}
    for item in questions:
        stage_counts[item.get("stage", "foundation")] = stage_counts.get(item.get("stage", "foundation"), 0) + 1
    kind = "追问卡片" if probe else "补充题目"
    prompt = f"""你是面试官助手。用 60 到 100 字说明这批{kind}的排布，不要列出题目正文，不要 JSON。
画像：{json.dumps(profile, ensure_ascii=False)}
阶段分布：{json.dumps(stage_counts, ensure_ascii=False)}
题量：{len(questions)}
{playbook_block("suggestions", "说明这批题目时同时遵守这些建议：")}"""
    yield from iter_model([{"role": "user", "content": prompt}])


def _public_selected(item: dict) -> dict:
    return {
        "id": item["id"],
        "category": item["category"],
        "topic": item["topic"],
        "difficulty": item["difficulty"],
        "stage": item.get("stage", "foundation"),
        "question": item["question"],
        "reason": item.get("reason", ""),
        "answer_direction": item.get("answer_direction")
        or _default_direction(item, item.get("stage", "foundation")),
        "reference_answer": item.get("reference_answer") or item["answer_outline"],
        "answer_outline": item["answer_outline"],
        "source": item.get("source") or "kb",
        "source_title": item.get("source_title") or "",
        "source_url": item.get("source_url") or "",
    }


def _normalize_stage(raw, item: dict, reason: str) -> str:
    stage = str(raw or "").strip().lower()
    if stage in STAGE_RANK:
        return stage
    return _infer_stage(item, reason)


def _infer_stage(item: dict, reason: str) -> str:
    blob = " ".join(
        [
            item.get("topic", ""),
            " ".join(item.get("tags") or []),
            item.get("question", ""),
            reason,
        ]
    ).lower()
    if any(hint in blob for hint in ARCHITECTURE_HINTS):
        return "architecture"
    if any(hint in blob for hint in FRAMEWORK_HINTS):
        return "framework"
    if _foundation_topic_rank(item) < 3:
        return "foundation"
    if item.get("difficulty") == "hard":
        return "architecture"
    if item.get("difficulty") == "easy":
        return "foundation"
    return "framework"


def _parse_years(raw: str) -> float | None:
    text = (raw or "").strip()
    if not text or "未知" in text:
        return None
    matched = re.search(r"(\d+(?:\.\d+)?)", text)
    if matched:
        return float(matched.group(1))
    digits = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
    for char, value in digits.items():
        if char in text:
            return float(value)
    return None


def _stage_quotas(count: int, junior: bool) -> dict[str, int]:
    weights = (
        {"foundation": 4, "framework": 2, "architecture": 2, "experience": 2}
        if junior
        else {"foundation": 2, "framework": 4, "architecture": 2, "experience": 2}
    )
    total = sum(weights.values())
    quotas = {stage: (count * weight) // total for stage, weight in weights.items()}
    leftover = count - sum(quotas.values())
    priority = ("foundation", "framework", "architecture", "experience") if junior else (
        "framework",
        "foundation",
        "architecture",
        "experience",
    )
    index = 0
    while leftover > 0:
        quotas[priority[index % len(priority)]] += 1
        leftover -= 1
        index += 1
    return quotas


def _foundation_topic_rank(item: dict) -> int:
    topic = str(item.get("topic") or "").lower()
    if "css" in topic:
        return 0
    if "javascript" in topic or topic in {"js", "ecmascript"}:
        return 1
    if "html" in topic:
        return 2
    return 3


def _draft_experience_questions(profile: dict, resume_text: str, count: int) -> list[dict]:
    if count <= 0:
        return []
    projects = [str(item) for item in (profile.get("projects") or []) if str(item).strip()]
    if not projects and profile.get("summary"):
        projects = [str(profile["summary"])[:80]]
    prompt = f"""根据这份简历写恰好 {count} 道「过往经历」面试题。
每道题必须点名简历里的具体项目、职责、技术选型或结果，禁止「介绍一下你的项目」这类空泛题。
只返回 JSON 数组，不要其他文字。每项：
{{"question": "题干", "reason": "对应简历哪一段", "answer_direction": "两到三句", "reference_answer": "结合简历信息的参考要点"}}

画像：
{json.dumps(profile, ensure_ascii=False)}

简历摘录：
{resume_text[:5000]}
{playbook_block("suggestions", "写经历题时同时遵守这些建议：")}"""
    drafted: list[dict] = []
    try:
        raw = complete_text(prompt)
        parsed = _load_json(str(raw))
    except Exception:
        parsed = []
    if isinstance(parsed, list):
        for item in parsed:
            if not isinstance(item, dict):
                continue
            question = str(item.get("question") or "").strip()
            if len(question) < 8:
                continue
            drafted.append(item)
            if len(drafted) >= count:
                break
    while len(drafted) < count and projects:
        project = str(projects[len(drafted) % len(projects)])
        drafted.append(
            {
                "question": f"在「{project}」里你负责哪一块？当时最难的一个决策是什么，结果如何？",
                "reason": f"简历项目：{project}",
                "answer_direction": "先说你的职责和约束，再讲决策与结果，最后补一个可改进点。",
                "reference_answer": f"围绕简历中的「{project}」展开职责、技术选型和结果，不要换成无关项目。",
            }
        )
    focus = profile.get("focus") or "frontend"
    selected: list[dict] = []
    for index, item in enumerate(drafted[:count], start=1):
        reference = str(item.get("reference_answer") or "").strip() or "结合简历中的项目职责与结果作答。"
        selected.append(
            {
                "id": f"resume-exp-{index}",
                "category": focus,
                "topic": "过往经历",
                "tags": ["resume", "experience"],
                "difficulty": "medium",
                "question": str(item["question"]).strip(),
                "answer_outline": reference,
                "stage": "experience",
                "reason": str(item.get("reason") or "基于简历项目追问").strip(),
                "answer_direction": str(item.get("answer_direction") or "").strip()
                or "先交代项目背景与你的职责，再说决策与结果，最后复盘一处可改进点。",
                "reference_answer": reference,
                "source": "resume",
            }
        )
    return selected


def _order_selected(selected: list[dict], focus: str) -> list[dict]:
    def key(item: dict):
        stage = item.get("stage", "foundation")
        topic_rank = _foundation_topic_rank(item) if stage == "foundation" and focus == "frontend" else 0
        return (STAGE_RANK.get(stage, 99), topic_rank, item.get("id", ""))

    return sorted(selected, key=key)


def _default_direction(item: dict, stage: str) -> str:
    if stage == "foundation":
        return "先给定义或结论，再补一个具体例子，最后点出常见误区。"
    if stage == "framework":
        return "先说框架机制怎么工作，再对比一种替代方案，最后落到项目里你会怎么选。"
    if stage == "architecture":
        return "先讲目标与约束，再给方案取舍，最后补监控、回滚或代价。"
    return "先交代项目背景与你的职责，再说决策与结果，最后复盘一处可改进点。"


def _balance_and_sort(selected: list[dict], quotas: dict[str, int], focus: str, junior: bool) -> list[dict]:
    buckets: dict[str, list[dict]] = {stage: [] for stage in ("foundation", "framework", "architecture")}
    seen: set[str] = set()
    for item in selected:
        stage = item.get("stage", "foundation")
        if stage not in buckets or item["id"] in seen:
            continue
        seen.add(item["id"])
        buckets[stage].append(item)

    def sort_bucket(stage: str, items: list[dict]) -> list[dict]:
        def key(item: dict):
            difficulty = {"easy": 0, "medium": 1, "hard": 2}.get(item.get("difficulty"), 1)
            if stage == "foundation" and focus == "frontend":
                return (_foundation_topic_rank(item), difficulty if junior else 0, item["id"])
            if stage == "foundation" and junior:
                return (0, difficulty, item["id"])
            if stage == "framework" and not junior:
                return (0, -difficulty, item["id"])
            return (0, difficulty, item["id"])

        return sorted(items, key=key)

    for stage in buckets:
        buckets[stage] = sort_bucket(stage, buckets[stage])

    picked: list[dict] = []
    for stage in ("foundation", "framework", "architecture"):
        need = quotas.get(stage, 0)
        picked.extend(buckets[stage][:need])
        buckets[stage] = buckets[stage][need:]

    short = sum(quotas.get(stage, 0) for stage in ("foundation", "framework", "architecture")) - len(picked)
    spill = ("foundation", "framework", "architecture") if junior else ("framework", "foundation", "architecture")
    while short > 0:
        progressed = False
        for stage in spill:
            if buckets[stage]:
                picked.append(buckets[stage].pop(0))
                short -= 1
                progressed = True
                if short <= 0:
                    break
        if not progressed:
            break
    return picked


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
