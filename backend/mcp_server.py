from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp.server.mcpserver import MCPServer

from src.mcp_catalog import SERVER_NAME, TOOLS
from src.web_questions import search_interview_questions

server = MCPServer(SERVER_NAME)
_search_tool = TOOLS[0]


@server.tool(
    name=_search_tool["name"],
    title=_search_tool["title"],
    description=_search_tool["description"],
)
def search_interview_questions_tool(topic: str, limit: int = 8) -> str:
    """联网检索面试题。

    topic 是技术主题，例如「Vue3 响应式」「MySQL 索引」「RAG」。
    limit 是希望返回的题目条数，范围 1 到 12，默认 8。
    """
    return search_interview_questions(topic, limit)


if __name__ == "__main__":
    server.run(transport="stdio")
