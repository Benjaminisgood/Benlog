#!/usr/bin/env bash
# === 🧠 Benlog 本地一体化管理脚本（Mac 专用） ===
# chmod +x /Users/benserver/.local/bin/benlog
# 用法: benlog start | stop | restart | status | pub | ip

set -euo pipefail
IFS=$'\n\t'

### === 路径设置 ===
LOCAL_PROJECT_DIR="/Users/benserver/Desktop/Benlog"
APP_MODULE="Benlog.app:create_app()"
LOCAL_PORT=5002

LOCAL_PID_FILE="$LOCAL_PROJECT_DIR/gunicorn.pid"
LOCAL_LOG_FILE="$LOCAL_PROJECT_DIR/gunicorn.log"

# Markdown 文件目标路径
BLOG_POSTS_DIR="/Users/benserver/Desktop/Benlog/Blog/posts"
EDU_NOTES_DIR="/Users/benserver/Desktop/Benlog/Edu/notes"

### === 工具函数 ===
msg() { echo -e "\033[1;32m$1\033[0m"; }
warn() { echo -e "\033[1;33m$1\033[0m"; }
err() { echo -e "\033[1;31m$1\033[0m"; }

check_port_in_log() {
  local logfile=$1
  local expected=$2

  if grep -q "Address already in use" "$logfile"; then
    err "❌ 启动失败：端口 $expected 已被占用"
    lsof -iTCP:$expected -sTCP:LISTEN -n -P || true
    return 1
  fi

  if grep -q "Listening at:" "$logfile"; then
    PORT_FOUND=$(grep "Listening at:" "$logfile" | tail -n1 | sed -E 's/.*:([0-9]+).*/\1/')
    if [ "$PORT_FOUND" != "$expected" ]; then
      err "❌ 服务端口异常：预期=$expected, 实际=$PORT_FOUND"
      tail -n 10 "$logfile"
      return 1
    fi
    return 0
  fi

  err "❌ 启动失败：日志中未找到端口信息"
  tail -n 20 "$logfile" || true
  return 1
}

### === 环境检查 ===
local_check_env() {
  cd "$LOCAL_PROJECT_DIR"

  if [ ! -d "myenv" ]; then
    warn "⚠️ 未检测到虚拟环境 (myenv)"
    read -p "是否创建新的虚拟环境？(y/n): " yn
    if [[ "$yn" == "y" ]]; then
      python3 -m venv myenv
      msg "✅ 已创建虚拟环境 myenv"
    else
      err "❌ 无虚拟环境，无法继续"
      exit 1
    fi
  fi

  source myenv/bin/activate
  msg "🐍 已激活虚拟环境 myenv"

  if [ -f "requirements.txt" ]; then
    msg "🔍 检查依赖..."
    missing=false
    while read -r pkg; do
      [[ -z "$pkg" || "$pkg" =~ ^# ]] && continue
      if ! pip show "$pkg" >/dev/null 2>&1; then
        warn "⚠️ 缺少依赖: $pkg"
        missing=true
      fi
    done < requirements.txt

    if $missing; then
      read -p "是否安装缺失依赖？(y/n): " yn
      if [[ "$yn" == "y" ]]; then
        pip install -r requirements.txt
        msg "✅ 依赖安装完成"
      else
        err "❌ 缺少依赖，启动可能失败"
      fi
    fi
  else
    warn "⚠️ 未找到 requirements.txt"
  fi
}

check_db_migrations() {
  msg "🗄 检查数据库迁移状态..."
  export FLASK_APP="$APP_MODULE"

  if [ ! -f "instance/site.db" ]; then
    warn "⚠️ 数据库不存在，执行初始化..."
    flask db init || true
    flask db migrate -m "init tables" || true
    flask db upgrade || true
    msg "✅ 数据库已初始化"
  else
    if [ ! -d "migrations" ]; then
      warn "⚠️ 未检测到 migrations 目录，初始化中..."
      flask db init || true
      flask db migrate -m "init tables" || true
    fi
    flask db upgrade || true
    msg "✅ 数据库已升级"
  fi
}

### === 服务控制 ===
start() {
  cd "$LOCAL_PROJECT_DIR"
  local_check_env
  check_db_migrations

  if lsof -iTCP:$LOCAL_PORT -sTCP:LISTEN -t >/dev/null; then
    err "❌ 端口 $LOCAL_PORT 已被占用"
    echo "👉 运行 'benlog stop' 后再试"
    exit 1
  fi

  msg "🚀 启动 Benlog (可外网访问)..."
  source myenv/bin/activate

  # ✅ 确保使用 0.0.0.0 并明确模块路径
  nohup gunicorn -w 4 -b 0.0.0.0:$LOCAL_PORT "Benlog.app:create_app()" > "$LOCAL_LOG_FILE" 2>&1 &
  echo $! > "$LOCAL_PID_FILE"
  sleep 2

  if ps -p $(cat "$LOCAL_PID_FILE") -o comm= | grep -q gunicorn; then
    msg "✅ 服务已启动 (PID=$(cat $LOCAL_PID_FILE), 端口=$LOCAL_PORT)"

    # 输出局域网 IP
    local ip=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null)
    if [ -n "$ip" ]; then
      echo "🌐 局域网访问: http://$ip:$LOCAL_PORT"
    fi
    echo "💻 本机访问: http://localhost:$LOCAL_PORT"
  else
    err "❌ 启动失败，请检查日志：$LOCAL_LOG_FILE"
    tail -n 20 "$LOCAL_LOG_FILE" || true
    rm -f "$LOCAL_PID_FILE"
    exit 1
  fi
}

stop() {
  if [ -f "$LOCAL_PID_FILE" ] && kill -0 $(cat "$LOCAL_PID_FILE") 2>/dev/null; then
    msg "🛑 停止服务..."
    kill -9 $(cat "$LOCAL_PID_FILE") || true
    rm -f "$LOCAL_PID_FILE"
    msg "✅ 已停止"
  else
    if lsof -iTCP:$LOCAL_PORT -sTCP:LISTEN -t >/dev/null; then
      warn "⚠️ 未找到 PID 文件，但端口被占用"
      kill -9 $(lsof -iTCP:$LOCAL_PORT -sTCP:LISTEN -t) || true
      rm -f "$LOCAL_PID_FILE"
      msg "✅ 已清理端口 $LOCAL_PORT 的进程"
    else
      warn "⚠️ 服务未运行"
    fi
  fi
}

status() {
  if [ -f "$LOCAL_PID_FILE" ]; then
    if ps -p $(cat "$LOCAL_PID_FILE") -o comm= 2>/dev/null | grep -q gunicorn; then
      msg "✅ Gunicorn 正在运行 (PID=$(cat $LOCAL_PID_FILE))"
      check_port_in_log "$LOCAL_LOG_FILE" "$LOCAL_PORT" || true
      return
    else
      warn "⚠️ PID 文件存在但进程已消失"
      rm -f "$LOCAL_PID_FILE"
    fi
  fi

  if lsof -iTCP:$LOCAL_PORT -sTCP:LISTEN -n -P | grep -q gunicorn; then
    msg "✅ Gunicorn 正在监听端口 $LOCAL_PORT"
  else
    warn "⚠️ 服务未运行"
    [ -f "$LOCAL_LOG_FILE" ] && {
      echo "🔎 最近日志:"
      tail -n 10 "$LOCAL_LOG_FILE"
    }
  fi
}

restart() {
  msg "🔄 正在重启 Benlog..."
  stop
  sleep 1
  start
}

### === Markdown 文件移动功能 ===
pub() {
  echo "📝 请输入一个或多个 Markdown 文件路径（可拖入多个文件，用空格分隔）:"
  read -e -p "→ " input_line
  eval "filepaths_raw=($input_line)"  # ✅ 修复多文件与转义路径处理

  if [ ${#filepaths_raw[@]} -eq 0 ]; then
    err "❌ 未输入任何文件"
    exit 1
  fi

  for filepath in "${filepaths_raw[@]}"; do
    # 处理 ~ 展开与清理多余空格
    filepath="${filepath/#\~/$HOME}"
    filepath=$(echo "$filepath" | sed 's/^ *//;s/ *$//')

    if [ ! -f "$filepath" ]; then
      err "❌ 文件不存在: $filepath"
      continue
    fi

    if [[ "$filepath" != *.md ]]; then
      warn "⚠️ 跳过非 Markdown 文件: $(basename "$filepath")"
      continue
    fi

    echo ""
    echo "📄 检测到文件：$(basename "$filepath")"
    echo "请选择移动目标："
    echo "  1️⃣ 博客 (Blog/posts)"
    echo "  2️⃣ 笔记 (Edu/notes)"
    echo "  3️⃣ 跳过此文件"
    read -p "输入 1 / 2 / 3: " choice

    case "$choice" in
      1) target="$BLOG_POSTS_DIR" ;;
      2) target="$EDU_NOTES_DIR" ;;
      3) warn "⏭ 已跳过 $(basename "$filepath")"; continue ;;
      *) err "❌ 无效输入，已跳过 $(basename "$filepath")"; continue ;;
    esac

    mkdir -p "$target"
    mv "$filepath" "$target"
    msg "✅ 已移动 $(basename "$filepath") → $target"
  done

  echo ""
  msg "🎉 所有文件已处理完毕！"
}

ip() {
  echo "📡 当前局域网 IP:"
  for iface in en0 en1; do
    local ip=$(ipconfig getifaddr $iface 2>/dev/null || true)
    [ -n "$ip" ] && echo "   - $iface: http://$ip:$LOCAL_PORT"
  done
}

### === 命令分发 ===
case "${1:-}" in
  start) start ;;
  stop) stop ;;
  restart) restart ;;
  status) status ;;
  pub) pub ;;
  ip) ip ;;
  *)
    echo "用法: $0 {start|stop|restart|status|pub|ip}"
    ;;
esac