"""联网补题质量：过滤垃圾问句与汽车 ES6 等误匹配。"""

from __future__ import annotations

from src.web_questions import _is_interview_question, _search_topic


def test_search_topic_disambiguates_es6():
    assert "JavaScript" in _search_topic("ES6")
    assert "前端" in _search_topic("HTML5")


def test_rejects_ui_feedback_and_car_noise():
    assert not _is_interview_question("此页面对您有帮助吗？", "CSS3")
    assert not _is_interview_question("确定要放弃本次机会？", "HTML5")
    assert not _is_interview_question("突然想到，蔚来换电以后会不会也有电池斩杀线？", "ES6")
    assert not _is_interview_question("忽悠年轻人买蔚来ES6？", "ES6")


def test_accepts_real_frontend_questions():
    assert _is_interview_question("什么是 BFC？如何触发？", "CSS3")
    assert _is_interview_question("ES6 的 let/const 和 var 有什么区别？", "ES6")
    assert _is_interview_question("说说 Vue3 的响应式原理？", "Vue3")
    assert _is_interview_question("HTML5 有哪些新的语义化标签？", "HTML5")
