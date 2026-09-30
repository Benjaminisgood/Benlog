# Benlog

一个基于 Flask 的个人网站：博客、学习笔记、轻动态、动态页面和图库。目标仍然是「精简本真」——不换框架，内容放在本机 `instance/` 里，换机器时把这个目录拷走即可。

需要 Python 3.11 或 3.12。

## 本地运行

在仓库根目录：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
```

第一次使用，三选一创建管理员。不要把密码写进代码或提交到仓库。

网页（数据库里还没有用户时打开）：

```text
http://127.0.0.1:5000/setting/setup
```

或者在 `.env` 里填写 `ADMIN_EMAIL`、`ADMIN_USERNAME`、`ADMIN_PASSWORD`（至少 8 位），启动时如果还没有用户，会自动创建。

或者用命令（三个环境变量都有时不再询问）：

```bash
flask --app Benlog.app create-admin
```

启动：

```bash
flask --app Benlog.app run --host 127.0.0.1 --port 5000
```

浏览器打开 http://127.0.0.1:5000 。调试器默认关闭。只有在 `.env` 里设置 `FLASK_DEBUG=1` 才会打开。

检查登录、写文章和首页：

```bash
python scripts/smoke_test.py
```

## 配置

所有配置来自环境变量或根目录的 `.env`。样例是 `.env.example`。`.env` 已被 git 忽略。

| 变量 | 作用 |
| --- | --- |
| `SECRET_KEY` | 会话签名。留空则写入 `instance/.secret_key` |
| `DATABASE_URL` | 留空则使用 `instance/site.db` |
| `ALLOW_REGISTRATION` | 默认 `0`，不开放公开注册 |
| `STORAGE_BACKEND` | 默认 `local`，图库在 `instance/Gallery/media` |
| `OPENAI_API_KEY` | 可选。不填时 `/llm` 不会访问外网 |
| `BEHIND_PROXY` | 放在反向代理后才设为 `1` |

图库如果要接阿里云 OSS，把 `STORAGE_BACKEND` 设为 `oss`，填好 OSS 变量，并额外安装：

```bash
pip install -r requirements-oss.txt
```

没有 OSS 时不要装它，站点照常使用本地文件。

## 写文章

管理员登录后打开 `/blog`，点新建。编辑页有标题、摘要、标签、草稿开关，以及 Markdown 预览。状态选「草稿」时，访客看不到这篇文章。笔记 `/edu` 是同一套写法。

## 生产

```bash
gunicorn -w 1 -b 127.0.0.1:5000 "Benlog.app:create_app()"
```

前面可以加 Nginx。如果 Nginx 负责 HTTPS，把 `BEHIND_PROXY=1`。上传很大的文件时，同步调大 `client_max_body_size` 和 `MAX_CONTENT_LENGTH_MB`。

`benlog.sh` 是本机启停脚本，项目目录按脚本所在位置计算，不再写死某台 Mac 的路径。

## 内容放哪

```text
instance/
├── site.db
├── Blog/posts/
├── Edu/notes/
├── Neibr/neibr/
├── Gallery/media/
└── Index/
```

备份和迁移，拷贝 `instance/` 即可。不要把 `instance/` 或 `.env` 提交到仓库。
