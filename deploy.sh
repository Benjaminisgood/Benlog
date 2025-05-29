#!/usr/bin/env bash
# deploy.sh — 极简一键更新脚本（不含服务重启）
# 只负责拉取/更新代码、更新依赖，并保留指定数据目录

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
  "Gallery/galleries"
  "Index/dynamic_links"
  "Index/dynamic_pages"
  "instance/site.db"
  "migarations"
  "myenv"
  "Neibr/neibr"
)

# 临时备份目录
BACKUP_DIR="$(mktemp -d)"

echo "🔄 开始部署..."

# 1️⃣ 确保 Git 仓库已初始化或添加远程
if [ ! -d "$PROJECT_DIR/.git" ]; then
  echo "→ 仓库未检测到 .git，初始化并设置远程..."
  cd "$PROJECT_DIR"
  git init
  git remote add origin "$REMOTE_URL"
  git fetch origin
else
  cd "$PROJECT_DIR"
  # 确保 remote url 使用 HTTPS
  git remote set-url origin "$REMOTE_URL" || true
fi

# 2️⃣ 备份用户数据
for path in "${DATA_PATHS[@]}"; do
  if [ -e "$PROJECT_DIR/$path" ]; then
    echo "  → 备份 $path"
    mkdir -p "$BACKUP_DIR/$(dirname "$path")"
    cp -a "$PROJECT_DIR/$path" "$BACKUP_DIR/$path"
  fi
done

# 3️⃣ 拉取并重置到指定分支
echo "→ 拉取最新代码 (分支: $BRANCH) ..."
# 获取最新分支
git fetch origin "$BRANCH":$BRANCH || true
git fetch --all
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
    rm -rf "$PROJECT_DIR/$path"
    mkdir -p "$PROJECT_DIR/$(dirname "$path")"
    mv "$BACKUP_DIR/$path" "$PROJECT_DIR/$path"
  fi
done

# 6️⃣ 清理临时备份
echo "→ 清理临时文件..."
rm -rf "$BACKUP_DIR"

echo "✅ 代码已更新完成，数据已保留。请手动重启你的服务或进程。"