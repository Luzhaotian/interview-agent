#!/usr/bin/env bash
# 同时启动后端 (127.0.0.1:8000) 和前端 (默认 5173)。Ctrl+C 会一起停掉。
set -euo pipefail
set -m

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_PID=""
WEB_PID=""

node_satisfies_web() {
  command -v node >/dev/null 2>&1 || return 1
  node -e 'const [major, minor] = process.versions.node.split(".").map(Number); const ok = (major === 22 && minor >= 18) || major > 24 || (major === 24 && minor >= 12); process.exit(ok ? 0 : 1)'
}

load_node() {
  local nvm_dir="${NVM_DIR:-$HOME/.nvm}"
  if [[ -s "$nvm_dir/nvm.sh" ]]; then
    export NVM_DIR="$nvm_dir"
    # nvm.sh 自己会打开 set -e，并以非 0 返回。这里先关掉，避免脚本直接退出。
    set +e
    set +u
    # shellcheck disable=SC1091
    . "$NVM_DIR/nvm.sh"
    set +e
    if [[ -f "$ROOT/.nvmrc" ]]; then
      nvm use "$(tr -d '[:space:]' < "$ROOT/.nvmrc")" >/dev/null 2>&1 || true
    elif ! node_satisfies_web; then
      nvm use 26 >/dev/null 2>&1 || true
    fi
    set -e
    set -u
  fi

  if ! command -v npm >/dev/null 2>&1; then
    echo "未找到 npm。当前 shell 用的是 nvm，先执行 nvm use 26。" >&2
    exit 1
  fi
  if ! node_satisfies_web; then
    echo "当前 Node 是 $(node -v)，前端需要 22.18 或以上（也支持 24.12 及以上）。" >&2
    exit 1
  fi
}

kill_tree() {
  local pid="$1"
  local child
  [[ -n "$pid" ]] || return 0
  while IFS= read -r child; do
    [[ -n "$child" ]] && kill_tree "$child"
  done < <(pgrep -P "$pid" 2>/dev/null || true)
  kill "$pid" 2>/dev/null || true
}

cleanup() {
  local code="${1:-$?}"
  trap - EXIT INT TERM
  kill_tree "$BACKEND_PID"
  kill_tree "$WEB_PID"
  wait 2>/dev/null || true
  exit "$code"
}

trap 'cleanup 130' INT
trap 'cleanup 143' TERM
trap cleanup EXIT

if [[ -x "$ROOT/backend/.venv/bin/python" ]]; then
  PYTHON="$ROOT/backend/.venv/bin/python"
elif [[ -x "$ROOT/backend/venv/bin/python" ]]; then
  PYTHON="$ROOT/backend/venv/bin/python"
else
  echo "未找到 Python 虚拟环境。请先在 backend 目录执行：" >&2
  echo "  python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt" >&2
  exit 1
fi

load_node

if [[ ! -x "$ROOT/web/node_modules/.bin/vite" ]]; then
  echo "正在安装前端依赖…"
  (cd "$ROOT/web" && npm install)
fi

if [[ ! -f "$ROOT/backend/.env" ]]; then
  echo "提示：还没有 backend/.env，服务能启动，但生成题目会失败。" >&2
  echo "  cp backend/.env.example backend/.env" >&2
fi

echo "正在启动后端 http://127.0.0.1:8000"
(
  cd "$ROOT/backend"
  exec "$PYTHON" main.py serve
) &
BACKEND_PID=$!

ready=0
for _ in $(seq 1 60); do
  if curl -sf "http://127.0.0.1:8000/api/health" >/dev/null; then
    ready=1
    break
  fi
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "后端启动失败。" >&2
    wait "$BACKEND_PID" || true
    exit 1
  fi
  sleep 0.5
done

if [[ "$ready" -ne 1 ]]; then
  echo "后端在 30 秒内没有就绪。" >&2
  exit 1
fi

echo "后端已就绪。正在启动前端 http://127.0.0.1:5173"
echo "按 Ctrl+C 同时停止前后端。"
(
  cd "$ROOT/web"
  exec npm run dev
) &
WEB_PID=$!

while kill -0 "$BACKEND_PID" 2>/dev/null && kill -0 "$WEB_PID" 2>/dev/null; do
  sleep 1
done

if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
  echo "后端已退出。" >&2
  wait "$BACKEND_PID" || true
  exit 1
fi

echo "前端已退出。" >&2
wait "$WEB_PID" || true
exit 1
