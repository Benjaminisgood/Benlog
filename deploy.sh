#!/usr/bin/env bash
# deploy.sh — 极简一键更新脚本（不含服务重启）
# 使用 HTTPS 克隆/更新代码、更新依赖，并保留指定数据目录
# 解决 HTTP/2 报错，通过 HTTP/1.1 及浅克隆降低传输量

set -e
IFS=$'\n\t'

# ➤ 请修改为你的项目根目录路径
PROJECT_DIR="/Benlogmain"
# ➤ 使用 HTTPS 克隆（带或不带 Token）
REMOTE_URL="https://github.com/Benjaminisgood/Benlog.git"
# ➤ 要部署的分支
BRANCH="benlog_base"

# ➤ 更新前需保留的目录/文件列表（相对于 PROJECT_DIR）
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
)

# 临时备份目录
BACKUP_DIR="$(mktemp -d)"

echo "🔄 开始部署..."

# 1️⃣ 进入项目目录并配置 Git
cd "$PROJECT_DIR"
if [ ! -d ".git" ]; then
  echo "→ 初始化 Git 仓库..."
  git init
  git remote add origin "$REMOTE_URL"
fi
# 强制使用 HTTP/1.1 避免 HTTP/2 报错
git config http.version HTTP/1.1
# 可根据需要增加 buffer 大小
git config http.postBuffer 524288000
# 确保 remote URL
git remote set-url origin "$REMOTE_URL" || true

# 2️⃣ 备份用户数据
for path in "${DATA_PATHS[@]}"; do
  if [ -e "$path" ]; then
    echo "  → 备份 $path"
    mkdir -p "$BACKUP_DIR/$(dirname "$path")"
    cp -a "$path" "$BACKUP_DIR/$path"
  fi
done

# 3️⃣ 浅克隆/拉取并切换分支
echo "→ 拉取最新代码 (分支: $BRANCH) ..."
# 尝试浅拉取指定分支
git fetch --depth=1 origin "$BRANCH" || true
# 重置到远程分支最新状态
git reset --hard "origin/$BRANCH"

# 4️⃣ 更新 Python 依赖
echo "→ 更新依赖..."
if [ -f "requirements.txt" ]; then
  pip install --upgrade pip
  pip install -r requirements.txt
fi

# 5️⃣ 恢复用户数据
echo "→ 恢复备份的数据..."
for path in "${DATA_PATHS[@]}"; do
  if [ -e "$BACKUP_DIR/$path" ]; then
    echo "  → 恢复 $path"
    rm -rf "$path"
    mkdir -p "$(dirname "$path")"
    mv "$BACKUP_DIR/$path" "$path"
  fi
done

# 6️⃣ 清理临时备份
echo "→ 清理临时文件..."
rm -rf "$BACKUP_DIR"

echo "✅ 代码已更新完成，数据已保留。请手动重启你的服务或进程。"