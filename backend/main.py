from __future__ import annotations

import argparse
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", message=".*LibreSSL.*")
warnings.filterwarnings("ignore", message=".*allowed_objects.*")

from src.graph import build_graph
from src.kb import ingest
from src.llm import question_count


def main() -> None:
    parser = argparse.ArgumentParser(description="根据简历和知识库推荐面试题")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("ingest", help="扫描 kb/ 并重建本地检索索引")

    recommend = sub.add_parser("recommend", help="扫描简历并推荐 10-20 道面试题")
    recommend.add_argument("resume", help="简历路径，支持 PDF、DOCX、Markdown、TXT")
    recommend.add_argument("--count", type=int, default=None, help="题目数量，限制在 10 到 20")

    serve = sub.add_parser("serve", help="启动 HTTP 服务，供前端调用")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)

    args = parser.parse_args()
    if args.command == "serve":
        import uvicorn

        from src.api import app

        uvicorn.run(app, host=args.host, port=args.port)
        return

    if args.command == "ingest":
        questions = ingest()
        counts = _count_by_category(questions)
        print(
            f"已索引 {len(questions)} 道题（含向量）："
            f"前端 {counts.get('frontend', 0)}，"
            f"Agent {counts.get('agent', 0)}，"
            f"后端 {counts.get('backend', 0)}"
        )
        return

    result = build_graph().invoke(
        {
            "resume_path": str(Path(args.resume).expanduser().resolve()),
            "question_count": question_count(args.count),
        }
    )
    print(result["report"])
    print(f"报告已写入 {result['report_path']}")


def _count_by_category(questions: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in questions:
        counts[item["category"]] = counts.get(item["category"], 0) + 1
    return counts


if __name__ == "__main__":
    main()
