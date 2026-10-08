"""题目阶段（foundation/framework/architecture/experience）的纯函数逻辑。

从 graph.py 拆出：配额计算、阶段推断、排序与配平都不依赖模型调用，
单独放这里方便测试，也让 graph.py 只剩流程与 prompt。
"""

from __future__ import annotations

import re

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


def normalize_stage(raw, item: dict, reason: str) -> str:
    stage = str(raw or "").strip().lower()
    if stage in STAGE_RANK:
        return stage
    return infer_stage(item, reason)


def infer_stage(item: dict, reason: str) -> str:
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
    if foundation_topic_rank(item) < 3:
        return "foundation"
    if item.get("difficulty") == "hard":
        return "architecture"
    if item.get("difficulty") == "easy":
        return "foundation"
    return "framework"


def parse_years(raw: str) -> float | None:
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


def stage_quotas(count: int, junior: bool) -> dict[str, int]:
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


def foundation_topic_rank(item: dict) -> int:
    topic = str(item.get("topic") or "").lower()
    if "css" in topic:
        return 0
    if "javascript" in topic or topic in {"js", "ecmascript"}:
        return 1
    if "html" in topic:
        return 2
    return 3


def order_selected(selected: list[dict], focus: str) -> list[dict]:
    def key(item: dict):
        stage = item.get("stage", "foundation")
        topic_rank = foundation_topic_rank(item) if stage == "foundation" and focus == "frontend" else 0
        return (STAGE_RANK.get(stage, 99), topic_rank, item.get("id", ""))

    return sorted(selected, key=key)


def default_direction(item: dict, stage: str) -> str:
    if stage == "foundation":
        return "先给定义或结论，再补一个具体例子，最后点出常见误区。"
    if stage == "framework":
        return "先说框架机制怎么工作，再对比一种替代方案，最后落到项目里你会怎么选。"
    if stage == "architecture":
        return "先讲目标与约束，再给方案取舍，最后补监控、回滚或代价。"
    return "先交代项目背景与你的职责，再说决策与结果，最后复盘一处可改进点。"


def balance_and_sort(selected: list[dict], quotas: dict[str, int], focus: str, junior: bool) -> list[dict]:
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
                return (foundation_topic_rank(item), difficulty if junior else 0, item["id"])
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
