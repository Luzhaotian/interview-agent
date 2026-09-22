from __future__ import annotations

import json
import re
from pathlib import Path

import jieba
from pydantic import BaseModel, Field, ValidationError

from src.embeddings import (
    EMBEDDINGS_PATH,
    active_backend,
    cosine_scores,
    embed_corpus,
    embed_query,
    embeddings_match,
    load_embeddings,
    save_embeddings,
)

jieba.setLogLevel(20)

ROOT = Path(__file__).resolve().parents[1]
KB_DIR = ROOT / "kb"
INDEX_PATH = ROOT / "data" / "index.json"
CATEGORIES = {"frontend", "agent", "backend"}
DIFFICULTIES = {"easy", "medium", "hard"}
STOPWORDS = set("的 了 和 与 在 是 什么 如何 怎么 一个 以及 或者 我们 你 我".split())
SKILL_ALIASES = {
    "mysql": ["sql", "数据库"],
    "postgresql": ["sql", "数据库"],
    "postgres": ["sql", "数据库"],
    "mongodb": ["数据库"],
    "redis": ["缓存"],
    "langgraph": ["agent"],
    "langchain": ["agent"],
    "rag": ["agent"],
    # 简历写法 ↔ 题库 tags/topic，避免误报缺口去联网抓垃圾
    "html5": ["html"],
    "html": ["html5"],
    "css3": ["css"],
    "css": ["css3"],
    "js": ["javascript", "es6"],
    "javascript": ["js", "es6"],
    "es6": ["javascript", "js", "es2015"],
    "es2015": ["es6", "javascript"],
    "ts": ["typescript"],
    "typescript": ["ts"],
    "vue3": ["vue"],
    "vue2": ["vue"],
    "vue": ["vue3", "vue2"],
    "reactjs": ["react"],
    "react.js": ["react"],
    "nodejs": ["node", "node.js"],
    "node.js": ["node", "nodejs"],
    "node": ["nodejs", "node.js"],
    "webpack": ["工程化", "打包"],
    "vite": ["工程化", "打包"],
}


class Question(BaseModel):
    id: str
    category: str
    topic: str
    tags: list[str] = Field(default_factory=list)
    difficulty: str
    question: str
    answer_outline: str


def ingest() -> list[dict]:
    questions = scan_kb()
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(
        json.dumps({"questions": questions}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    texts = [_index_text(item) for item in questions]
    backend = active_backend()
    print(f"正在为 {len(questions)} 道题生成向量（backend={backend}）…")
    matrix = embed_corpus(texts)
    save_embeddings([item["id"] for item in questions], matrix)
    print(f"向量已写入 {EMBEDDINGS_PATH}，维度 {matrix.shape[1]}")
    return questions


def load_index() -> list[dict]:
    if not INDEX_PATH.is_file() or _kb_newer_than_index() or not _embeddings_ready():
        return ingest()
    payload = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    questions = payload["questions"]
    if not embeddings_match(questions):
        return ingest()
    return questions


def scan_kb() -> list[dict]:
    if not KB_DIR.is_dir():
        raise SystemExit(f"知识库目录不存在：{KB_DIR}")

    questions: list[dict] = []
    seen: set[str] = set()
    files = sorted(
        path
        for path in KB_DIR.rglob("*")
        if path.suffix.lower() in {".json", ".md", ".markdown"} and path.is_file()
    )
    if not files:
        raise SystemExit(f"{KB_DIR} 里没有 Markdown 或 JSON 题目")

    for path in files:
        default_category = _category_from_path(path)
        for raw in _read_file(path, default_category):
            try:
                item = Question.model_validate(raw).model_dump()
            except ValidationError as exc:
                raise SystemExit(f"{path} 题目格式不对：{exc}") from exc
            if item["category"] not in CATEGORIES:
                raise SystemExit(f"{path} 的分类必须是 frontend / agent / backend：{item['id']}")
            if item["difficulty"] not in DIFFICULTIES:
                raise SystemExit(f"{path} 的难度必须是 easy / medium / hard：{item['id']}")
            if item["id"] in seen:
                raise SystemExit(f"题目 id 重复：{item['id']}（{path}）")
            seen.add(item["id"])
            questions.append(item)

    if not questions:
        raise SystemExit("没有扫描到任何题目")
    return questions


def retrieve(profile: dict, questions: list[dict], limit: int = 40) -> list[dict]:
    """向量相似度检索，再叠加分类权重与技能标签重合。"""
    if not questions:
        return []

    matrix = _question_matrix(questions)
    query = " ".join(
        [
            " ".join(profile.get("skills") or []),
            " ".join(profile.get("projects") or []),
            profile.get("summary") or "",
            profile.get("focus") or "",
        ]
    )
    scores = cosine_scores(embed_query(query), matrix)
    weights = _category_weights(profile.get("focus") or "frontend")
    skill_tokens = _skill_tokens(profile.get("skills") or [])

    ranked: list[tuple[float, dict]] = []
    for item, score in zip(questions, scores):
        overlap = _skill_overlap(item, skill_tokens)
        # 余弦约在 [-1,1]，面试题通常 >0；再乘分类权重，并给技能重合加分
        ranked.append((float(score) * weights.get(item["category"], 1.0) + overlap * 0.08, item))

    ranked.sort(key=lambda pair: pair[0], reverse=True)
    if ranked and ranked[0][0] <= 0:
        focus = profile.get("focus") or "frontend"
        ranked.sort(key=lambda pair: (0 if pair[1]["category"] == focus else 1, pair[1]["id"]))
        return [item for _, item in ranked[:limit]]

    focus = profile.get("focus") or "frontend"
    primary = [item for _, item in ranked if item["category"] == focus]
    related_by_category: dict[str, list[dict]] = {}
    for _, item in ranked:
        if item["category"] == focus or _skill_overlap(item, skill_tokens) <= 0:
            continue
        related_by_category.setdefault(item["category"], []).append(item)
    related: list[dict] = []
    for items in related_by_category.values():
        related.extend(items[:4])
    related = related[:8]
    selected = primary[: limit - len(related)] + related
    if len(selected) < limit:
        seen = {item["id"] for item in selected}
        selected.extend(item for _, item in ranked if item["id"] not in seen)
    return selected[:limit]


def find_skill_gaps(profile: dict, questions: list[dict], max_gaps: int = 3) -> list[str]:
    """找出简历技能在知识库里几乎没有对应题的缺口主题。"""
    gaps: list[str] = []
    seen: set[str] = set()
    for skill in profile.get("skills") or []:
        text = str(skill).strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        if _skill_covered(text, questions):
            continue
        gaps.append(text)
        if len(gaps) >= max_gaps:
            break
    return gaps


def _question_matrix(questions: list[dict]):
    loaded = load_embeddings()
    if loaded and embeddings_match(questions):
        _, vectors, _, _ = loaded
        return vectors
    matrix = embed_corpus([_index_text(item) for item in questions])
    save_embeddings([item["id"] for item in questions], matrix)
    return matrix


def _embeddings_ready() -> bool:
    return EMBEDDINGS_PATH.is_file()


def _skill_covered(skill: str, questions: list[dict]) -> bool:
    tokens = _skill_tokens([skill])
    if any(_skill_overlap(item, tokens) > 0 for item in questions):
        return True
    needle = skill.lower()
    for item in questions:
        blob = _index_text(item).lower()
        if needle and needle in blob:
            return True
    return False


def _read_file(path: Path, default_category: str | None) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"{path} 不是合法 JSON：{exc}") from exc
        if isinstance(payload, dict):
            payload = payload.get("questions", [payload])
        if not isinstance(payload, list):
            raise SystemExit(f"{path} 必须是题目数组")
        return [_fill_category(item, default_category) for item in payload]
    return _parse_markdown(text, default_category)


def _parse_markdown(text: str, default_category: str | None) -> list[dict]:
    chunks = re.split(r"(?m)^##\s+", text)
    items: list[dict] = []
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        lines = chunk.splitlines()
        item: dict = {"id": lines[0].strip(), "tags": []}
        body: list[str] = []
        meta_done = False
        for line in lines[1:]:
            if not meta_done and re.match(r"^[A-Za-z_]+\s*:", line):
                key, value = line.split(":", 1)
                key = key.strip().lower()
                value = value.strip()
                if key == "tags":
                    item["tags"] = [part.strip() for part in re.split(r"[,，]", value) if part.strip()]
                else:
                    item[key] = value
                continue
            meta_done = True
            body.append(line)
        content = "\n".join(body).strip()
        question, outline = _split_markdown_body(content)
        item["question"] = question
        item["answer_outline"] = outline
        items.append(_fill_category(item, default_category))
    return items


def _split_markdown_body(content: str) -> tuple[str, str]:
    question_match = re.search(r"题目[:：]\s*(.+)", content)
    outline_match = re.search(r"要点[:：]\s*([\s\S]+)", content)
    if question_match:
        question = question_match.group(1).strip()
        outline = outline_match.group(1).strip() if outline_match else ""
        return question, outline
    parts = re.split(r"\n\s*\n", content, maxsplit=1)
    question = parts[0].strip()
    outline = parts[1].strip() if len(parts) > 1 else ""
    return question, outline


def _fill_category(item: dict, default_category: str | None) -> dict:
    if not item.get("category") and default_category:
        item = {**item, "category": default_category}
    return item


def _category_from_path(path: Path) -> str | None:
    for part in path.parts:
        if part in CATEGORIES:
            return part
    return None


def _index_text(item: dict) -> str:
    return " ".join(
        [
            item["question"],
            item["topic"],
            item["answer_outline"],
            item["category"],
            " ".join(item["tags"]),
        ]
    )


def _tokenize(text: str) -> list[str]:
    tokens = []
    for token in jieba.lcut(text.lower()):
        token = token.strip()
        if not token or token in STOPWORDS or not any(char.isalnum() for char in token):
            continue
        tokens.append(token)
    return tokens or ["空"]


def _skill_tokens(skills: list[str]) -> set[str]:
    tokens = set(_tokenize(" ".join(skills)))
    for token in list(tokens):
        tokens.update(SKILL_ALIASES.get(token, []))
    return tokens


def _skill_overlap(item: dict, skill_tokens: set[str]) -> int:
    tag_tokens = set(_tokenize(" ".join(item["tags"] + [item["topic"], item["category"]])))
    return len(skill_tokens & tag_tokens)


def _category_weights(focus: str) -> dict[str, float]:
    if focus == "backend":
        return {"backend": 1.5, "frontend": 0.55, "agent": 0.7}
    if focus == "agent":
        return {"agent": 1.5, "backend": 0.7, "frontend": 0.6}
    return {"frontend": 1.45, "agent": 0.7, "backend": 0.55}


def _kb_newer_than_index() -> bool:
    if not INDEX_PATH.is_file():
        return True
    index_mtime = INDEX_PATH.stat().st_mtime
    for path in KB_DIR.rglob("*"):
        if path.is_file() and path.stat().st_mtime > index_mtime:
            return True
    return False
