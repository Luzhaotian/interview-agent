"""AgentError 语义：业务错误必须能被 except Exception 捕获，兜底才不是死代码。"""

from __future__ import annotations

import pytest

from src.errors import AgentError
from src.graph import _load_json


def test_agent_error_is_ordinary_exception():
    # SystemExit 继承 BaseException，except Exception 捕不到；AgentError 必须能捕到，
    # 否则 graph.py 里那些 except Exception 的降级分支全是死代码。
    assert issubclass(AgentError, Exception)
    assert not issubclass(SystemExit, Exception)

    caught = False
    try:
        raise AgentError("boom")
    except Exception:
        caught = True
    assert caught


def test_load_json_raises_agent_error_on_garbage():
    """_load_json 失败时抛 AgentError，而不是 SystemExit。"""
    with pytest.raises(AgentError):
        _load_json("模型说了一段没有 JSON 的话")


def test_load_json_parses_fenced_json():
    assert _load_json('```json\n[{"id": "x"}]\n```') == [{"id": "x"}]
