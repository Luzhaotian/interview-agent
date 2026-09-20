from __future__ import annotations

import os
from contextvars import ContextVar
from pathlib import Path
from typing import Callable, Iterator

from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

_reasoning_hook: ContextVar[Callable[[str], None] | None] = ContextVar("reasoning_hook", default=None)


def question_count(override: int | None = None) -> int:
    if override is not None:
        raw = override
    else:
        raw_text = (os.getenv("QUESTION_COUNT") or "15").strip() or "15"
        raw = int(raw_text)
    return max(10, min(20, raw))


def bind_reasoning(hook: Callable[[str], None]):
    return _reasoning_hook.set(hook)


def unbind_reasoning(token) -> None:
    _reasoning_hook.reset(token)


def complete_text(prompt: str) -> str:
    return "".join(iter_model([{"role": "user", "content": prompt}], yield_content=True))


def iter_model(messages: list[dict], yield_content: bool = True) -> Iterator[str]:
    """流式调用 DeepSeek，把 reasoning_content 交给当前思考回调，正文按片段返回。"""
    client = OpenAI(
        api_key=_api_key(),
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        timeout=120,
    )
    stream = client.chat.completions.create(
        model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        messages=messages,
        stream=True,
        temperature=0.2,
        extra_body={"thinking": {"type": "enabled"}},
    )
    for chunk in stream:
        choices = getattr(chunk, "choices", None) or []
        if not choices:
            continue
        delta = choices[0].delta
        reasoning = _reasoning_text(delta)
        if reasoning:
            hook = _reasoning_hook.get()
            if hook:
                hook(reasoning)
        if yield_content:
            content = getattr(delta, "content", None) or ""
            if content:
                yield str(content)


def _api_key() -> str:
    key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not key:
        raise SystemExit("请先复制 .env.example 为 .env，并填写 DEEPSEEK_API_KEY")
    return key


def _reasoning_text(delta) -> str:
    text = getattr(delta, "reasoning_content", None)
    if text:
        return str(text)
    extra = getattr(delta, "model_extra", None) or {}
    return str(extra.get("reasoning_content") or "")
