"""向量相似度纯函数测试（不加载 embedding 模型）。"""

from __future__ import annotations

import numpy as np

from src.embeddings import cosine_scores, _l2_normalize


def test_cosine_identical_vectors():
    matrix = _l2_normalize(np.asarray([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32))
    query = np.asarray([1.0, 0.0], dtype=np.float32)
    scores = cosine_scores(query, matrix)
    assert scores[0] > 0.99
    assert abs(float(scores[1])) < 0.01


def test_cosine_ranks_closer_first():
    matrix = _l2_normalize(
        np.asarray(
            [
                [1.0, 0.1, 0.0],
                [0.0, 1.0, 0.0],
                [0.9, 0.2, 0.0],
            ],
            dtype=np.float32,
        )
    )
    query = np.asarray([1.0, 0.0, 0.0], dtype=np.float32)
    scores = cosine_scores(query, matrix)
    order = list(np.argsort(-scores))
    assert order[0] in (0, 2)
    assert order[-1] == 1
