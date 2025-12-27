# Neibr/views.py
from flask import render_template, request, redirect, url_for, flash, current_app  # type: ignore
from . import neibr_bp, db  # 从 Neibr/__init__.py 导入蓝图和本地数据库实例
from flask_login import login_required, current_user, login_user  # type: ignore # Flask-Login 用于用户会话管理
from .models import User, Post  # 从本地 models.py 导入 User 和 Post 模型
from werkzeug.security import generate_password_hash, check_password_hash  # type: ignore # 用于密码加密和验证
import os
import shutil
import io
import base64
import binascii
import multiprocessing
import tempfile
from PIL import Image
from PIL import UnidentifiedImageError
from PIL import ImageOps, ImageDraw
from werkzeug.utils import secure_filename  # type: ignore
import yaml
from datetime import datetime, timezone, timedelta
from flask import send_from_directory, abort  # type: ignore
from flask import session
from flask import jsonify
from math import ceil
from markupsafe import Markup, escape  # 新增此行
import re
from unidecode import unidecode
from urllib.parse import urlparse
from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError
import requests
from typing import Any, Optional, List


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

IMAGE_QUALITY = 22
REMOTE_LINKS_FILENAME = 'media_links.yaml'
MAX_REMOTE_COVER_BYTES = 5 * 1024 * 1024
COVER_DATA_URI_PREFIX = 'data:image/jpeg;base64,'

COMPRESSIBLE_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
IMAGE_EXTENSIONS = COMPRESSIBLE_IMAGE_EXTENSIONS | {'nef'}
VIDEO_EXTENSIONS = {'mp4', 'webm', 'mov'}
AUDIO_EXTENSIONS = {'mp3', 'wav', 'flac'}
DOCUMENT_EXTENSIONS = {'pdf', 'docx', 'xlsx', 'pptx'}
ALLOWED_LINK_SCHEMES = {'http', 'https'}
FRONT_MATTER_DELIM = '---'
CHINA_TZ = timezone(timedelta(hours=8))


def _neibr_storage_dir() -> str:
    return current_app.config.get('NEIBR_STORAGE_DIR') or os.path.join(
        current_app.instance_path,
        'Neibr',
        'neibr'
    )


def _coerce_datetime(value: Any) -> Optional[datetime]:
    """将字符串或 datetime 对象转换为 datetime，解析常见格式。"""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        for pattern in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y/%m/%d %H:%M:%S'):
            try:
                return datetime.strptime(value, pattern)
            except ValueError:
                continue
    return None


def convert_to_china_tz(dt: Optional[datetime]) -> Optional[datetime]:
    """将时间转换为中国标准时间（假定原始值为 UTC 或无时区）。"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(CHINA_TZ)


def format_china_datetime(dt: Optional[datetime], fmt: str = '%Y-%m-%d %H:%M') -> str:
    localized = convert_to_china_tz(dt)
    return localized.strftime(fmt) if localized else ''


@neibr_bp.app_template_filter('bjt_format')
def bjt_format(value: Any, fmt: str = '%Y-%m-%d %H:%M') -> str:
    dt = _coerce_datetime(value)
    if dt is None:
        return value or ''
    return format_china_datetime(dt, fmt)


def allowed_file(filename):
    allowed_extensions = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS | AUDIO_EXTENSIONS | DOCUMENT_EXTENSIONS | {'MOV'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions


def _should_compress_images(files) -> bool:
    max_files = current_app.config.get('NEIBR_COMPRESS_MAX_FILES')
    if max_files is None:
        return True
    try:
        max_files = int(max_files)
    except (TypeError, ValueError):
        return True
    if max_files <= 0:
        return False
    image_count = sum(
        1 for f in files
        if f and f.filename and f.filename.rsplit('.', 1)[-1].lower() in COMPRESSIBLE_IMAGE_EXTENSIONS
    )
    return image_count <= max_files


def compress_and_save_image(file_storage, save_path):
    try:
        img = Image.open(file_storage.stream)
        img = ImageOps.exif_transpose(img)
        max_edge = current_app.config.get('NEIBR_IMAGE_MAX_EDGE', 2560)
        if max_edge and max(img.size) > max_edge:
            img.thumbnail((max_edge, max_edge), Image.LANCZOS)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        quality = current_app.config.get('NEIBR_IMAGE_QUALITY', IMAGE_QUALITY)
        optimize = bool(current_app.config.get('NEIBR_IMAGE_OPTIMIZE', False))
        img.save(save_path, format='JPEG', quality=quality, optimize=optimize)
    except UnidentifiedImageError:
        raise  # 交由上层处理（或你可以 flash 一句）
        

def _compress_image_file(image_path: str, max_edge: int, quality: int, optimize: bool) -> bool:
    try:
        with Image.open(image_path) as img:
            img = ImageOps.exif_transpose(img)
            if max_edge and max(img.size) > max_edge:
                img.thumbnail((max_edge, max_edge), Image.LANCZOS)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            dir_name = os.path.dirname(image_path)
            with tempfile.NamedTemporaryFile(delete=False, dir=dir_name, suffix='.jpg') as tmp:
                tmp_path = tmp.name
            img.save(tmp_path, format='JPEG', quality=quality, optimize=optimize)
        os.replace(tmp_path, image_path)
        return True
    except UnidentifiedImageError:
        return False
    except Exception:
        return False


def _compress_images_worker(paths: List[str], max_edge: int, quality: int, optimize: bool) -> None:
    for path in paths:
        _compress_image_file(path, max_edge, quality, optimize)


def _start_background_compression(paths: List[str]) -> None:
    if not paths:
        return
    max_edge = current_app.config.get('NEIBR_IMAGE_MAX_EDGE', 2560)
    quality = current_app.config.get('NEIBR_IMAGE_QUALITY', IMAGE_QUALITY)
    optimize = bool(current_app.config.get('NEIBR_IMAGE_OPTIMIZE', False))
    process = multiprocessing.Process(
        target=_compress_images_worker,
        args=(paths, max_edge, quality, optimize),
        daemon=True
    )
    process.start()


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
    return os.path.join(_neibr_storage_dir(), str(post.user_id), str(post.id))


def resolve_visible_post(post_id: int) -> Optional[Post]:
    post = Post.query.get(post_id)
    if not post:
        return None
    if post.is_hidden and post.user_id != current_user.id:
        return None
    return post


def ensure_post_owner(post: Post):
    """确保当前用户有权限修改帖子。"""
    if post.user_id == current_user.id:
        return
    if getattr(current_user, 'is_admin', False):
        return
    abort(403)


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
            created = format_china_datetime(post.creation_time)
            snippet_source = f"{author} · 发布于 {created}"

    snippet = _clean_summary_text(snippet_source)
    if not snippet:
        return ''
    if len(snippet) <= limit:
        return snippet
    return snippet[:limit].rstrip() + '…'


def generate_cover_base64(image: Image.Image) -> str:
    """裁剪为 16:9 并返回 Base64 编码的 JPEG 字符串。"""
    target_size = (1280, 720)
    image = image.convert('RGB')
    cover = ImageOps.fit(image, target_size, method=Image.LANCZOS)
    buffer = io.BytesIO()
    cover.save(buffer, format='JPEG', quality=86, optimize=True)
    return base64.b64encode(buffer.getvalue()).decode('ascii')


def build_placeholder_cover_base64() -> str:
    """生成渐变占位封面并返回 Base64 字符串。"""
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
    buffer = io.BytesIO()
    img.save(buffer, format='JPEG', quality=85, optimize=True)
    return base64.b64encode(buffer.getvalue()).decode('ascii')


def _build_cover_from_local(path: str) -> Optional[str]:
    try:
        with Image.open(path) as img:
            return generate_cover_base64(img)
    except Exception:
        return None


def _build_cover_from_remote(url: str) -> Optional[str]:
    try:
        response = requests.get(url, timeout=8, stream=True)
        response.raise_for_status()

        buffer = io.BytesIO()
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                buffer.write(chunk)
            if buffer.tell() > MAX_REMOTE_COVER_BYTES:
                raise ValueError('remote image too large')

        buffer.seek(0)
        with Image.open(buffer) as img:
            return generate_cover_base64(img)
    except Exception:
        return None


def _build_cover_from_base64(data: str) -> Optional[str]:
    if not data:
        return None
    payload = data
    if data.startswith('data:'):
        _, _, payload = data.partition(',')
    try:
        decoded = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError):
        return None
    buffer = io.BytesIO(decoded)
    try:
        with Image.open(buffer) as img:
            return generate_cover_base64(img)
    except Exception:
        return None


def ensure_post_cover(post: Post, refresh: bool = False) -> str:
    """
    生成并缓存帖子封面图片 Base64：
    1. 优先使用本地上传图片；
    2. 其次尝试下载外链图片；
    3. 若均没有，则生成占位封面。
    """
    if post.cover_image and not refresh:
        return COVER_DATA_URI_PREFIX + post.cover_image

    folder = get_post_folder(post)
    os.makedirs(folder, exist_ok=True)

    cover_b64: Optional[str] = None

    # 1) 查找本地图片
    if os.path.isdir(folder):
        for fname in sorted(os.listdir(folder)):
            if fname in {'post.txt', 'comments.yaml', REMOTE_LINKS_FILENAME}:
                continue
            full_path = os.path.join(folder, fname)
            if not os.path.isfile(full_path):
                continue
            ext = fname.rsplit('.', 1)[-1].lower()
            if ext in {'jpg', 'jpeg', 'png', 'gif', 'webp'}:
                cover_b64 = _build_cover_from_local(full_path)
                if cover_b64:
                    break

    # 2) 远程图片
    if not cover_b64:
        remote_links = load_remote_links(folder)
        for item in remote_links:
            if item.get('type') == 'image':
                cover_b64 = _build_cover_from_remote(item['url'])
                if cover_b64:
                    break

    # 3) 占位封面
    if not cover_b64:
        cover_b64 = build_placeholder_cover_base64()

    post.cover_image = cover_b64
    return COVER_DATA_URI_PREFIX + cover_b64


def get_cover_data_uri(post: Post) -> str:
    """返回封面 Data URI，没有则生成并返回空字符串。"""
    if not post.cover_image:
        return ensure_post_cover(post)
    return COVER_DATA_URI_PREFIX + post.cover_image


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
        f"Created: {format_china_datetime(timestamp, '%Y-%m-%d %H:%M:%S')}",
        f"Updated: {format_china_datetime(updated_ts, '%Y-%m-%d %H:%M:%S')}",
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
        'created_at': format_china_datetime(post.creation_time),
        'tags': tags,
        'summary': extract_post_summary(post),
        'thumbnail': get_cover_data_uri(post),
        'detail_url': url_for('neibr.post_detail', title=post.title, src=src, pid=post.id),
        'edit_url': url_for('neibr.edit_post', post_id=post.id) if post.user_id == current_user.id else None,
        'is_hidden': post.is_hidden
    }


def _cover_error_response(message: str, status_code: int = 400):
    response = jsonify({'status': 'error', 'message': message})
    response.status_code = status_code
    return response


@neibr_bp.route('/api/posts/<int:post_id>/cover', methods=['POST'])
@login_required
def api_set_cover(post_id: int):
    post = Post.query.get_or_404(post_id)
    ensure_post_owner(post)

    payload = request.get_json(silent=True) or {}
    source = (payload.get('source') or '').lower()

    if source not in {'local', 'remote', 'data'}:
        return _cover_error_response('不支持的封面来源类型。')

    cover_b64: Optional[str] = None

    if source == 'local':
        filename = payload.get('filename')
        if not filename:
            return _cover_error_response('缺少要设为封面的文件名。')
        safe_name = os.path.basename(filename)
        folder = get_post_folder(post)
        file_path = os.path.join(folder, safe_name)
        if not os.path.isfile(file_path):
            return _cover_error_response('指定的本地文件不存在。')
        ext = safe_name.rsplit('.', 1)[-1].lower() if '.' in safe_name else ''
        if ext not in IMAGE_EXTENSIONS:
            return _cover_error_response('只能使用图片文件作为封面。')
        cover_b64 = _build_cover_from_local(file_path)
    elif source == 'remote':
        url = (payload.get('url') or '').strip()
        if not url:
            return _cover_error_response('缺少远程图片链接。')
        parsed = urlparse(url)
        if parsed.scheme not in ALLOWED_LINK_SCHEMES:
            return _cover_error_response('远程链接协议不受支持。')
        cover_b64 = _build_cover_from_remote(url)
    else:
        raw = payload.get('data') or payload.get('base64')
        cover_b64 = _build_cover_from_base64(raw or '')

    if not cover_b64:
        return _cover_error_response('无法解析图片，请确认文件或链接有效。')

    post.cover_image = cover_b64
    db.session.commit()

    message = '封面更新成功。'
    flash(message, 'success')
    return jsonify({
        'status': 'ok',
        'cover': COVER_DATA_URI_PREFIX + cover_b64,
        'message': message
    })


@neibr_bp.route('/api/posts/<int:post_id>/cover/auto', methods=['POST'])
@login_required
def api_auto_cover(post_id: int):
    post = Post.query.get_or_404(post_id)
    ensure_post_owner(post)

    cover_uri = ensure_post_cover(post, refresh=True)
    db.session.commit()
    message = '已根据最新媒体自动选定封面。'
    flash(message, 'success')
    return jsonify({
        'status': 'ok',
        'cover': cover_uri,
        'message': message
    })


@neibr_bp.route('/api/posts/<int:post_id>/cover', methods=['DELETE'])
@login_required
def api_delete_cover(post_id: int):
    post = Post.query.get_or_404(post_id)
    ensure_post_owner(post)

    post.cover_image = build_placeholder_cover_base64()
    db.session.commit()
    message = '封面已重置为默认图。'
    flash(message, 'info')
    return jsonify({
        'status': 'ok',
        'cover': COVER_DATA_URI_PREFIX + post.cover_image,
        'message': message
    })


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

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

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
    placeholder_uri = COVER_DATA_URI_PREFIX + build_placeholder_cover_base64()
    base_form_values = {
        'title': '',
        'tags': '',
        'post_text': '',
        'is_hidden': False,
        'remote_links_text': '',
        'remote_input': '',
        'cover_preview': None,
        'initial_media': {'local': [], 'remote': []}
    }

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        tags = request.form.get('tags', '').strip()
        post_text = request.form.get('post_text', '')
        files = request.files.getlist('media_files')
        if not files:
            files = request.files.getlist('files')
        remote_links_raw = request.form.get('media_links', '')
        is_hidden = bool(request.form.get('is_hidden'))
        cover_data_raw = (request.form.get('cover_data') or '').strip()
        cover_remote_url = (request.form.get('cover_remote_url') or '').strip()
        remote_input_value = request.form.get('remote_input', '').strip()

        remote_links = sanitize_remote_links(remote_links_raw)

        form_values = {
            'title': title,
            'tags': tags,
            'post_text': post_text,
            'is_hidden': is_hidden,
            'remote_links_text': "\n".join(link['url'] for link in remote_links),
            'remote_input': remote_input_value,
            'cover_preview': None,
            'initial_media': {'local': [], 'remote': remote_links}
        }

        if cover_data_raw:
            form_values['cover_preview'] = f"{COVER_DATA_URI_PREFIX}{cover_data_raw}"
        elif cover_remote_url:
            form_values['cover_preview'] = cover_remote_url

        if not title:
            flash('标题不能为空。', 'warning')
            return render_template(
                'create_post.html',
                title='创建帖子',
                cover_placeholder=placeholder_uri,
                form_values=form_values
            )

        existing = Post.query.filter_by(title=title).first()
        if existing:
            flash('标题已存在，请换一个新的标题。', 'warning')
            return render_template(
                'create_post.html',
                title='创建帖子',
                cover_placeholder=placeholder_uri,
                form_values=form_values
            )

        # 创建帖子记录
        post = Post(title=title, tags=tags, user_id=current_user.id)
        post.is_hidden = is_hidden

        db.session.add(post)
        try:
            db.session.flush()  # 获取 post.id
        except IntegrityError:
            db.session.rollback()
            flash('标题已存在，请换一个新的标题。', 'warning')
            return render_template(
                'create_post.html',
                title='创建帖子',
                cover_placeholder=placeholder_uri,
                form_values=form_values
            )
        except Exception:
            db.session.rollback()
            flash('创建帖子时发生错误，请稍后重试。', 'danger')
            return render_template(
                'create_post.html',
                title='创建帖子',
                cover_placeholder=placeholder_uri,
                form_values=form_values
            )

        # 构建帖子文件夹路径：static/neibr/user_id/post_id
        folder_path = os.path.join(_neibr_storage_dir(), str(current_user.id), str(post.id))
        os.makedirs(folder_path, exist_ok=True)

        compress_images = _should_compress_images(files)
        compress_paths: List[str] = []
        for file in files:
            if file and file.filename:
                filename = sanitize_filename(file)

                # 判断后缀是否合法
                if not allowed_file(filename):
                    flash(f'文件类型不允许：{file.filename}', 'warning')
                    continue

                ext = filename.rsplit('.', 1)[1].lower()
                file_path = os.path.join(folder_path, filename)

                if ext in COMPRESSIBLE_IMAGE_EXTENSIONS and compress_images:
                    file.save(file_path)
                    compress_paths.append(file_path)
                else:
                    file.save(file_path)

        if compress_paths:
            _start_background_compression(compress_paths)

        save_remote_links(folder_path, remote_links)

        cover_selected = False

        if cover_data_raw:
            cover_b64 = _build_cover_from_base64(cover_data_raw)
            if cover_b64:
                post.cover_image = cover_b64
                cover_selected = True
            else:
                flash('封面数据解析失败，已自动生成封面。', 'warning')

        if not cover_selected and cover_remote_url:
            cover_b64 = _build_cover_from_remote(cover_remote_url)
            if cover_b64:
                post.cover_image = cover_b64
                cover_selected = True
            else:
                flash('封面链接不可用，已自动生成封面。', 'warning')

        if not cover_selected:
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
    
    return render_template('create_post.html', title='创建帖子', cover_placeholder=placeholder_uri, form_values=base_form_values)

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
    folder_path = os.path.join(_neibr_storage_dir(), str(user_id), str(post.id))

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
    excluded_files = {'post.txt', 'comments.yaml', REMOTE_LINKS_FILENAME}
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
            raw_comments = yaml.safe_load(f) or []
    else:
        raw_comments = []

    formatted_comments = []
    for item in raw_comments:
        entry = dict(item)
        ts_raw = entry.get('timestamp')
        dt = _coerce_datetime(ts_raw)
        entry['timestamp_display'] = format_china_datetime(dt, '%Y-%m-%d %H:%M') if dt else (ts_raw or '')
        formatted_comments.append(entry)
    comments = formatted_comments

    # 处理评论提交
    if request.method == 'POST':
        new_comment = {
            'username': current_user.username,
            'content': request.form['comment'],
            'timestamp': format_china_datetime(datetime.utcnow(), '%Y-%m-%d %H:%M:%S')
        }
        raw_comments.append(new_comment)

        # 写入评论到 YAML 文件
        with open(comments_file, 'w') as f:
            yaml.safe_dump(raw_comments, f)

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


def _handle_edit_post(post: Post):
    """共用的帖子编辑处理逻辑，支持按 ID 或旧标题访问。"""
    if post.user_id != current_user.id:
        flash('您无权编辑此帖子。', 'error')
        return redirect(url_for('neibr.index'))

    folder_path = os.path.join(_neibr_storage_dir(), str(post.user_id), str(post.id))

    if request.method == 'POST':
        post.title = request.form['title']
        post.tags = request.form['tags']

        body_text = request.form['post_text']
        remote_links_raw = request.form.get('media_links', '')

        is_hidden = request.form.get('is_hidden')
        post.is_hidden = True if is_hidden else False

        author_name = User.query.get(post.user_id).username
        file_content = build_post_file_content(post, body_text, author_name, updated_at=datetime.utcnow())
        with open(os.path.join(folder_path, 'post.txt'), 'w') as f:
            f.write(file_content)

        files = request.files.getlist('media_files') if 'media_files' in request.files else []
        compress_images = _should_compress_images(files)
        compress_paths: List[str] = []
        for file in files:
            if file and file.filename:
                filename = sanitize_filename(file)

                if not allowed_file(filename):
                    flash(f'文件类型不允许：{file.filename}', 'warning')
                    continue

                ext = filename.rsplit('.', 1)[-1].lower()
                file_path = os.path.join(folder_path, filename)

                if ext in COMPRESSIBLE_IMAGE_EXTENSIONS and compress_images:
                    file.save(file_path)
                    compress_paths.append(file_path)
                else:
                    file.save(file_path)

        if compress_paths:
            _start_background_compression(compress_paths)

        delete_files = request.form.getlist('delete_files')
        for filename in delete_files:
            file_path = os.path.join(folder_path, filename)
            if os.path.exists(file_path):
                os.remove(file_path)

        remote_links = sanitize_remote_links(remote_links_raw)
        save_remote_links(folder_path, remote_links)

        cover_selected = False
        cover_data_raw = (request.form.get('cover_data') or '').strip()
        cover_remote_url = (request.form.get('cover_remote_url') or '').strip()

        if cover_data_raw:
            cover_b64 = _build_cover_from_base64(cover_data_raw)
            if cover_b64:
                post.cover_image = cover_b64
                cover_selected = True
            else:
                flash('封面数据解析失败，已保留原封面。', 'warning')

        if not cover_selected and cover_remote_url:
            cover_b64 = _build_cover_from_remote(cover_remote_url)
            if cover_b64:
                post.cover_image = cover_b64
                cover_selected = True
            else:
                flash('封面链接不可用，已保留原封面。', 'warning')

        if not cover_selected and not post.cover_image:
            ensure_post_cover(post, refresh=True)

        db.session.commit()
        flash('帖子已更新。', 'success')
        return redirect(url_for('neibr.post_detail', title=post.title, pid=post.id))

    text_path = os.path.join(folder_path, 'post.txt')
    if os.path.exists(text_path):
        with open(text_path, 'r') as f:
            _, body_text = parse_post_file(f.read())
            post_text = body_text
    else:
        post_text = ''

    media_files = []
    if os.path.isdir(folder_path):
        media_files = [
            f for f in os.listdir(folder_path)
            if f not in {'post.txt', 'comments.yaml', REMOTE_LINKS_FILENAME}
        ]
        remote_media = load_remote_links(folder_path)
    else:
        remote_media = []
    remote_links_text = '\n'.join(link['url'] for link in remote_media)

    local_media_payload = [
        {
            'filename': fname,
            'url': url_for('neibr.media_file', user_id=post.user_id, post_id=post.id, filename=fname),
            'kind': detect_media_type(fname)
        }
        for fname in media_files
    ]

    remote_media_payload = [
        {
            'url': item['url'],
            'type': item.get('type') or detect_media_type(item.get('url', ''))
        }
        for item in remote_media
    ]

    initial_media = {
        'local': local_media_payload,
        'remote': remote_media_payload
    }

    cover_uri = get_cover_data_uri(post)
    placeholder_uri = COVER_DATA_URI_PREFIX + build_placeholder_cover_base64()

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return render_template(
        'edit_post.html',
        post=post,
        post_text=post_text,
        media_files=media_files,
        remote_media=remote_media,
        remote_links_text=remote_links_text,
        initial_media=initial_media,
        cover_uri=cover_uri,
        cover_placeholder=placeholder_uri
    )


@neibr_bp.route('/edit_post/<int:post_id>', methods=['GET', 'POST'])
@login_required
def edit_post(post_id):
    post = Post.query.get_or_404(post_id)
    return _handle_edit_post(post)


@neibr_bp.route('/edit_post/<string:title>', methods=['GET', 'POST'])
@login_required
def edit_post_legacy(title):
    post = Post.query.filter_by(title=title).first_or_404()
    if request.method == 'GET':
        return redirect(url_for('neibr.edit_post', post_id=post.id))
    return _handle_edit_post(post)


@neibr_bp.route('/delete_post/<int:post_id>', methods=['POST'])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    ensure_post_owner(post)

    folder_path = get_post_folder(post)
    if os.path.isdir(folder_path):
        shutil.rmtree(folder_path, ignore_errors=True)

    try:
        db.session.delete(post)
        db.session.commit()
        flash('帖子已删除。', 'success')
    except Exception:
        db.session.rollback()
        flash('删除帖子时出现问题，请稍后重试。', 'error')
        return redirect(url_for('neibr.edit_post', post_id=post_id))

    return redirect(url_for('neibr.index'))



@neibr_bp.route('/media/<user_id>/<post_id>/<path:filename>')
def media_file(user_id, post_id, filename):
    # 1) 校验后缀
    if not allowed_file(filename):
        abort(403)  # Forbidden，不在白名单里的类型一律拒绝

    # 2) 计算真实路径
    base = _neibr_storage_dir()
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

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return jsonify({
        'posts': items,
        'has_more': page * per_page < total
    })
