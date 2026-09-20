from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULES_DIR = ROOT / "rules"
_COMMENT = re.compile(r"<!--.*?-->", re.S)

# 规则文件缺失时的兜底，与 interview-gate 默认标准一致。
GATE_FALLBACK = """必须同时满足，缺一条就是不推荐：

- 前端基础精通
- 熟悉 AI
- 有企业级 AI 项目
- 企业级 AI 项目至少要一个

先给结论，只能是「推荐面试」或「不推荐面试」。推荐就写推荐面试的理由，不推荐就写不推荐的理由。每条理由对应一条标准，并指出简历里的依据。简历没写的，明确说材料不足，不要算作满足。
"""


def load_rule(name: str) -> str:
    """读取 backend/rules/<name>.md。文件不存在或只有注释时返回空字符串。"""
    path = RULES_DIR / f"{name}.md"
    if not path.is_file():
        return ""
    text = _COMMENT.sub("", path.read_text(encoding="utf-8"))
    return text.strip()


def gate_playbook() -> str:
    return load_rule("interview-gate") or GATE_FALLBACK


def playbook_block(name: str, title: str) -> str:
    text = load_rule(name)
    if not text:
        return ""
    return f"\n{title}\n{text}\n"
