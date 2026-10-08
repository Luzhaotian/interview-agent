from __future__ import annotations


class AgentError(RuntimeError):
    """业务级可预期错误。

    库里一律抛这个而不是 SystemExit：
    - CLI（main.py）捕获后打印消息并以退出码 1 结束
    - HTTP（api.py）捕获后转 4xx/5xx
    - 流程内允许降级的地方可以用普通 ``except Exception`` 捕获
      （SystemExit 继承 BaseException，``except Exception`` 捕不到，兜底会变死代码）
    """
