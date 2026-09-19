from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp.server.mcpserver import MCPServer

from src.web_questions import search_interview_questions

server = MCPServer("interview-web")


@server.tool(
    name="search_interview_questions",
    title="联网查面试题",
    description="按技术主题上网检索公开面试题，返回题目、来源标题和链接。不会写入本地知识库。",
)
def search_interview_questions_tool(topic: str, limit: int = 8) -> str:
    """联网检索面试题。

    topic 是技术主题，例如「Vue3 响应式」「MySQL 索引」「RAG」。
    limit 是希望返回的题目条数，范围 1 到 12，默认 8。
    """
    return search_interview_questions(topic, limit)


if __name__ == "__main__":
    server.run(transport="stdio")
