from __future__ import annotations

import html
import re
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}
SKIP_HOSTS = {"bing.com", "www.bing.com", "cn.bing.com"}
JUNK = ("登录", "注册", "版权所有", "cookie", "隐私政策", "扫码", "关注公众号")


def search_interview_questions(topic: str, limit: int = 8) -> str:
    topic = (topic or "").strip()
    if not topic:
        return "请提供要查询的技术主题，例如 Vue3 响应式、MySQL 索引。"
    limit = max(1, min(12, int(limit)))
    payload = search_interview_questions_payload(topic, limit)
    if not payload["questions"] and not payload["hits"]:
        return f"没有搜到和「{payload['query']}」相关的公开页面。"
    return _format(payload["query"], payload["questions"], payload["hits"][:6])


def search_interview_questions_payload(topic: str, limit: int = 8) -> dict:
    """结构化联网检索，供推荐流程与 MCP 工具共用。"""
    topic = (topic or "").strip()
    limit = max(1, min(12, int(limit or 8)))
    if not topic:
        return {"query": "", "questions": [], "hits": []}
    query = topic if "面试" in topic else f"{topic} 面试题"
    try:
        hits = _merge(_search_bing(query), _search_bing(f"{topic} 高频面试题"))
        hits = _rank(hits)
    except Exception:
        return {"query": query, "questions": [], "hits": []}
    if not hits:
        return {"query": query, "questions": [], "hits": []}
    pages = [hit for hit in hits if "面试" in hit["title"] or "面试" in hit["snippet"]]
    questions = _collect_questions((pages or hits)[:4], limit)
    return {"query": query, "questions": questions, "hits": hits}


def _search_bing(query: str) -> list[dict]:
    params = urllib.parse.urlencode({"q": query, "count": "8"})
    request = urllib.request.Request(
        "https://cn.bing.com/search?" + params,
        headers=HEADERS,
    )
    with urllib.request.urlopen(request, timeout=12) as response:
        page = response.read().decode("utf-8", "replace")

    hits: list[dict] = []
    seen: set[str] = set()
    for block in re.findall(r'<li class="b_algo".*?</li>', page, re.S):
        link = re.search(
            r'<h2[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
            block,
            re.S,
        )
        if not link:
            continue
        url = html.unescape(link.group(1)).strip()
        host = urllib.parse.urlparse(url).netloc.lower()
        if not url.startswith("http") or host in SKIP_HOSTS or url in seen:
            continue
        seen.add(url)
        caption = re.search(r'class="b_caption"[^>]*>(.*?)</div>', block, re.S)
        hits.append(
            {
                "title": _clean(link.group(2)),
                "url": url,
                "snippet": _clean(caption.group(1) if caption else ""),
            }
        )
    return hits


def _merge(first: list[dict], second: list[dict]) -> list[dict]:
    merged: list[dict] = []
    seen: set[str] = set()
    for hit in [*first, *second]:
        if hit["url"] in seen:
            continue
        seen.add(hit["url"])
        merged.append(hit)
    return merged


def _rank(hits: list[dict]) -> list[dict]:
    def score(hit: dict) -> int:
        title = hit["title"]
        snippet = hit["snippet"]
        value = 0
        if "面试" in title:
            value += 5
        if "面试" in snippet:
            value += 2
        if any(word in title for word in ("教程", "文档", "官网", "安装")):
            value -= 3
        return value

    return sorted(hits, key=score, reverse=True)


def _collect_questions(hits: list[dict], limit: int) -> list[dict]:
    found: list[dict] = []
    seen: set[str] = set()
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(_fetch_questions, hit["url"]): hit for hit in hits}
        try:
            for future in as_completed(futures, timeout=18):
                hit = futures[future]
                try:
                    lines = future.result()
                except Exception:
                    continue
                for line in lines:
                    key = re.sub(r"\s+", "", line)
                    if key in seen:
                        continue
                    seen.add(key)
                    found.append({"question": line, "title": hit["title"], "url": hit["url"]})
                    if len(found) >= limit:
                        return found
        except TimeoutError:
            return found
    return found


def _fetch_questions(url: str) -> list[str]:
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=8) as response:
        content_type = response.headers.get("Content-Type", "")
        if content_type and "html" not in content_type and "text" not in content_type:
            return []
        raw = response.read(350_000)
    text = _html_to_text(raw.decode("utf-8", "replace"))
    questions: list[str] = []
    for match in re.findall(r"[^\n。！!]{8,140}[？?]", text):
        line = _clean(match)
        if len(line) < 8 or any(word in line.lower() for word in JUNK):
            continue
        if line not in questions:
            questions.append(line)
        if len(questions) >= 6:
            break
    return questions


def _html_to_text(page: str) -> str:
    page = re.sub(r"(?is)<(script|style|noscript).*?>.*?</\1>", " ", page)
    page = re.sub(r"(?i)<br\s*/?>", "\n", page)
    page = re.sub(r"(?i)</(p|div|li|h[1-6]|tr|blockquote)>", "\n", page)
    page = re.sub(r"<[^>]+>", " ", page)
    return html.unescape(page)


def _clean(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip(" \t-·|")


def _format(query: str, questions: list[dict], hits: list[dict]) -> str:
    lines = [f"检索：{query}", ""]
    if questions:
        lines.append("题目：")
        for index, item in enumerate(questions, start=1):
            lines.append(f"{index}. {item['question']}")
            lines.append(f"   来源：{item['title']}")
            lines.append(f"   链接：{item['url']}")
        lines.append("")
    lines.append("参考页面：")
    for item in hits:
        lines.append(f"- {item['title']}")
        lines.append(f"  {item['url']}")
        if item["snippet"]:
            lines.append(f"  {item['snippet']}")
    lines.append("")
    lines.append("这些题来自公开网页，没有写入本地知识库。")
    return "\n".join(lines)
