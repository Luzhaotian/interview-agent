"""本机文本向量 + 余弦相似度（不依赖向量数据库）。

默认 backend=local：TF-IDF → TruncatedSVD 稠密向量（纯本机，适合学习公式）。
可选 backend=neural：fastembed + BGE 中文小模型（需能下载 Hugging Face / 镜像）。

学习要点：
1. ingest 时为每道题生成向量，写入 data/embeddings.npz
2. 查询向量与题库矩阵做余弦相似度（已 L2 归一化，点积即可）
3. 无数据库：几百道题放内存足够
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Iterable

import numpy as np

# 国内访问 Hugging Face 常超时；neural 模式可走镜像
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

ROOT = Path(__file__).resolve().parents[1]
EMBEDDINGS_PATH = ROOT / "data" / "embeddings.npz"
VECTORIZER_PATH = ROOT / "data" / "vectorizer.joblib"
MODEL_NAME = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")
# local = TF-IDF+SVD；neural = fastembed；auto = 有缓存模型则 neural，否则 local
BACKEND = os.getenv("EMBEDDING_BACKEND", "local")


def embed_corpus(texts: Iterable[str]) -> np.ndarray:
    """建库：拟合编码器并返回 (n, dim) 归一化矩阵。"""
    cleaned = [text.strip() or "空" for text in texts]
    backend = _resolve_backend()
    if backend == "neural":
        vectors = np.asarray(list(_neural_model().embed(cleaned)), dtype=np.float32)
        return _l2_normalize(vectors)

    from joblib import dump

    pipe = _new_local_pipeline()
    matrix = pipe.fit_transform(cleaned)
    if hasattr(matrix, "toarray"):
        matrix = matrix.toarray()
    dump(pipe, VECTORIZER_PATH)
    return _l2_normalize(np.asarray(matrix, dtype=np.float32))


def embed_query(text: str) -> np.ndarray:
    """查询：用与建库同一套编码器。"""
    cleaned = text.strip() or "空"
    backend = _resolve_backend()
    if backend == "neural":
        vectors = np.asarray(list(_neural_model().embed([cleaned])), dtype=np.float32)
        return _l2_normalize(vectors)[0]

    from joblib import load

    if not VECTORIZER_PATH.is_file():
        raise SystemExit("缺少 data/vectorizer.joblib，请先运行 python main.py ingest")
    pipe = load(VECTORIZER_PATH)
    matrix = pipe.transform([cleaned])
    if hasattr(matrix, "toarray"):
        matrix = matrix.toarray()
    return _l2_normalize(np.asarray(matrix, dtype=np.float32))[0]


def cosine_scores(query: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """query 与矩阵每行的余弦相似度。两侧已归一化时等于点积。"""
    q = _l2_normalize(query.reshape(1, -1))[0]
    m = _l2_normalize(matrix)
    return m @ q


def save_embeddings(ids: list[str], matrix: np.ndarray) -> None:
    EMBEDDINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        EMBEDDINGS_PATH,
        ids=np.asarray(ids, dtype=object),
        vectors=_l2_normalize(np.asarray(matrix, dtype=np.float32)),
        model=np.asarray(_model_label()),
        backend=np.asarray(_resolve_backend()),
    )


def load_embeddings() -> tuple[list[str], np.ndarray, str, str] | None:
    if not EMBEDDINGS_PATH.is_file():
        return None
    data = np.load(EMBEDDINGS_PATH, allow_pickle=True)
    ids = [str(item) for item in data["ids"].tolist()]
    vectors = np.asarray(data["vectors"], dtype=np.float32)
    model = str(data["model"]) if "model" in data.files else ""
    backend = str(data["backend"]) if "backend" in data.files else "local"
    return ids, vectors, model, backend


def embeddings_match(questions: list[dict]) -> bool:
    loaded = load_embeddings()
    if not loaded:
        return False
    ids, vectors, model, backend = loaded
    if backend != _resolve_backend():
        return False
    if backend == "neural" and model != MODEL_NAME:
        return False
    if backend == "local" and not VECTORIZER_PATH.is_file():
        return False
    if ids != [item["id"] for item in questions]:
        return False
    return vectors.shape[0] == len(questions)


def active_backend() -> str:
    return _resolve_backend()


def _model_label() -> str:
    if _resolve_backend() == "neural":
        return MODEL_NAME
    return "tfidf-svd-char3-256"


@lru_cache(maxsize=1)
def _resolve_backend() -> str:
    choice = (BACKEND or "local").strip().lower()
    if choice == "neural":
        _neural_model()
        return "neural"
    if choice == "auto":
        try:
            _neural_model()
            return "neural"
        except Exception as exc:  # noqa: BLE001
            print(f"语义向量模型不可用（{exc}），改用本机 TF-IDF+SVD。")
            return "local"
    return "local"


@lru_cache(maxsize=1)
def _neural_model():
    from fastembed import TextEmbedding

    print(f"加载向量模型 {MODEL_NAME}（首次会下载）…")
    return TextEmbedding(model_name=MODEL_NAME)


def _new_local_pipeline():
    from sklearn.decomposition import TruncatedSVD
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import Normalizer

    # 中文用字级 n-gram，不额外依赖分词模型
    vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(1, 3),
        min_df=1,
        max_features=12000,
    )
    svd = TruncatedSVD(n_components=256, random_state=42)
    return make_pipeline(vectorizer, svd, Normalizer(copy=False))


def _l2_normalize(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=-1, keepdims=True)
    norms = np.maximum(norms, 1e-12)
    return matrix / norms
