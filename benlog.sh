#!/usr/bin/env bash
# === 🧠 Benlog 一体化管理脚本（服务器 + 本地 Mac） ===
# chmod +x ~/benlog.sh
# ./benlog.sh server deploy | start | stop | restart | status
# ./benlog.sh local start | stop | status

set -euo pipefail
IFS=$'\n\t'

### === 路径设置 ===
SERVER_PROJECT_DIR="/home/Benlogmain.tar/Benlogmain"
LOCAL_PROJECT_DIR="/Users/benserver/Desktop/Benlog"

APP_MODULE="Benlog.app:create_app()"

SERVER_PORT=5000
LOCAL_PORT=5000

SERVER_PID_FILE="$SERVER_PROJECT_DIR/gunicorn.pid"
LOCAL_PID_FILE="$LOCAL_PROJECT_DIR/gunicorn.pid"

SERVER_LOG_FILE="$SERVER_PROJECT_DIR/gunicorn.log"
LOCAL_LOG_FILE="$LOCAL_PROJECT_DIR/gunicorn.log"

### === 部署相关配置（服务器端专用） ===
REPO_OWNER="Benjaminisgood"
REPO_NAME="Benlog"
BRANCH="benlog_base"
REMOTE_SSH="git@github.com:${REPO_OWNER}/${REPO_NAME}.git"
REMOTE_HTTPS="https://github.com/${REPO_OWNER}/${REPO_NAME}.git"
ZIP_URL="https://github.com/${REPO_OWNER}/${REPO_NAME}/archive/refs/heads/${BRANCH}.zip"
GITHUB_TOKEN="${GITHUB_TOKEN:-}"  # 可选 GitHub token

DATA_PATHS=(
  "Benlog/static"
  "Blog/posts"
  "Edu/notes"
  "Index/dynamic_links"
  "Index/dynamic_pages"
  "instance/site.db"
  "migarations"
  "myenv"
  "Neibr/neibr"
  "instance/config.py"
  "Settings/visible_albums.json"
)

### === 工具函数 ===
msg() { echo -e "\033[1;32m$1\033[0m"; }
warn() { echo -e "\033[1;33m$1\033[0m"; }
err() { echo -e "\033[1;31m$1\033[0m"; }

### === 本地端管理 ===
local_start() {
  cd "$LOCAL_PROJECT_DIR"
  if [ -f "$LOCAL_PID_FILE" ] && kill -0 $(cat "$LOCAL_PID_FILE") 2>/dev/null; then
    warn "⚠️ 本地 Gunicorn 已经运行 (PID=$(cat $LOCAL_PID_FILE))"
  else
    msg "🚀 启动本地 Gunicorn 服务..."
    source myenv/bin/activate
    nohup gunicorn -w 3 --threads 6 -b 0.0.0.0:$LOCAL_PORT "$APP_MODULE" > "$LOCAL_LOG_FILE" 2>&1 &
    echo $! > "$LOCAL_PID_FILE"
    msg "✅ 本地服务已启动 (端口=$LOCAL_PORT, PID=$(cat $LOCAL_PID_FILE))"
  fi
}

local_stop() {
  if [ -f "$LOCAL_PID_FILE" ] && kill -0 $(cat "$LOCAL_PID_FILE") 2>/dev/null; then
    msg "🛑 停止本地服务..."
    kill -9 $(cat "$LOCAL_PID_FILE") || true
    rm -f "$LOCAL_PID_FILE"
    msg "✅ 本地服务已停止"
  else
    warn "⚠️ 本地服务未运行"
  fi
}

local_status() {
  if [ -f "$LOCAL_PID_FILE" ] && kill -0 $(cat "$LOCAL_PID_FILE") 2>/dev/null; then
    msg "✅ 本地 Gunicorn 正在运行 (PID=$(cat $LOCAL_PID_FILE)，端口=$LOCAL_PORT)"
  else
    warn "⚠️ 本地 Gunicorn 未运行"
  fi
}

### === 服务器端管理 ===
server_start() {
  cd "$SERVER_PROJECT_DIR"
  if [ -f "$SERVER_PID_FILE" ] && kill -0 $(cat "$SERVER_PID_FILE") 2>/dev/null; then
    warn "⚠️ 服务器 Gunicorn 已经运行 (PID=$(cat $SERVER_PID_FILE))"
  else
    msg "🚀 启动服务器 Gunicorn 服务..."
    source myenv/bin/activate
    nohup gunicorn -w 3 --threads 6 -b 0.0.0.0:$SERVER_PORT "$APP_MODULE" > "$SERVER_LOG_FILE" 2>&1 &
    echo $! > "$SERVER_PID_FILE"
    msg "✅ 服务器服务已启动 (端口=$SERVER_PORT, PID=$(cat $SERVER_PID_FILE))"
  fi
}

server_stop() {
  if [ -f "$SERVER_PID_FILE" ] && kill -0 $(cat "$SERVER_PID_FILE") 2>/dev/null; then
    msg "🛑 停止服务器服务..."
    kill -9 $(cat "$SERVER_PID_FILE") || true
    rm -f "$SERVER_PID_FILE"
    msg "✅ 服务器服务已停止"
  else
    warn "⚠️ 服务器服务未运行"
  fi
}

server_status() {
  if [ -f "$SERVER_PID_FILE" ] && kill -0 $(cat "$SERVER_PID_FILE") 2>/dev/null; then
    msg "✅ 服务器 Gunicorn 正在运行 (PID=$(cat $SERVER_PID_FILE)，端口=$SERVER_PORT)"
  else
    warn "⚠️ 服务器 Gunicorn 未运行"
  fi
}

server_deploy() {
  cd "$SERVER_PROJECT_DIR"
  msg "📦 执行服务器端部署流程..."
  BACKUP_DIR="$(mktemp -d)"
  TEMP_CLONE="$(mktemp -d)"
  CLONE_SUCCESS=false

  echo "🔄 正在部署分支: $BRANCH"

  # 1️⃣ 备份
  for path in "${DATA_PATHS[@]}"; do
    if [ -e "$path" ]; then
      echo "→ 备份: $path"
      mkdir -p "$BACKUP_DIR/$(dirname "$path")"
      cp -a "$path" "$BACKUP_DIR/$path"
    fi
  done

  # 2️⃣ 拉取代码
  echo "🚀 尝试 SSH 拉取..."
  if ssh -T git@github.com 2>&1 | grep -q "successfully authenticated"; then
    git clone --depth=1 --branch "$BRANCH" "$REMOTE_SSH" "$TEMP_CLONE" && CLONE_SUCCESS=true
  fi
  if ! $CLONE_SUCCESS && [[ -n "$GITHUB_TOKEN" ]]; then
    echo "🚀 尝试 Token 拉取..."
    TOKEN_URL="https://${GITHUB_TOKEN}:x-oauth-basic@github.com/${REPO_OWNER}/${REPO_NAME}.git"
    git clone --depth=1 --branch "$BRANCH" "$TOKEN_URL" "$TEMP_CLONE" && CLONE_SUCCESS=true
  fi
  if ! $CLONE_SUCCESS; then
    echo "🚀 尝试 HTTPS 拉取..."
    git clone --depth=1 --branch "$BRANCH" "$REMOTE_HTTPS" "$TEMP_CLONE" && CLONE_SUCCESS=true
  fi
  if ! $CLONE_SUCCESS; then
    echo "🚀 尝试 Zip 下载方式..."
    ZIP_PATH="$(mktemp)"
    curl -L "$ZIP_URL" -o "$ZIP_PATH"
    unzip "$ZIP_PATH" -d "$TEMP_CLONE"
    TEMP_CLONE="${TEMP_CLONE}/${REPO_NAME}-${BRANCH}"
    [ -d "$TEMP_CLONE" ] && CLONE_SUCCESS=true
  fi
  if ! $CLONE_SUCCESS; then
    err "❌ 所有拉取方式失败，请检查网络/GitHub 设置"
    exit 1
  fi

  # 3️⃣ 清除旧代码（保留 myenv）
  echo "🧹 清空旧代码..."
  find . -mindepth 1 -maxdepth 1 ! -name "myenv" ! -name ".git" -exec rm -rf {} +

  # 4️⃣ 拷贝新代码
  echo "📥 拷贝新代码..."
  cp -a "$TEMP_CLONE/." .

  # 5️⃣ 安装依赖
  echo "🐍 安装依赖..."
  source myenv/bin/activate
  pip install --upgrade pip
  if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
  fi

  # 6️⃣ 恢复数据
  echo "🔁 恢复备份..."
  for path in "${DATA_PATHS[@]}"; do
    if [ -e "$BACKUP_DIR/$path" ]; then
      echo "→ 恢复: $path"
      rm -rf "$path"
      mkdir -p "$(dirname "$path")"
      mv "$BACKUP_DIR/$path" "$path"
    fi
  done

  # 7️⃣ 重启服务
  server_stop
  server_start

  # 8️⃣ 清理
  rm -rf "$BACKUP_DIR" "$TEMP_CLONE"
  msg "✅ 部署完成！"
}

### === 命令分发 ===
case "${1:-}" in
  local)
    case "${2:-}" in
      start) local_start ;;
      stop) local_stop ;;
      status) local_status ;;
      *) err "用法: $0 local {start|stop|status}" ;;
    esac
    ;;
  server)
    case "${2:-}" in
      start) server_start ;;
      stop) server_stop ;;
      restart) server_stop && server_start ;;
      status) server_status ;;
      deploy) server_deploy ;;
      *) err "用法: $0 server {start|stop|restart|status|deploy}" ;;
    esac
    ;;
  *)
    err "用法: $0 {local|server} [命令]"
    ;;
esac