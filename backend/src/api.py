from __future__ import annotations

import json
import queue
import threading
import warnings
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Optional

warnings.filterwarnings("ignore", message=".*LibreSSL.*")
warnings.filterwarnings("ignore", message=".*allowed_objects.*")

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.graph import (
    build_graph,
    iter_chat_events,
    run_recommend_stream,
    run_screen_stream,
    stream_chat_tokens,
    stream_intro_tokens,
)
from src.kb import load_index
from src.llm import bind_reasoning, question_count, unbind_reasoning
from src.mcp_catalog import SERVER, TOOLS

ALLOWED_SUFFIXES = {".pdf", ".docx", ".md", ".markdown", ".txt"}
MAX_UPLOAD_FILES = 8

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
    questions = _questions_or_http()
    counts: dict[str, int] = {}
    for item in questions:
        counts[item["category"]] = counts.get(item["category"], 0) + 1
    return {"total": len(questions), "counts": counts}


@app.get("/api/kb/questions")
def kb_questions() -> dict:
    questions = _questions_or_http()
    return {"total": len(questions), "questions": [_public_kb_item(item) for item in questions]}


@app.get("/api/mcp")
def mcp() -> dict:
    return {"server": SERVER, "tools": TOOLS}


class ChatTurn(BaseModel):
    role: str
    content: str


class ChatBody(BaseModel):
    messages: list[ChatTurn] = Field(min_length=1)
    context: str = ""
    selected_ids: list[str] = Field(default_factory=list)
    profile: Optional[dict] = None
    count: int = 5


@app.post("/api/chat")
def chat(body: ChatBody) -> dict:
    turns = _parse_chat_turns(body)
    context = body.context.strip()[:12000] or "（无）"
    try:
        reply = "".join(stream_chat_tokens(turns, context)).strip()
    except SystemExit as exc:
        raise HTTPException(status_code=400, detail=_exit_message(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"回复失败：{exc}") from exc
    if not reply:
        raise HTTPException(status_code=500, detail="模型没有返回内容")
    return {"reply": reply}


@app.post("/api/chat/stream")
def chat_stream(body: ChatBody) -> StreamingResponse:
    turns = _parse_chat_turns(body)
    context = body.context.strip()[:12000] or "（无）"
    selected_ids = [str(item) for item in body.selected_ids if str(item).strip()]
    count = max(3, min(8, int(body.count or 5)))

    def events():
        events_queue: queue.Queue = queue.Queue()

        def on_event(payload: dict) -> None:
            events_queue.put(payload)

        def worker() -> None:
            token = bind_reasoning(
                lambda text: on_event({"type": "thinking", "text": text, "append": True})
            )
            try:
                for payload in iter_chat_events(
                    turns,
                    context,
                    profile=body.profile,
                    selected_ids=selected_ids,
                    count=count,
                ):
                    on_event(payload)
            except SystemExit as exc:
                on_event({"type": "error", "detail": _exit_message(exc)})
            except Exception as exc:
                on_event({"type": "error", "detail": f"回复失败：{exc}"})
            finally:
                unbind_reasoning(token)
                events_queue.put(None)

        threading.Thread(target=worker, daemon=True).start()
        while True:
            item = events_queue.get()
            if item is None:
                break
            yield _sse(item)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/recommend")
async def recommend(files: list[UploadFile] = File(...), count: int = Form(15)) -> dict:
    saved = await _save_uploads(files)
    target_count = question_count(count)
    results: list[dict] = []
    try:
        for name, path in saved:
            result = build_graph().invoke(
                {
                    "resume_path": str(path),
                    "question_count": target_count,
                }
            )
            results.append(
                {
                    "name": name,
                    "profile": result["profile"],
                    "questions": [_public_question(item) for item in result["selected"]],
                }
            )
    except SystemExit as exc:
        raise HTTPException(status_code=400, detail=_exit_message(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"生成失败：{exc}") from exc
    finally:
        _cleanup_paths([path for _, path in saved])

    payload: dict = {"results": results}
    if len(results) == 1:
        payload["profile"] = results[0]["profile"]
        payload["questions"] = results[0]["questions"]
    return payload


@app.post("/api/recommend/stream")
async def recommend_stream(
    files: list[UploadFile] = File(...), count: int = Form(15)
) -> StreamingResponse:
    saved = await _save_uploads(files)
    target_count = question_count(count)

    def events():
        events_queue: queue.Queue = queue.Queue()

        def on_event(payload: dict) -> None:
            events_queue.put(payload)

        def worker() -> None:
            token = bind_reasoning(
                lambda text: on_event({"type": "thinking", "text": text, "append": True})
            )
            try:
                total = len(saved)
                for index, (name, path) in enumerate(saved, start=1):
                    on_event({"type": "resume", "name": name, "index": index, "total": total})
                    try:
                        state = run_recommend_stream(str(path), target_count, on_event=on_event)
                        for piece in stream_intro_tokens(state["profile"], state["selected"]):
                            on_event({"type": "token", "text": piece})
                    except SystemExit as exc:
                        on_event({"type": "error", "name": name, "detail": _exit_message(exc)})
                    except Exception as exc:
                        on_event({"type": "error", "name": name, "detail": f"生成失败：{exc}"})
                events_queue.put({"type": "done"})
            finally:
                unbind_reasoning(token)
                _cleanup_paths([path for _, path in saved])
                events_queue.put(None)

        threading.Thread(target=worker, daemon=True).start()
        while True:
            item = events_queue.get()
            if item is None:
                break
            yield _sse(item)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/screen/stream")
async def screen_stream(files: list[UploadFile] = File(...)) -> StreamingResponse:
    saved = await _save_uploads(files)

    def events():
        events_queue: queue.Queue = queue.Queue()

        def on_event(payload: dict) -> None:
            events_queue.put(payload)

        def worker() -> None:
            token = bind_reasoning(
                lambda text: on_event({"type": "thinking", "text": text, "append": True})
            )
            try:
                total = len(saved)
                for index, (name, path) in enumerate(saved, start=1):
                    on_event({"type": "resume", "name": name, "index": index, "total": total})
                    try:
                        run_screen_stream(str(path), on_event=on_event)
                    except SystemExit as exc:
                        on_event({"type": "error", "name": name, "detail": _exit_message(exc)})
                    except Exception as exc:
                        on_event({"type": "error", "name": name, "detail": f"判断失败：{exc}"})
                events_queue.put({"type": "done"})
            finally:
                unbind_reasoning(token)
                _cleanup_paths([path for _, path in saved])
                events_queue.put(None)

        threading.Thread(target=worker, daemon=True).start()
        while True:
            item = events_queue.get()
            if item is None:
                break
            yield _sse(item)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _save_uploads(uploads: list[UploadFile]) -> list[tuple[str, Path]]:
    if not uploads:
        raise HTTPException(status_code=400, detail="请至少上传一个文件")
    if len(uploads) > MAX_UPLOAD_FILES:
        raise HTTPException(status_code=400, detail=f"一次最多 {MAX_UPLOAD_FILES} 个文件")
    saved: list[tuple[str, Path]] = []
    try:
        for item in uploads:
            path = await _save_upload(item)
            name = Path(item.filename or path.name).name.replace("\n", " ")
            saved.append((name, path))
    except Exception:
        _cleanup_paths([path for _, path in saved])
        raise
    return saved


async def _save_upload(file: UploadFile) -> Path:
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
        return Path(tmp.name)


def _cleanup_paths(paths: list[Path]) -> None:
    for path in paths:
        path.unlink(missing_ok=True)


def _parse_chat_turns(body: ChatBody) -> list[tuple[str, str]]:
    turns: list[tuple[str, str]] = []
    for item in body.messages[-12:]:
        if item.role not in {"user", "assistant"}:
            raise HTTPException(status_code=400, detail="消息角色只能是 user 或 assistant")
        text = item.content.strip()
        if text:
            turns.append((item.role, text[:8000]))
    if not turns or turns[-1][0] != "user":
        raise HTTPException(status_code=400, detail="请先写一条要发送的消息")
    return turns


def _questions_or_http() -> list[dict]:
    try:
        return load_index()
    except SystemExit as exc:
        raise HTTPException(status_code=500, detail=_exit_message(exc)) from exc


def _public_kb_item(item: dict) -> dict:
    return {
        "id": item["id"],
        "category": item["category"],
        "topic": item["topic"],
        "tags": item.get("tags") or [],
        "difficulty": item["difficulty"],
        "question": item["question"],
        "answer_outline": item["answer_outline"],
    }


def _public_question(item: dict) -> dict:
    from src.graph import _default_direction

    stage = item.get("stage", "foundation")
    return {
        "id": item["id"],
        "category": item["category"],
        "topic": item["topic"],
        "difficulty": item["difficulty"],
        "stage": stage,
        "question": item["question"],
        "reason": item.get("reason", ""),
        "answer_direction": item.get("answer_direction") or _default_direction(item, stage),
        "reference_answer": item.get("reference_answer") or item["answer_outline"],
        "answer_outline": item["answer_outline"],
        "source": item.get("source") or "kb",
        "source_title": item.get("source_title") or "",
        "source_url": item.get("source_url") or "",
    }


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _exit_message(exc: SystemExit) -> str:
    if isinstance(exc.code, str) and exc.code:
        return exc.code
    return "请求失败"
