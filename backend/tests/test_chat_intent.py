"""聊天意图分类：关键词匹配要覆盖常见说法，且互不抢判。"""

from __future__ import annotations

from src.graph import _classify_chat_intent


def test_gate_wins_over_more():
    assert _classify_chat_intent("请判断是否可以进入可约面试环节") == "interview_gate"


def test_more_questions_common_phrases():
    for text in (
        "再来几道题",
        "换一批题看看",
        "重新出 5 道",
        "另外来几道架构题",
        "补充一些 CSS 题",
    ):
        assert _classify_chat_intent(text) == "more_questions", text


def test_probe_questions():
    assert _classify_chat_intent("围绕第 3 题继续追问") == "probe_questions"
    assert _classify_chat_intent("这道题面试官会怎么深挖？") == "probe_questions"


def test_plain_chat():
    assert _classify_chat_intent("响应式和双向绑定是一回事吗？") == "chat"
