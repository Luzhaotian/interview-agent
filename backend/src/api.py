from __future__ import annotations

import warnings
from pathlib import Path
from tempfile import NamedTemporaryFile

warnings.filterwarnings("ignore", message=".*LibreSSL.*")
warnings.filterwarnings("ignore", message=".*allowed_objects.*")

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from src.graph import build_graph
from src.kb import load_index
from src.llm import question_count

ALLOWED_SUFFIXES = {".pdf", ".docx", ".md", ".markdown", ".txt"}

app = FastAPI(title="interview-agent")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.get("/api/kb")
def kb() -> dict:
    try:
        questions = load_index()
    except SystemExit as exc:
        raise HTTPException(status_code=500, detail=_exit_message(exc)) from exc
    counts: dict[str, int] = {}
    for item in questions:
        counts[item["category"]] = counts.get(item["category"], 0) + 1
    return {"total": len(questions), "counts": counts}


@app.post("/api/recommend")
async def recommend(file: UploadFile = File(...), count: int = Form(15)) -> dict:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=400, detail="简历只支持 PDF、DOCX、Markdown、TXT")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="简历是空的")
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="简历文件不能超过 10MB")

    with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(data)
        path = Path(tmp.name)

    try:
        result = build_graph().invoke(
            {
                "resume_path": str(path),
                "question_count": question_count(count),
            }
        )
    except SystemExit as exc:
        raise HTTPException(status_code=400, detail=_exit_message(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"生成失败：{exc}") from exc
    finally:
        path.unlink(missing_ok=True)

    return {
        "profile": result["profile"],
        "questions": [_public_question(item) for item in result["selected"]],
    }


def _public_question(item: dict) -> dict:
    return {
        "id": item["id"],
        "category": item["category"],
        "topic": item["topic"],
        "difficulty": item["difficulty"],
        "question": item["question"],
        "reason": item.get("reason", ""),
        "answer_outline": item["answer_outline"],
    }


def _exit_message(exc: SystemExit) -> str:
    if isinstance(exc.code, str) and exc.code:
        return exc.code
    return "请求失败"
