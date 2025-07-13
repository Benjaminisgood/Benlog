#!/usr/bin/env bash
# === 🧠 一键部署脚本 deploy.sh（含重启服务） ===

set -euo pipefail
IFS=$'\n\t'

# ➤ 项目路径
PROJECT_DIR="/home/Benlogmain.tar/Benlogmain"
cd "$PROJECT_DIR"

# ➤ Git 仓库信息
REPO_OWNER="Benjaminisgood"
REPO_NAME="Benlog"
BRANCH="benlog_base"
REMOTE_SSH="git@github.com:${REPO_OWNER}/${REPO_NAME}.git"
REMOTE_HTTPS="https://github.com/${REPO_OWNER}/${REPO_NAME}.git"
ZIP_URL="https://github.com/${REPO_OWNER}/${REPO_NAME}/archive/refs/heads/${BRANCH}.zip"
GITHUB_TOKEN="${GITHUB_TOKEN:-}"  # 可选 GitHub token

# ➤ 用户数据需保留路径（相对于项目根目录）
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

BACKUP_DIR="$(mktemp -d)"
TEMP_CLONE="$(mktemp -d)"
CLONE_SUCCESS=false

echo "🔄 正在部署分支: $BRANCH"

# 🔸1️⃣ 数据备份
for path in "${DATA_PATHS[@]}"; do
  if [ -e "$path" ]; then
    echo "→ 备份: $path"
    mkdir -p "$BACKUP_DIR/$(dirname "$path")"
    cp -a "$path" "$BACKUP_DIR/$path"
  fi
done

# 🔸2️⃣ 拉取代码
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
  echo "❌ 所有拉取方式失败，请检查网络/GitHub 设置"
  exit 1
fi

# 🔸3️⃣ 清除旧代码（保留虚拟环境、数据库、配置等）
echo "🧹 清空旧代码..."
find . -mindepth 1 -maxdepth 1 ! -name "myenv" ! -name ".git" -exec rm -rf {} +

# 🔸4️⃣ 拷贝新代码
echo "📥 拷贝新代码..."
cp -a "$TEMP_CLONE/." .

# 🔸5️⃣ 激活虚拟环境 + 安装依赖
echo "🐍 激活虚拟环境 & 安装依赖..."
source myenv/bin/activate
pip install --upgrade pip
if [ -f "requirements.txt" ]; then
  pip install -r requirements.txt
fi

# 🔸6️⃣ 恢复数据
echo "🔁 恢复备份数据..."
for path in "${DATA_PATHS[@]}"; do
  if [ -e "$BACKUP_DIR/$path" ]; then
    echo "→ 恢复: $path"
    rm -rf "$path"
    mkdir -p "$(dirname "$path")"
    mv "$BACKUP_DIR/$path" "$path"
  fi
done

# 🔸7️⃣ 启动服务
echo "🚀 重启 Gunicorn 服务..."
pkill -f gunicorn || true
gunicorn -w 3 --threads 6 -b 0.0.0.0:80 "Benlog.app:create_app()"

# 🔚 清理
rm -rf "$BACKUP_DIR" "$TEMP_CLONE"
echo "✅ 部署完成！服务已自动重启。"