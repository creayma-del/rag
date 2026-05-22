#!/bin/bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
RUNTIME_DIR="$ROOT_DIR/.runtime"
LOG_DIR="$RUNTIME_DIR/logs"
PID_DIR="$RUNTIME_DIR/pids"
PYTHON_BIN="${PYTHON_BIN:-python3}"

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

mkdir -p "$LOG_DIR" "$PID_DIR"

BACKEND_LOG="$LOG_DIR/backend.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"
BACKEND_PID_FILE="$PID_DIR/backend.pid"
FRONTEND_PID_FILE="$PID_DIR/frontend.pid"

# ============================================================
# 停止旧服务
# ============================================================

stop_pid_file() {
  local pid_file="$1"
  local service_name="$2"

  if [ ! -f "$pid_file" ]; then
    return
  fi

  local pid
  pid="$(cat "$pid_file" 2>/dev/null || true)"
  if [ -n "${pid:-}" ] && kill -0 "$pid" 2>/dev/null; then
    echo "停止 $service_name 进程: $pid"
    kill "$pid" 2>/dev/null || true
    sleep 1
    if kill -0 "$pid" 2>/dev/null; then
      echo "强制停止 $service_name 进程: $pid"
      kill -9 "$pid" 2>/dev/null || true
    fi
  fi

  rm -f "$pid_file"
}

stop_port_processes() {
  local port="$1"
  local service_name="$2"
  local pids

  pids="$(port_pids "$port")"
  if [ -z "$pids" ]; then
    return
  fi

  echo "清理占用端口 $port 的 $service_name 进程: $pids"
  for pid in $pids; do
    kill "$pid" 2>/dev/null || true
  done

  sleep 1

  pids="$(port_pids "$port")"
  if [ -n "$pids" ]; then
    echo "强制清理占用端口 $port 的 $service_name 进程: $pids"
    for pid in $pids; do
      kill -9 "$pid" 2>/dev/null || true
    done
  fi
}

stop_existing_services() {
  stop_pid_file "$BACKEND_PID_FILE" "后端"
  stop_pid_file "$FRONTEND_PID_FILE" "前端"
  stop_port_processes "$BACKEND_PORT" "后端"
  stop_port_processes "$FRONTEND_PORT" "前端"
}

# ============================================================
# 依赖检查
# ============================================================

# 后端关键 Python 包（覆盖 requirements.txt 中的核心依赖）
BACKEND_PACKAGES=(
  fastapi
  uvicorn
  langchain
  chromadb
  openai
  torch
  sentence_transformers
  pydantic
)

check_python_dependencies() {
  echo "检查 Python 依赖..."
  local missing=()

  for pkg in "${BACKEND_PACKAGES[@]}"; do
    if ! "$PYTHON_BIN" -c "import $pkg" 2>/dev/null; then
      missing+=("$pkg")
    fi
  done

  if [ ${#missing[@]} -eq 0 ]; then
    echo "Python 依赖完整"
  else
    echo "缺少 Python 依赖: ${missing[*]}"
    echo "正在安装 Python 依赖..."
    cd "$BACKEND_DIR"
    "$PYTHON_BIN" -m pip install -r requirements.txt
    cd "$ROOT_DIR"
  fi
}

check_pnpm() {
  if ! command -v pnpm &>/dev/null; then
    echo "pnpm 未安装，正在安装..."
    npm install -g pnpm
  fi
}

check_frontend_dependencies() {
  echo "检查前端依赖..."
  cd "$FRONTEND_DIR"

  if [ ! -d "node_modules" ]; then
    echo "node_modules 不存在，正在安装前端依赖..."
    pnpm install
  else
    # 检查 package.json 中的依赖是否已全部安装
    local missing
    missing="$(pnpm ls --depth 0 2>/dev/null | grep -c "ERR" || true)"
    if [ "$missing" -gt 0 ] 2>/dev/null; then
      echo "检测到缺失的前端依赖，正在安装..."
      pnpm install
    else
      echo "前端依赖完整"
    fi
  fi

  cd "$ROOT_DIR"
}

# ============================================================
# 服务启动
# ============================================================

port_pids() {
  local port="$1"
  lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true
}

wait_for_port() {
  local port="$1"
  local service_name="$2"
  local retries="${3:-20}"

  for _ in $(seq 1 "$retries"); do
    if [ -n "$(port_pids "$port")" ]; then
      echo "$service_name 已启动，监听端口 $port"
      return 0
    fi
    sleep 1
  done

  echo "$service_name 启动失败，端口 $port 未就绪"
  return 1
}

start_backend() {
  echo "启动后端服务 (端口 $BACKEND_PORT)..."
  cd "$BACKEND_DIR"
  nohup "$PYTHON_BIN" -m uvicorn api:app --host 0.0.0.0 --port "$BACKEND_PORT" >"$BACKEND_LOG" 2>&1 &
  echo $! >"$BACKEND_PID_FILE"

  if ! wait_for_port "$BACKEND_PORT" "后端"; then
    echo "后端日志:"
    tail -n 50 "$BACKEND_LOG" || true
    exit 1
  fi
  cd "$ROOT_DIR"
}

start_frontend() {
  echo "启动前端服务 (端口 $FRONTEND_PORT)..."
  cd "$FRONTEND_DIR"
  nohup pnpm dev --host 0.0.0.0 --port "$FRONTEND_PORT" --strictPort >"$FRONTEND_LOG" 2>&1 &
  echo $! >"$FRONTEND_PID_FILE"

  if ! wait_for_port "$FRONTEND_PORT" "前端"; then
    echo "前端日志:"
    tail -n 50 "$FRONTEND_LOG" || true
    exit 1
  fi
  cd "$ROOT_DIR"
}

# ============================================================
# 主流程
# ============================================================

echo "启动个人知识库 RAG"

stop_existing_services

check_python_dependencies
check_pnpm
check_frontend_dependencies

start_backend
start_frontend

echo ""
echo "服务已启动!"
echo "后端 API: http://localhost:$BACKEND_PORT"
echo "前端界面: http://localhost:$FRONTEND_PORT"
echo "后端日志: $BACKEND_LOG"
echo "前端日志: $FRONTEND_LOG"
echo ""
echo "按 Ctrl+C 停止所有服务"

trap "echo '正在停止服务...'; bash '$ROOT_DIR/stop.sh'; exit" INT

wait
