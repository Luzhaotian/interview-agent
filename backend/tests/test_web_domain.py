"""联网补题的领域适配：backend/agent 简历不该拿「前端开发」去搜。"""

from __future__ import annotations

from src.web_questions import (
    DOMAIN_KEYWORDS,
    DOMAIN_QUERY,
    _is_interview_question,
    _looks_like_interview_page,
)


def test_domain_query_covers_all_focus():
    assert DOMAIN_QUERY["frontend"] == "前端开发"
    assert DOMAIN_QUERY["backend"] == "后端开发"
    assert "Agent" in DOMAIN_QUERY["agent"]


def test_backend_question_accepted_for_backend_domain():
    # MySQL 索引这类后端题，在 backend 领域应被接受
    assert _is_interview_question("MySQL 的聚簇索引和二级索引有什么区别？", "MySQL", "backend")


def test_frontend_domain_does_not_leak_into_backend_check():
    # 纯前端话术题在 backend 领域，若不含后端领域词/主题词/话术则拒绝
    assert not _is_interview_question("今天天气不错要不要出去玩？", "MySQL", "backend")


def test_page_filter_uses_domain_keywords():
    # 标题不含「面试」，只能靠 topic + 领域词命中；backend 领域应认 Java/并发
    hit = {"title": "Java 并发编程总结", "snippet": "线程池 分布式锁", "host": "example.com"}
    assert _looks_like_interview_page(hit, "java", "backend")
    # 同一页在前端领域不该被领域词命中（topic「java」也不在前端关键词里）
    assert not _looks_like_interview_page(
        {"title": "随便一个无关页", "snippet": "无关内容", "host": "example.com"},
        "java",
        "frontend",
    )
