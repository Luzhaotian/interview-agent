"""MCP 工具目录。页面和 MCP 服务共用这份说明，避免两处文案分开改。"""

SERVER_NAME = "interview-web"

SERVER = {
    "name": SERVER_NAME,
    "transport": "stdio",
    "config": ".cursor/mcp.json",
    "command": "bash backend/run_mcp.sh",
    "summary": (
        "联网查面试题服务。推荐流程在扫描简历后若发现知识库缺口，"
        "会自动调用同一工具 search_interview_questions 补题；"
        "Cursor 里也可手动调用。网页抽屉只展示接口说明。"
    ),
}

TOOLS = [
    {
        "name": "search_interview_questions",
        "title": "联网查面试题",
        "description": (
            "按技术主题上网检索公开面试题，返回题目、来源标题和链接。"
            "推荐链路在知识库缺少对应技能题时自动调用；结果不写入本地知识库。"
        ),
        "parameters": [
            {
                "name": "topic",
                "type": "string",
                "required": True,
                "description": "技术主题，例如「Vue3 响应式」「MySQL 索引」「RAG」。",
            },
            {
                "name": "limit",
                "type": "integer",
                "required": False,
                "default": 8,
                "description": "希望返回的题目条数，范围 1 到 12，默认 8。",
            },
        ],
    }
]
