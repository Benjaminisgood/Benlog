# Neibr/views.py
from flask import render_template, request, redirect, url_for, flash  # type: ignore
from . import neibr_bp, db  # 从 Neibr/__init__.py 导入蓝图和本地数据库实例
from flask_login import login_required, current_user, login_user  # type: ignore # Flask-Login 用于用户会话管理
from .models import User, Post  # 从本地 models.py 导入 User 和 Post 模型
from werkzeug.security import generate_password_hash, check_password_hash  # type: ignore # 用于密码加密和验证
import os
import io
from PIL import Image
from PIL import UnidentifiedImageError
from PIL import ImageOps, ImageDraw
from werkzeug.utils import secure_filename  # type: ignore
import yaml
from datetime import datetime
from flask import send_from_directory, abort  # type: ignore
from flask import session
from flask import jsonify, request
from math import ceil
from markupsafe import Markup, escape  # 新增此行
import re
from unidecode import unidecode
from urllib.parse import urlparse
from sqlalchemy import and_, or_
import requests
from typing import Optional


def convert_rich_text(text):
    """
    多功能富文本转换器（先处理，后包装为 Markup）：
    - URL => 链接
    - 图片链接 => <img>
    - 视频链接 => <video>
    - @user => 用户链接
    - #tag => 标签高亮
    - 邮箱 => mailto:
    """

    # 👉 不转义，直接处理富文本（text 已经是纯文本了）
    # 若数据库存储有恶意 HTML，请预处理
    text = re.sub(r'(https?://[^\s]+\.(?:png|jpg|jpeg|gif|webp))',
                  r'<img src="\1" class="inline-img" loading="lazy">', text)

    text = re.sub(r'(https?://[^\s]+\.(?:mp4|webm|mov))',
                  r'<video src="\1" class="inline-video" controls></video>', text)

    text = re.sub(r'(https?://[^\s]+)',
                  lambda m: f'<a class="link-card" href="{m.group(0)}" target="_blank" rel="noopener">{m.group(0)}</a>', text)

    text = re.sub(r'\b([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b',
                  r'<a href="mailto:\1">\1</a>', text)

    text = re.sub(r'@(\w+)',
                  r'<a href="/user/\1" class="mention">@\1</a>', text)

    text = re.sub(r'#(\w+)',
                  r'<span class="hashtag">#\1</span>', text)

    return Markup(text)  # 👈 标记为“安全 HTML”

# 项目根目录下的 static/neibr 路径
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
UPLOAD_BASE_PATH = os.path.join(BASE_DIR, 'Neibr', 'neibr')
IMAGE_QUALITY = 22
REMOTE_LINKS_FILENAME = 'media_links.yaml'

COMPRESSIBLE_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
IMAGE_EXTENSIONS = COMPRESSIBLE_IMAGE_EXTENSIONS | {'nef'}
VIDEO_EXTENSIONS = {'mp4', 'webm', 'mov'}
AUDIO_EXTENSIONS = {'mp3', 'wav', 'flac'}
DOCUMENT_EXTENSIONS = {'pdf', 'docx', 'xlsx', 'pptx'}
ALLOWED_LINK_SCHEMES = {'http', 'https'}
FRONT_MATTER_DELIM = '---'


def allowed_file(filename):
    allowed_extensions = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS | AUDIO_EXTENSIONS | DOCUMENT_EXTENSIONS | {'MOV'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions


def compress_and_save_image(file_storage, save_path):
    try:
        img = Image.open(file_storage.stream)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        img_io = io.BytesIO()
        img.save(img_io, format='JPEG', quality=IMAGE_QUALITY, optimize=True)
        img_io.seek(0)

        with open(save_path, 'wb') as out_f:
            out_f.write(img_io.read())
    except UnidentifiedImageError:
        raise  # 交由上层处理（或你可以 flash 一句）
        


def sanitize_filename(file):
    original_name = file.filename
    filename = secure_filename(unidecode(original_name))

    if not filename or filename.startswith('.'):
        ext = original_name.rsplit('.', 1)[-1].lower() if '.' in original_name else 'bin'
        filename = f"file_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.{ext}"
    else:
        ext = filename.rsplit('.', 1)[-1].lower()
        name = filename.rsplit('.', 1)[0]
        filename = f"{name}_{datetime.utcnow().strftime('%H%M%S')}.{ext}"

    return filename


def detect_media_type(source: str) -> str:
    """根据扩展名推断媒体类型。"""
    path = urlparse(source).path if '://' in source else source
    if '.' not in path:
        return 'file'
    ext = path.rsplit('.', 1)[-1].lower()
    if ext in IMAGE_EXTENSIONS:
        return 'image'
    if ext in VIDEO_EXTENSIONS:
        return 'video'
    if ext in AUDIO_EXTENSIONS:
        return 'audio'
    if ext in DOCUMENT_EXTENSIONS:
        return 'document'
    return 'file'


def sanitize_remote_links(raw_links: str):
    """
    将换行分隔的远程媒体链接转换成统一字典，并过滤非法链接。
    """
    links = []
    if not raw_links:
        return links

    for line in raw_links.splitlines():
        url = line.strip()
        if not url:
            continue
        parsed = urlparse(url)
        if parsed.scheme not in ALLOWED_LINK_SCHEMES:
            flash(f'忽略不受支持的链接：{url}', 'warning')
            continue
        links.append({
            'url': url,
            'type': detect_media_type(url)
        })
    return links


def load_remote_links(folder_path: str):
    """
    从磁盘读取远程媒体链接列表。
    """
    links_file = os.path.join(folder_path, REMOTE_LINKS_FILENAME)
    if not os.path.exists(links_file):
        return []
    with open(links_file, 'r') as f:
        data = yaml.safe_load(f) or []

    normalized = []
    for item in data:
        if isinstance(item, dict) and 'url' in item:
            normalized.append({
                'url': item['url'],
                'type': item.get('type') or detect_media_type(item['url'])
            })
        elif isinstance(item, str):
            normalized.append({
                'url': item,
                'type': detect_media_type(item)
            })
    return normalized


def save_remote_links(folder_path: str, links: list):
    """
    保存远程媒体链接；如果无链接则删除配置文件。
    """
    links_file = os.path.join(folder_path, REMOTE_LINKS_FILENAME)
    if links:
        with open(links_file, 'w') as f:
            yaml.safe_dump(links, f, allow_unicode=True)
    else:
        if os.path.exists(links_file):
            os.remove(links_file)


def base_visible_posts_query():
    """返回当前用户可见的帖子基础查询。"""
    visibility_filter = or_(Post.is_hidden == False, Post.user_id == current_user.id)
    return Post.query.filter(visibility_filter)


def random_visible_post(exclude_ids=None):
    """返回一个随机可见帖子，排除给定 ID 列表。"""
    query = base_visible_posts_query()
    if exclude_ids:
        query = query.filter(Post.id.notin_(exclude_ids))
    return query.order_by(db.func.random()).first()


def get_post_folder(post: Post) -> str:
    """计算帖子对应的存储目录。"""
    return os.path.join(UPLOAD_BASE_PATH, str(post.user_id), str(post.id))


def resolve_visible_post(post_id: int) -> Optional[Post]:
    post = Post.query.get(post_id)
    if not post:
        return None
    if post.is_hidden and post.user_id != current_user.id:
        return None
    return post


def _clean_summary_text(text: str) -> str:
    """轻量清洗 Markdown / HTML，压缩空白。"""
    if not text:
        return ''
    # 链接语法 -> 文本
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1', text)
    # 行内代码/粗体/标题标记
    text = re.sub(r'[`*_#>]+', ' ', text)
    # HTML 标签
    text = re.sub(r'<[^>]+>', ' ', text)
    # 图片语法
    text = re.sub(r'!\s*\[[^\]]*\]\s*\([^)]*\)', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def extract_post_summary(post: Post, limit: int = 140) -> str:
    """读取帖子文本生成摘要，用于列表页卡片展示。"""
    folder = get_post_folder(post)
    text_path = os.path.join(folder, 'post.txt')
    if not os.path.exists(text_path):
        return ''
    with open(text_path, 'r') as f:
        raw = f.read()
    meta, body = parse_post_file(raw)
    body = body.strip()

    if body:
        snippet_source = body
    else:
        snippet_source = meta.get('Summary') or meta.get('Excerpt') or ''
        if not snippet_source:
            author = meta.get('Author') or '邻居'
            created = post.creation_time.strftime('%Y-%m-%d %H:%M')
            snippet_source = f"{author} · 发布于 {created}"

    snippet = _clean_summary_text(snippet_source)
    if not snippet:
        return ''
    if len(snippet) <= limit:
        return snippet
    return snippet[:limit].rstrip() + '…'


def save_cover_from_image(image: Image.Image, cover_path: str):
    """将任意图像裁剪成 16:9 封面并写入磁盘。"""
    target_size = (1280, 720)
    image = image.convert('RGB')
    cover = ImageOps.fit(image, target_size, method=Image.LANCZOS)
    os.makedirs(os.path.dirname(cover_path), exist_ok=True)
    cover.save(cover_path, format='JPEG', quality=86, optimize=True)


def create_placeholder_cover(cover_path: str):
    """生成一个渐变背景的占位封面，便于分享。"""
    width, height = 1280, 720
    top_color = (255, 77, 103)
    bottom_color = (91, 134, 229)
    img = Image.new('RGB', (width, height))
    draw = ImageDraw.Draw(img)
    for y in range(height):
        ratio = y / (height - 1)
        r = int(top_color[0] + (bottom_color[0] - top_color[0]) * ratio)
        g = int(top_color[1] + (bottom_color[1] - top_color[1]) * ratio)
        b = int(top_color[2] + (bottom_color[2] - top_color[2]) * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    img.save(cover_path, format='JPEG', quality=85, optimize=True)


def ensure_post_cover(post: Post, refresh: bool = False):
    """
    生成并缓存帖子封面图片，避免重复计算：
    1. 优先使用本地上传图片；
    2. 其次尝试下载外链图片；
    3. 若均没有，则生成占位封面。
    """
    folder = get_post_folder(post)
    os.makedirs(folder, exist_ok=True)
    cover_filename = 'cover.jpg'
    cover_path = os.path.join(folder, cover_filename)

    if os.path.exists(cover_path) and not refresh:
        return url_for('neibr.media_file', user_id=post.user_id, post_id=post.id, filename=cover_filename)

    # 1) 查找本地图片
    local_candidate = None
    if os.path.isdir(folder):
        for fname in sorted(os.listdir(folder)):
            if fname in {'post.txt', 'comments.yaml', REMOTE_LINKS_FILENAME, cover_filename}:
                continue
            full_path = os.path.join(folder, fname)
            if not os.path.isfile(full_path):
                continue
            ext = fname.rsplit('.', 1)[-1].lower()
            if ext in {'jpg', 'jpeg', 'png', 'gif', 'webp'}:
                local_candidate = full_path
                break

    if local_candidate:
        try:
            with Image.open(local_candidate) as img:
                save_cover_from_image(img, cover_path)
            return url_for('neibr.media_file', user_id=post.user_id, post_id=post.id, filename=cover_filename)
        except Exception:
            pass

    # 2) 远程图片 (直接使用外链 URL)
    remote_links = load_remote_links(folder)
    for item in remote_links:
        if item.get('type') == 'image':
            return item['url']

    # 3) 占位封面
    create_placeholder_cover(cover_path)
    return url_for('neibr.media_file', user_id=post.user_id, post_id=post.id, filename=cover_filename)


def build_post_file_content(post: Post, body_text: str, author_name: str, updated_at: Optional[datetime] = None) -> str:
    """生成包含前置说明的帖子文本文件内容。"""
    timestamp = post.creation_time or datetime.utcnow()
    if post.creation_time is None:
        post.creation_time = timestamp
    updated_ts = updated_at or datetime.utcnow()
    meta_lines = [
        FRONT_MATTER_DELIM,
        f"Title: {post.title}",
        f"Author: {author_name}",
        f"Tags: {post.tags or ''}",
        f"Hidden: {'Yes' if post.is_hidden else 'No'}",
        f"Created: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Updated: {updated_ts.strftime('%Y-%m-%d %H:%M:%S')}",
        FRONT_MATTER_DELIM,
        ""
    ]
    body = body_text.strip('\n')
    if body:
        meta_lines.append(body)
    return '\n'.join(meta_lines) + '\n'


def parse_post_file(raw_text: str):
    """
    解析带有前置说明的帖子文本。
    返回 (meta_dict, body_text)。
    """
    if raw_text.startswith(FRONT_MATTER_DELIM):
        closing_index = raw_text.find(f"\n{FRONT_MATTER_DELIM}", len(FRONT_MATTER_DELIM) + 1)
        if closing_index != -1:
            meta_segment = raw_text[len(FRONT_MATTER_DELIM) + 1:closing_index]
            body = raw_text[closing_index + len(FRONT_MATTER_DELIM) + 1:].lstrip('\n')
            meta = {}
            for line in meta_segment.splitlines():
                if ':' not in line:
                    continue
                key, value = line.split(':', 1)
                meta[key.strip()] = value.strip()
            return meta, body
    return {}, raw_text


def build_post_card(post: Post, src: str, author_name: str):
    """生成前端卡片展示所需的结构化数据。"""
    tags = [t.strip() for t in (post.tags or '').split(',') if t.strip()]
    return {
        'id': post.id,
        'title': post.title,
        'author': author_name,
        'created_at': post.creation_time.strftime('%Y-%m-%d %H:%M'),
        'tags': tags,
        'summary': extract_post_summary(post),
        'thumbnail': ensure_post_cover(post),
        'detail_url': url_for('neibr.post_detail', title=post.title, src=src, pid=post.id),
        'edit_url': url_for('neibr.edit_post', title=post.title) if post.user_id == current_user.id else None,
        'is_hidden': post.is_hidden
    }


@neibr_bp.route('/')
def index():
    """
    Neibr 模块的主页，展示最新的 10 个帖子和随机选择的 10 个帖子。
    返回值：渲染 neibr_index.html 模板，传入帖子数据。
    """
    if not current_user.is_authenticated:
        flash('请先登录以查看内容。', 'login')
        return redirect(url_for('setting.login'))

    latest_posts = Post.query.filter(
       (Post.is_hidden == False) | (Post.user_id == current_user.id)
    ). order_by(Post.creation_time.desc()).limit(10).all()

    random_posts = Post.query.filter(
       (Post.is_hidden == False) | (Post.user_id == current_user.id)
    ). order_by(db.func.random()).limit(10).all()

    my_posts = Post.query.filter_by(user_id=current_user.id).order_by(Post.creation_time.desc()).limit(10).all()

    all_posts = latest_posts + random_posts + my_posts
    session['neibr_seq_latest'] = [p.id for p in latest_posts]
    session['neibr_seq_random'] = [p.id for p in random_posts]
    session['neibr_seq_my'] = [p.id for p in my_posts]

    user_ids = {p.user_id for p in all_posts}
    if user_ids:
        users = User.query.filter(User.id.in_(user_ids)).all()
        user_map = {u.id: u.username for u in users}
    else:
        user_map = {}

    latest_cards = [build_post_card(p, 'latest', user_map.get(p.user_id, '神秘邻居')) for p in latest_posts]
    random_cards = [build_post_card(p, 'random', user_map.get(p.user_id, '神秘邻居')) for p in random_posts]
    my_cards = [build_post_card(p, 'my', user_map.get(p.user_id, current_user.username)) for p in my_posts]

    return render_template(
        'neibr_index.html',
        latest_cards=latest_cards,
        random_cards=random_cards,
        my_cards=my_cards,
        current_username=current_user.username
    )

@neibr_bp.route('/create_post', methods=['GET', 'POST'])
@login_required
def create_post():
    """
    允许登录用户创建新帖子，上传多媒体文件并保存到文件系统。
    方法：
        GET - 显示创建帖子页面。
        POST - 处理表单数据，保存帖子和文件到 static/neibr/user_id/post_id。
    返回值：
        GET - 渲染 create_post.html 模板。
        POST - 成功则重定向到帖子详情页。
    """
    if request.method == 'POST':
        title = request.form['title']
        tags = request.form['tags']
        post_text = request.form.get('post_text', '')
        files = request.files.getlist('files')
        remote_links_raw = request.form.get('media_links', '')

        is_hidden = request.form.get('is_hidden')

        # 创建帖子记录
        post = Post(title=title, tags=tags, user_id=current_user.id)
        post.is_hidden = True if is_hidden else False

        db.session.add(post)
        db.session.flush()  # 获取 post.id

        # 构建帖子文件夹路径：static/neibr/user_id/post_id
        folder_path = os.path.join(UPLOAD_BASE_PATH, str(current_user.id), str(post.id))
        os.makedirs(folder_path, exist_ok=True)

        for file in files:
            if file and file.filename:
                filename = sanitize_filename(file)

                # 判断后缀是否合法
                if not allowed_file(filename):
                    flash(f'文件类型不允许：{file.filename}', 'warning')
                    continue

                ext = filename.rsplit('.', 1)[1].lower()
                file_path = os.path.join(folder_path, filename)

                if ext in COMPRESSIBLE_IMAGE_EXTENSIONS:
                    compress_and_save_image(file, file_path)
                else:
                    file.save(file_path)

        remote_links = sanitize_remote_links(remote_links_raw)
        save_remote_links(folder_path, remote_links)
        ensure_post_cover(post, refresh=True)

        # 保存帖子文案到 post.txt（包含元数据）
        text_path = os.path.join(folder_path, 'post.txt')
        author_name = current_user.username
        file_content = build_post_file_content(post, post_text, author_name, updated_at=datetime.utcnow())
        with open(text_path, 'w') as f:
            f.write(file_content)

        db.session.commit()
        flash('帖子创建成功。', 'create_post')
        return redirect(url_for('neibr.post_detail', title=post.title, pid=post.id))
    
    return render_template('create_post.html', title='创建帖子')

@neibr_bp.route('/post/<string:title>', methods=['GET', 'POST'])
@login_required
def post_detail(title):
    """
    显示特定帖子的详情，包括文案、多媒体文件、导航链接和评论。
    参数：
        post_id - 帖子 ID。
    返回值：
        渲染 post_detail.html 模板，传入帖子数据。
    """
    src = request.args.get('src', 'latest')
    if src not in {'latest', 'random', 'my'}:
        src = 'latest'

    pid = request.args.get('pid', type=int)
    if pid:
        post = Post.query.get_or_404(pid)
        if post.title != title:
            return redirect(url_for('neibr.post_detail', title=post.title, src=src, pid=post.id))
    else:
        post = Post.query.filter_by(title=title).first_or_404()

    if post.is_hidden and post.user_id != current_user.id:
        abort(403)

    user_id = post.user_id
    author = User.query.get(user_id).username

    # 构建帖子文件夹路径：static/neibr/user_id/post_id
    folder_path = os.path.join(UPLOAD_BASE_PATH, str(user_id), str(post.id))

    # 读取帖子文案（允许文案缺失）
    text_path = os.path.join(folder_path, 'post.txt')
    if os.path.exists(text_path):
        with open(text_path, 'r') as f:
            post_text_raw = f.read()
    else:
        post_text_raw = ''
    _, post_body = parse_post_file(post_text_raw)
    post_text = convert_rich_text(post_body) if post_body else Markup('')

    # 获取媒体文件列表，排除配置文件
    excluded_files = {'post.txt', 'comments.yaml', REMOTE_LINKS_FILENAME, 'cover.jpg'}
    media_files = []
    if os.path.isdir(folder_path):
        media_files = [
            f for f in os.listdir(folder_path)
            if f not in excluded_files and os.path.isfile(os.path.join(folder_path, f))
        ]
        media_files.sort()
        remote_media = load_remote_links(folder_path)
    else:
        remote_media = []

    # 动态上一条/下一条：根据 feed 模式自动判定
    previous_post = None
    next_post = None

    if src in {'latest', 'my'}:
        query = base_visible_posts_query()
        if src == 'my':
            query = query.filter(Post.user_id == current_user.id)

        previous_post = query.filter(
            or_(
                Post.creation_time > post.creation_time,
                and_(Post.creation_time == post.creation_time, Post.id > post.id)
            )
        ).order_by(Post.creation_time.asc(), Post.id.asc()).first()

        next_post = query.filter(
            or_(
                Post.creation_time < post.creation_time,
                and_(Post.creation_time == post.creation_time, Post.id < post.id)
            )
        ).order_by(Post.creation_time.desc(), Post.id.desc()).first()

    else:
        history = session.get('neibr_random_history', [])
        seq = session.get('neibr_seq_random', [])

        if not history:
            if seq and post.id in seq:
                history = seq[:]
            else:
                history = [post.id]

        if post.id not in history:
            history.append(post.id)

        cursor = history.index(post.id)
        session['neibr_random_history'] = history
        session['neibr_random_cursor'] = cursor

        if cursor > 0:
            preview_index = cursor - 1
            previous_post = resolve_visible_post(history[preview_index])
            while preview_index >= 0 and previous_post is None:
                history.pop(preview_index)
                cursor -= 1
                preview_index -= 1
                if preview_index >= 0:
                    previous_post = resolve_visible_post(history[preview_index])
            if previous_post is None:
                cursor = max(cursor, 0)

        forward_index = cursor + 1
        while forward_index < len(history):
            next_candidate = resolve_visible_post(history[forward_index])
            if next_candidate:
                next_post = next_candidate
                break
            history.pop(forward_index)
        else:
            next_candidate = random_visible_post(exclude_ids=history)
            if next_candidate:
                history.append(next_candidate.id)
                next_post = next_candidate

        cursor = history.index(post.id)
        session['neibr_random_history'] = history
        session['neibr_random_cursor'] = cursor

    # 读取评论
    comments_file = os.path.join(folder_path, 'comments.yaml')
    if os.path.exists(comments_file):
        with open(comments_file, 'r') as f:
            comments = yaml.safe_load(f) or []
    else:
        comments = []

    # 处理评论提交
    if request.method == 'POST':
        new_comment = {
            'username': current_user.username,
            'content': request.form['comment'],
            'timestamp': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        }
        comments.append(new_comment)

        # 写入评论到 YAML 文件
        with open(comments_file, 'w') as f:
            yaml.safe_dump(comments, f)

        flash('评论已提交！', 'success')
        return redirect(url_for('neibr.post_detail', title=post.title, src=src, pid=post.id))

    if previous_post and previous_post.id == post.id:
        previous_post = None
    if next_post and next_post.id == post.id:
        next_post = None

    previous_url = url_for('neibr.post_detail', title=previous_post.title, src=src, pid=previous_post.id) if previous_post else None
    next_url = url_for('neibr.post_detail', title=next_post.title, src=src, pid=next_post.id) if next_post else None

    can_edit = current_user.is_authenticated and post.user_id == current_user.id


    return render_template(
        'post_detail.html',
        post=post,
        author=author,
        post_text=post_text,
        media_files=media_files,
        remote_media=remote_media,
        comments=comments,
        previous_post=previous_post,
        next_post=next_post,
        previous_url=previous_url,
        next_url=next_url,
        can_edit=can_edit,
        feed_source=src
    )


@neibr_bp.route('/edit_post/<string:title>', methods=['GET', 'POST'])
@login_required
def edit_post(title):
    post = Post.query.filter_by(title=title).first_or_404()

    # 确保当前用户是帖子作者
    if post.user_id != current_user.id:
        flash('您无权编辑此帖子。', 'error')
        return redirect(url_for('neibr.index'))

    folder_path = os.path.join(UPLOAD_BASE_PATH, str(current_user.id), str(post.id))

    if request.method == 'POST':
        # 更新标题和正文内容
        post.title = request.form['title']
        post.tags = request.form['tags']  # 添加更新标签

        body_text = request.form['post_text']
        remote_links_raw = request.form.get('media_links', '')

        is_hidden = request.form.get('is_hidden')
        post.is_hidden = True if is_hidden else False

        # 更新帖子文案
        folder_path = os.path.join(UPLOAD_BASE_PATH, str(current_user.id), str(post.id))

        author_name = User.query.get(post.user_id).username
        file_content = build_post_file_content(post, body_text, author_name, updated_at=datetime.utcnow())
        with open(os.path.join(folder_path, 'post.txt'), 'w') as f:
            f.write(file_content)

        # 处理媒体文件上传
        if 'media_files' in request.files:
            for file in request.files.getlist('media_files'):
                if file and file.filename:
                    filename = sanitize_filename(file)

                    if not allowed_file(filename):
                        flash(f'文件类型不允许：{file.filename}', 'warning')
                        continue

                    ext = filename.rsplit('.', 1)[-1].lower()
                    file_path = os.path.join(folder_path, filename)

                    if ext in COMPRESSIBLE_IMAGE_EXTENSIONS:
                        try:
                            compress_and_save_image(file, file_path)
                        except UnidentifiedImageError:
                            flash(f'图片文件无法识别：{file.filename}，请上传有效图片', 'danger')
                            continue
                    else:
                        file.save(file_path)

        # 处理删除媒体文件请求
        delete_files = request.form.getlist('delete_files')
        for filename in delete_files:
            file_path = os.path.join(folder_path, filename)
            if os.path.exists(file_path):
                os.remove(file_path)

        remote_links = sanitize_remote_links(remote_links_raw)
        save_remote_links(folder_path, remote_links)
        ensure_post_cover(post, refresh=True)

        db.session.commit()
        flash('帖子已更新。', 'success')
        return redirect(url_for('neibr.post_detail', title=post.title, pid=post.id))

    # 读取帖子文案
    folder_path = os.path.join(UPLOAD_BASE_PATH, str(current_user.id), str(post.id))
    text_path = os.path.join(folder_path, 'post.txt')
    if os.path.exists(text_path):
        with open(text_path, 'r') as f:
            _, body_text = parse_post_file(f.read())
            post_text = body_text
    else:
        post_text = ''

        
    # 获取媒体文件列表
    media_files = []
    if os.path.isdir(folder_path):
        media_files = [
            f for f in os.listdir(folder_path)
            if f not in {'post.txt', 'comments.yaml', REMOTE_LINKS_FILENAME, 'cover.jpg'}
        ]
        remote_media = load_remote_links(folder_path)
    else:
        remote_media = []
    remote_links_text = '\n'.join(link['url'] for link in remote_media)

    return render_template('edit_post.html', post=post, post_text=post_text, media_files=media_files, remote_media=remote_media, remote_links_text=remote_links_text)



@neibr_bp.route('/media/<user_id>/<post_id>/<path:filename>')
def media_file(user_id, post_id, filename):
    # 1) 校验后缀
    if not allowed_file(filename):
        abort(403)  # Forbidden，不在白名单里的类型一律拒绝

    # 2) 计算真实路径
    base = os.path.join(BASE_DIR, 'Neibr', 'neibr')
    folder = os.path.join(base, user_id, post_id)
    full_path = os.path.join(folder, filename)

    # 3) 文件存在性检查
    if not os.path.isfile(full_path):
        abort(404)

    # 4) 安全地发送文件
    return send_from_directory(folder, filename)




@neibr_bp.route('/api/posts')
@login_required
def api_posts():
    src  = request.args.get('src', 'latest')
    page = int(request.args.get('page', 1))
    per_page = 10

    # 基础查询：公开或本人的帖子
    base_q = Post.query.filter(
      (Post.is_hidden == False) | (Post.user_id == current_user.id)
    )

    if src == 'latest':
        q = base_q.order_by(Post.creation_time.desc())
    elif src == 'random':
        q = base_q.order_by(db.func.random())
    elif src == 'my':
        q = base_q.filter_by(user_id=current_user.id) \
                  .order_by(Post.creation_time.desc())
    else:
        q = base_q.order_by(Post.creation_time.desc())

    total = q.count()
    posts = q.offset((page - 1) * per_page).limit(per_page).all()

    user_ids = {p.user_id for p in posts}
    if user_ids:
        users = User.query.filter(User.id.in_(user_ids)).all()
        user_map = {u.id: u.username for u in users}
    else:
        user_map = {}

    cards = [build_post_card(p, src, user_map.get(p.user_id, '神秘邻居')) for p in posts]
    items = [{
        'title': card['title'],
        'author': card['author'],
        'date': card['created_at'],
        'tags': card['tags'],
        'summary': card['summary'],
        'thumbnail': card['thumbnail'],
        'url': card['detail_url'],
        'edit_url': card['edit_url'],
        'is_hidden': card['is_hidden']
    } for card in cards]

    return jsonify({
        'posts': items,
        'has_more': page * per_page < total
    })
