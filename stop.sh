#!/bin/bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_DIR="$ROOT_DIR/.runtime/pids"

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

BACKEND_PID_FILE="$PID_DIR/backend.pid"
FRONTEND_PID_FILE="$PID_DIR/frontend.pid"

port_pids() {
  local port="$1"
  lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true
}

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

echo "停止服务..."

stop_pid_file "$BACKEND_PID_FILE" "后端"
stop_pid_file "$FRONTEND_PID_FILE" "前端"
stop_port_processes "$BACKEND_PORT" "后端"
stop_port_processes "$FRONTEND_PORT" "前端"

echo "服务已全部停止"
