from __future__ import annotations

import html
import re
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import TimeoutError as FuturesTimeoutError

# 不同领域的检索词，避免后端/Agent 简历也拿「前端开发」去搜
DOMAIN_QUERY = {
    "frontend": "前端开发",
    "backend": "后端开发",
    "agent": "AI Agent 大模型应用开发",
}
DOMAIN_KEYWORDS = {
    "frontend": ("前端", "javascript", "js", "vue", "react", "css", "html", "typescript"),
    "backend": ("后端", "java", "go", "python", "mysql", "redis", "分布式", "并发", "数据库", "服务端"),
    "agent": ("agent", "llm", "rag", "langchain", "langgraph", "大模型", "向量", "prompt", "智能体"),
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

SKIP_HOSTS = {
    "bing.com",
    "www.bing.com",
    "cn.bing.com",
    "autohome.com.cn",
    "www.autohome.com.cn",
    "car.autohome.com.cn",
    "jd.com",
    "www.jd.com",
    "taobao.com",
    "tmall.com",
}

# 标题/摘要里出现这些，基本不是前端面试题页
SKIP_TITLE = (
    "报价",
    "图片",
    "汽车之家",
    "蔚来",
    "车型",
    "经销商",
    "二手车",
    "登录",
    "注册",
)

JUNK_QUESTION = (
    "登录",
    "注册",
    "版权所有",
    "cookie",
    "隐私政策",
    "扫码",
    "关注公众号",
    "有帮助吗",
    "对您有帮助",
    "放弃本次",
    "确定要放弃",
    "是否确认",
    "点击这里",
    "立即下载",
    "免费领取",
    "蔚来",
    "换电",
    "电池",
    "报价",
    "年轻人买",
)

# 更像面试题干的开头/用词
INTERVIEW_HINTS = (
    "什么是",
    "如何",
    "怎样",
    "怎么",
    "为何",
    "为什么",
    "说说",
    "谈一谈",
    "讲讲",
    "解释",
    "简述",
    "描述",
    "区别",
    "对比",
    "原理",
    "实现",
    "优缺点",
    "适用",
    "场景",
    "有哪些",
    "能不能",
    "可不可以",
    "是否",
    "请",
    "简述",
    "列举",
    "设计",
    "优化",
    "排查",
    "解决",
    "理解",
    "机制",
    "流程",
    "生命周期",
    "渲染",
    "响应式",
    "闭包",
    "原型",
    "事件循环",
    "盒模型",
    "BFC",
    "重绘",
    "回流",
    "同源",
    "跨域",
    "Promise",
    "async",
    "await",
    "虚拟 DOM",
    "diff",
    "webpack",
    "vite",
)

# 搜索消歧：避免 ES6→蔚来车、HTML5→无关页
TOPIC_SEARCH_ALIAS = {
    "es6": "ES6 JavaScript ECMAScript",
    "es2015": "ES6 JavaScript",
    "es7": "ES7 JavaScript",
    "es8": "ES8 JavaScript",
    "html5": "HTML5 前端",
    "css3": "CSS3 前端",
    "vue3": "Vue3 前端",
    "vue2": "Vue2 前端",
    "react": "React 前端",
    "typescript": "TypeScript 前端",
    "ts": "TypeScript 前端",
    "node": "Node.js 后端",
    "nodejs": "Node.js 后端",
}

PREFERRED_HOSTS = (
    "juejin.cn",
    "zhuanlan.zhihu.com",
    "www.zhihu.com",
    "blog.csdn.net",
    "www.cnblogs.com",
    "segmentfault.com",
    "www.nowcoder.com",
    "leetcode.cn",
    "developer.mozilla.org",
    "github.com",
    "www.jianshu.com",
)


def search_interview_questions(topic: str, limit: int = 8, domain: str = "frontend") -> str:
    topic = (topic or "").strip()
    if not topic:
        return "请提供要查询的技术主题，例如 Vue3 响应式、MySQL 索引。"
    limit = max(1, min(12, int(limit)))
    payload = search_interview_questions_payload(topic, limit, domain)
    if not payload["questions"] and not payload["hits"]:
        return f"没有搜到和「{payload['query']}」相关的公开页面。"
    return _format(payload["query"], payload["questions"], payload["hits"][:6])


def search_interview_questions_payload(topic: str, limit: int = 8, domain: str = "frontend") -> dict:
    """结构化联网检索，供推荐流程与 MCP 工具共用。

    domain 取 frontend / backend / agent，决定搜索词里的领域限定；
    缺省按 frontend，保证旧调用方（MCP 工具）行为不变。
    """
    topic = (topic or "").strip()
    limit = max(1, min(12, int(limit or 8)))
    if not topic:
        return {"query": "", "questions": [], "hits": []}

    domain = (domain or "frontend").strip().lower()
    if domain not in DOMAIN_QUERY:
        domain = "frontend"
    search_topic = _search_topic(topic)
    query = f"{search_topic} {DOMAIN_QUERY[domain]} 面试题"
    try:
        hits = _merge(
            _search_bing(query),
            _search_bing(f"{search_topic} 高频面试题 大厂"),
        )
        hits = _rank(hits, topic)
    except Exception:
        return {"query": query, "questions": [], "hits": []}
    if not hits:
        return {"query": query, "questions": [], "hits": []}

    # 只要看起来像面试/技术文章的页面；绝不打开汽车站等
    pages = [hit for hit in hits if _looks_like_interview_page(hit, topic, domain)]
    questions = _collect_questions(pages[:5] or hits[:3], topic, limit, domain)
    return {"query": query, "questions": questions, "hits": hits}


def _search_topic(topic: str) -> str:
    key = re.sub(r"[\s_\-]+", "", topic).lower()
    return TOPIC_SEARCH_ALIAS.get(key, topic)


def _search_bing(query: str) -> list[dict]:
    params = urllib.parse.urlencode({"q": query, "count": "10"})
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
        if not url.startswith("http") or _host_blocked(host) or url in seen:
            continue
        seen.add(url)
        caption = re.search(r'class="b_caption"[^>]*>(.*?)</div>', block, re.S)
        title = _clean(link.group(2))
        if any(word in title for word in SKIP_TITLE):
            continue
        hits.append(
            {
                "title": title,
                "url": url,
                "snippet": _clean(caption.group(1) if caption else ""),
                "host": host,
            }
        )
    return hits


def _host_blocked(host: str) -> bool:
    host = host.lower()
    if host in SKIP_HOSTS:
        return True
    return any(host.endswith(item) for item in (".autohome.com.cn",))


def _merge(first: list[dict], second: list[dict]) -> list[dict]:
    merged: list[dict] = []
    seen: set[str] = set()
    for hit in [*first, *second]:
        if hit["url"] in seen:
            continue
        seen.add(hit["url"])
        merged.append(hit)
    return merged


def _rank(hits: list[dict], topic: str) -> list[dict]:
    topic_l = topic.lower()

    def score(hit: dict) -> int:
        title = hit["title"]
        snippet = hit["snippet"]
        host = hit.get("host") or urllib.parse.urlparse(hit["url"]).netloc.lower()
        blob = f"{title} {snippet}".lower()
        value = 0
        if "面试" in title:
            value += 8
        if "面试" in snippet:
            value += 3
        if topic_l and topic_l in blob:
            value += 4
        if any(host.endswith(pref) or host == pref for pref in PREFERRED_HOSTS):
            value += 3
        if any(word in title for word in ("教程", "入门到精通", "官网", "安装", "下载", "报价")):
            value -= 4
        if any(word in blob for word in ("蔚来", "汽车之家", "车型")):
            value -= 20
        return value

    return sorted(hits, key=score, reverse=True)


def _looks_like_interview_page(hit: dict, topic: str, domain: str = "frontend") -> bool:
    blob = f"{hit['title']} {hit['snippet']}".lower()
    if any(word in blob for word in ("蔚来", "汽车之家", "车型", "报价")):
        return False
    if "面试" in blob:
        return True
    topic_l = topic.lower()
    keywords = DOMAIN_KEYWORDS.get(domain, DOMAIN_KEYWORDS["frontend"])
    if topic_l and topic_l in blob and any(w in blob for w in keywords):
        return True
    host = hit.get("host") or ""
    return any(host.endswith(pref) or host == pref for pref in PREFERRED_HOSTS[:8])


def _collect_questions(hits: list[dict], topic: str, limit: int, domain: str = "frontend") -> list[dict]:
    found: list[dict] = []
    seen: set[str] = set()
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(_fetch_questions, hit["url"], topic, domain): hit for hit in hits}
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
        except (TimeoutError, FuturesTimeoutError):
            # 整批超时：返回已抓到的部分，让上层降级用知识库候选继续
            return found
    return found


def _fetch_questions(url: str, topic: str, domain: str = "frontend") -> list[str]:
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=8) as response:
        content_type = response.headers.get("Content-Type", "")
        if content_type and "html" not in content_type and "text" not in content_type:
            return []
        raw = response.read(350_000)
    text = _html_to_text(raw.decode("utf-8", "replace"))
    questions: list[str] = []

    # 优先抓「1. xxx？」「### 什么是…」这类列表/标题题干
    patterns = [
        r"(?m)^\s*\d{1,2}[\.、\)]\s*([^\n？?]{6,100}[？?])",
        r"(?m)^\s*[（(]?\d{1,2}[）)]\s*([^\n？?]{6,100}[？?])",
        r"(?m)^#+\s*([^\n？?]{6,80}[？?])",
        r"([^\n。！!]{6,100}[？?])",
    ]
    for pattern in patterns:
        for match in re.findall(pattern, text):
            line = _clean(match if isinstance(match, str) else match)
            if not _is_interview_question(line, topic, domain):
                continue
            if line not in questions:
                questions.append(line)
            if len(questions) >= 6:
                return questions
    return questions


def _is_interview_question(line: str, topic: str, domain: str = "frontend") -> bool:
    if len(line) < 8 or len(line) > 120:
        return False
    lower = line.lower()
    if any(word in line for word in JUNK_QUESTION) or any(word in lower for word in JUNK_QUESTION):
        return False
    # 必须是问句，且不像站点反馈/弹窗
    if not (line.endswith("？") or line.endswith("?")):
        return False
    if re.match(r"^(确定|是否|确认|您?想|还要|继续)", line):
        return False

    topic_key = re.sub(r"[\s_\-]+", "", topic).lower()
    topic_tokens = {
        topic_key,
        topic.lower(),
        *TOPIC_SEARCH_ALIAS.get(topic_key, topic).lower().split(),
    }
    topic_tokens = {t for t in topic_tokens if len(t) >= 2}

    has_hint = any(hint.lower() in lower or hint in line for hint in INTERVIEW_HINTS)
    has_topic = any(token in lower for token in topic_tokens)
    # 非前端领域补一条领域词命中，避免 backend/agent 题因前端向话术不匹配被误杀
    has_domain = any(w in lower for w in DOMAIN_KEYWORDS.get(domain, ()))
    # ES6 特例：必须沾 JavaScript / 前端语义，防止汽车页漏网
    if topic_key in {"es6", "es2015", "es7", "es8"}:
        if not any(w in lower for w in ("js", "javascript", "ecmascript", "前端", "变量", "promise", "箭头", "解构", "模块")):
            if not has_hint:
                return False

    # 至少：面试话术提示，或题干里出现主题词 / 领域词
    if not (has_hint or has_topic or has_domain):
        return False
    return True


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
