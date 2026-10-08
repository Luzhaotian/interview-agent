from __future__ import annotations

from pathlib import Path


from src.errors import AgentError
def read_resume(path: Path) -> str:
    if not path.is_file():
        raise AgentError(f"找不到简历文件：{path}")

    suffix = path.suffix.lower()
    if suffix == ".pdf":
        text = _read_pdf(path)
    elif suffix == ".docx":
        text = _read_docx(path)
    elif suffix in {".md", ".txt", ".markdown"}:
        text = path.read_text(encoding="utf-8")
    else:
        raise AgentError("简历只支持 PDF、DOCX、Markdown、TXT")

    text = text.strip()
    if not text:
        raise AgentError(f"简历是空的：{path}")
    return text


def _read_pdf(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _read_docx(path: Path) -> str:
    from docx import Document

    document = Document(str(path))
    return "\n".join(paragraph.text for paragraph in document.paragraphs)
