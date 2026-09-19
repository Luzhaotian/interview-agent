from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def question_count(override: int | None = None) -> int:
    if override is not None:
        raw = override
    else:
        raw_text = (os.getenv("QUESTION_COUNT") or "15").strip() or "15"
        raw = int(raw_text)
    return max(10, min(20, raw))


def get_llm() -> ChatOpenAI:
    key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not key:
        raise SystemExit("请先复制 .env.example 为 .env，并填写 DEEPSEEK_API_KEY")
    return ChatOpenAI(
        model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        api_key=key,
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        temperature=0.2,
        timeout=90,
    )
