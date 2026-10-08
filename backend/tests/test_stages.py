"""stages.py 纯函数：配额、阶段推断、排序。从 graph.py 拆出后的回归测试。"""

from __future__ import annotations

from src.stages import (
    balance_and_sort,
    infer_stage,
    order_selected,
    parse_years,
    stage_quotas,
)


def test_quotas_sum_to_count():
    for count in (10, 15, 20):
        for junior in (True, False):
            quotas = stage_quotas(count, junior)
            assert sum(quotas.values()) == count


def test_junior_leans_foundation_senior_leans_framework():
    junior = stage_quotas(16, True)
    senior = stage_quotas(16, False)
    assert junior["foundation"] > junior["framework"]
    assert senior["framework"] > senior["foundation"]


def test_parse_years_variants():
    assert parse_years("3年") == 3.0
    assert parse_years("三年") == 3.0
    assert parse_years("未知") is None
    assert parse_years("") is None


def test_infer_stage_by_hints():
    css = {"topic": "CSS", "tags": [], "question": "什么是 BFC？", "difficulty": "easy"}
    vue = {"topic": "框架", "tags": ["vue"], "question": "响应式原理？", "difficulty": "medium"}
    perf = {"topic": "性能", "tags": [], "question": "首屏优化？", "difficulty": "hard"}
    assert infer_stage(css, "") == "foundation"
    assert infer_stage(vue, "") == "framework"
    assert infer_stage(perf, "") == "architecture"


def test_order_selected_stage_then_css_first():
    items = [
        {"id": "fw", "stage": "framework"},
        {"id": "html", "stage": "foundation", "topic": "HTML"},
        {"id": "css", "stage": "foundation", "topic": "CSS"},
        {"id": "exp", "stage": "experience"},
        {"id": "arch", "stage": "architecture"},
    ]
    ordered = [item["id"] for item in order_selected(items, "frontend")]
    assert ordered == ["css", "html", "fw", "arch", "exp"]


def test_balance_and_sort_respects_quotas_and_spills():
    def make(stage, n, start=0):
        return [
            {"id": f"{stage}-{start + i}", "stage": stage, "difficulty": "medium"}
            for i in range(n)
        ]

    selected = [*make("foundation", 5), *make("framework", 1), *make("architecture", 1)]
    quotas = {"foundation": 3, "framework": 2, "architecture": 2}
    picked = balance_and_sort(selected, quotas, "frontend", junior=True)
    # 配额 3+2+2=7，实有 5+1+1=7，全部保留
    assert len(picked) == 7
    stages = [item["stage"] for item in picked]
    assert stages[:3] == ["foundation"] * 3  # 先取 foundation 配额
