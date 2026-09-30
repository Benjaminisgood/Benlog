import os, math
import re
import random
from flask import request, redirect, flash, render_template, abort, current_app, url_for, jsonify
import frontmatter
from datetime import datetime
from . import blog_bp
from flask_login import login_required, current_user
from Benlog.render import clean_html, is_draft, render_markdown
from Benlog.security import clean_slug, editor_required, safe_slug

# POSTS_DIR 存放 blog 模块的 Markdown 文件
def _posts_dir() -> str:
    return current_app.config.get('BLOG_POSTS_DIR') or os.path.join(
        current_app.instance_path,
        'Blog',
        'posts'
    )

ALLOWED_EXTENSIONS = {'md', 'html'}
PER_PAGE = 10  # 每页显示条数

COVER_KEYS = ('cover', 'image', 'banner', 'thumbnail', 'hero')
BLUE_GRADIENTS = [
    ('#60a5fa', '#2563eb'),
    ('#38bdf8', '#0ea5e9'),
    ('#818cf8', '#3730a3'),
    ('#22d3ee', '#0ea5e9'),
    ('#93c5fd', '#3b82f6')
]


def hex_to_rgba(hex_color: str, alpha: float = 0.85) -> str:
    """将 HEX 颜色转换为带透明度的 rgba 字符串。"""
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 3:
        hex_color = ''.join(c * 2 for c in hex_color)
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return f'rgba({r}, {g}, {b}, {alpha})'


def pick_gradient(key: str) -> str:
    """根据 key 选择一个渐变背景。"""
    colors = BLUE_GRADIENTS[hash(key) % len(BLUE_GRADIENTS)]
    return f"linear-gradient(135deg, {hex_to_rgba(colors[0], 0.92)}, {hex_to_rgba(colors[1], 0.82)})"


def normalize_tags(raw_tags):
    if not raw_tags:
        return []
    if isinstance(raw_tags, str):
        return [tag.strip() for tag in raw_tags.split(',') if tag.strip()]
    if isinstance(raw_tags, (list, tuple, set)):
        return [str(tag).strip() for tag in raw_tags if str(tag).strip()]
    return []


def strip_markup(text: str) -> str:
    """移除 Markdown / HTML 标记，提取纯文本。"""
    if not text:
        return ''
    text = re.sub(r'```.*?```', ' ', text, flags=re.S)
    text = re.sub(r'`[^`]+`', ' ', text)
    text = re.sub(r'!\[[^\]]*\]\([^\)]+\)', ' ', text)
    text = re.sub(r'\[[^\]]*\]\([^\)]+\)', ' ', text)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'[#>*_~\-]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def create_excerpt(text: str, limit: int = 140) -> str:
    cleaned = strip_markup(text)
    if not cleaned:
        return ''
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[:limit].rstrip() + '…'


def select_cover(metadata: dict) -> str | None:
    for key in COVER_KEYS:
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def load_post_card(slug: str, last_modified: datetime):
    """加载单篇文章的 Frontmatter 和摘要信息。"""
    posts_dir = _posts_dir()
    md_path = os.path.join(posts_dir, f"{slug}.md")
    html_path = os.path.join(posts_dir, f"{slug}.html")

    title = slug
    summary = ''
    cover = None
    tags = []
    published = None

    if os.path.exists(md_path):
        try:
            post_data = frontmatter.load(md_path)
            metadata = post_data.metadata or {}
            title = metadata.get('title') or title
            summary = metadata.get('description') or metadata.get('summary') or create_excerpt(post_data.content)
            cover = select_cover(metadata)
            tags = normalize_tags(metadata.get('tags'))
            published = metadata.get('date')
        except Exception:
            with open(md_path, 'r', encoding='utf-8') as f:
                summary = create_excerpt(f.read())
    elif os.path.exists(html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        summary = create_excerpt(html_content)
    else:
        return None

    display_meta = published if isinstance(published, str) and published.strip() else last_modified.strftime("%Y-%m-%d %H:%M")

    return {
        'slug': slug,
        'title': title,
        'summary': summary,
        'cover': cover,
        'tags': tags,
        'meta': display_meta,
        'last_modified': last_modified,
        'gradient': pick_gradient(slug)
    }

def get_all_posts(include_drafts=True):
    """返回按时间倒序排列的所有文章元信息列表"""
    posts = []
    posts_dir = _posts_dir()
    os.makedirs(posts_dir, exist_ok=True)
    for filename in os.listdir(posts_dir):
        if not filename.endswith(('.md', '.html')):
            continue
        slug = filename.rsplit('.', 1)[0]
        if not safe_slug(slug):
            continue
        filepath = os.path.join(posts_dir, filename)
        metadata = {}
        if filename.endswith('.md'):
            try:
                metadata = frontmatter.load(filepath).metadata or {}
            except Exception:
                metadata = {}
        draft = is_draft(metadata)
        if draft and not include_drafts:
            continue
        lm = datetime.fromtimestamp(os.path.getmtime(filepath))
        posts.append({'slug': slug, 'last_modified': lm, 'draft': draft})
    posts.sort(key=lambda x: x['last_modified'], reverse=True)
    return posts

def _can_edit():
    return current_user.is_authenticated and (getattr(current_user, 'is_admin', False) or current_user.id == 1)


def _locate_post(slug):
    slug = safe_slug(slug)
    if not slug:
        abort(404)
    posts_dir = _posts_dir()
    for ext in ('md', 'html'):
        path = os.path.join(posts_dir, f'{slug}.{ext}')
        if os.path.isfile(path):
            return path, ext
    return None, None


def _split_post(path, ext):
    with open(path, 'r', encoding='utf-8') as handle:
        raw = handle.read()
    if ext != 'md':
        return {}, raw, raw
    try:
        parsed = frontmatter.loads(raw)
    except Exception:
        return {}, raw, raw
    metadata = dict(parsed.metadata or {})
    return metadata, parsed.content or '', raw


def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def sanitize_filename(filename: str) -> str:
    # 去除路径，替换所有非字母数字、下划线、连字符、点 为下划线
    name = os.path.basename(filename)
    return re.sub(r'[^A-Za-z0-9._-]', '_', name)

@blog_bp.route('/upload', methods=['POST'])
@login_required
def upload_post():
    # 权限检查
    if not (current_user.is_admin or current_user.id == 1):
        abort(403)

    if 'post_file' not in request.files:
        flash("未选择文件", "error")
        return redirect(url_for('blog.list_posts'))

    file = request.files['post_file']
    if file.filename == '':
        flash("未选择文件", "error")
        return redirect(url_for('blog.list_posts'))

    if not allowed_file(file.filename):
        flash("只能上传 .md 或 .html 文件", "error")
        return redirect(url_for('blog.list_posts'))

    # 安全清洗文件名
    filename = sanitize_filename(file.filename)
    posts_dir = _posts_dir()
    save_path = os.path.join(posts_dir, filename)

    # 保存文件
    file.save(save_path)

    flash("上传成功！", "success")
    return redirect(url_for('blog.list_posts'))

@blog_bp.route('/')
def list_posts():
    posts_dir = _posts_dir()
    os.makedirs(posts_dir, exist_ok=True)

    # 1. 获取 page 参数
    try:
        page = int(request.args.get('page', 1))
    except ValueError:
        page = 1

    order = request.args.get('order', 'desc').lower()
    if order not in ('asc', 'desc', 'random'):
        order = 'desc'

    can_edit = _can_edit()
    all_posts = get_all_posts(include_drafts=can_edit)
    if order == 'asc':
        all_posts.sort(key=lambda x: x['last_modified'])
    elif order == 'random':
        random.shuffle(all_posts)
    random_slug = random.choice(all_posts)['slug'] if all_posts else None

    # 3. 计算总页数，并确保 page 在合理范围
    total = len(all_posts)
    total_pages = math.ceil(total / PER_PAGE) if total else 1
    page = max(1, min(page, total_pages))

    # 4. 切片出当前页的文章
    start = (page - 1) * PER_PAGE
    end   = start + PER_PAGE
    page_entries = all_posts[start:end]
    card_items = []
    for entry in page_entries:
        card = load_post_card(entry['slug'], entry['last_modified'])
        if not card:
            card = {
                'slug': entry['slug'],
                'title': entry['slug'],
                'summary': '',
                'cover': None,
                'tags': [],
                'meta': entry['last_modified'].strftime("%Y-%m-%d %H:%M"),
                'last_modified': entry['last_modified'],
                'gradient': pick_gradient(entry['slug'])
            }
        card['url'] = url_for('blog.show_post', slug=entry['slug'])
        card_items.append(card)

    can_edit = _can_edit()
    random_url = url_for('blog.show_post', slug=random_slug) if (random_slug and not can_edit) else None

    return render_template(
        'blog_index.html',
        title="Blog",
        cards=card_items,
        page=page,
        total_pages=total_pages,
        can_edit=can_edit,
        random_url=random_url,
        current_order=order
    )

@blog_bp.route('/<slug>')
def show_post(slug):
    """支持显示 .md 或 .html 文件的文章"""
    path, ext = _locate_post(slug)
    if not path:
        abort(404, description="没有找到该文章")

    metadata, body, raw = _split_post(path, ext)
    if is_draft(metadata) and not _can_edit():
        abort(404, description="没有找到该文章")

    if ext == 'md':
        content_html = render_markdown(body)
        post_title = metadata.get('title') or slug
        post_summary = metadata.get('description') or metadata.get('summary') or ''
        return render_template(
            'blog_post.html',
            post_content=content_html,
            post_date=metadata.get('date', ''),
            frontmatter=metadata,
            post_title=post_title,
            post_summary=post_summary,
            needs_math=True,
        )

    return render_template(
        'blog_post.html',
        post_content=clean_html(raw),
        post_date='',
        frontmatter={},
        post_title=slug,
        post_summary='',
        needs_math=True,
    )


@blog_bp.route('/manage_posts')
@login_required
def manage_posts():
    """管理员博客管理页面：列出所有 Markdown 文件"""
    if not (current_user.is_admin or current_user.id == 1):
        flash("无权限访问博客管理页面", "error")
        return redirect(url_for('index.home'))

    posts_dir = _posts_dir()
    if not os.path.exists(posts_dir):
        abort(500, description=f"Posts directory not found: {posts_dir}")

    posts = []
    for filename in os.listdir(posts_dir):
        if filename.endswith(('.md', '.html')):  # ✅ 支持两种后缀
            filepath = os.path.join(posts_dir, filename)
            last_modified = datetime.fromtimestamp(os.path.getmtime(filepath))
            slug, ext = filename.rsplit('.', 1)
            posts.append({
                'filename': filename,
                'slug': slug,
                'ext': ext,  # ✅ 额外加上扩展名，方便前端判断类型
                'last_modified': last_modified
            })


    posts.sort(key=lambda x: x['last_modified'], reverse=True)

    return render_template('blog_manage_posts.html', posts=posts)

@blog_bp.route('/new', methods=['POST'])
@login_required
def new_post():
    if not (current_user.is_admin or current_user.id == 1):
        abort(403)

    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    filename = f"post_{timestamp}.md"
    posts_dir = _posts_dir()
    filepath = os.path.join(posts_dir, filename)
    
    default_frontmatter = {
        'title': '新文章',
        'date': datetime.now().strftime("%Y-%m-%d"),
        'tags': ['note'],
        'summary': '',
        'status': 'published'
    }
    default_content = "在这里写 Markdown。"
    post_data = frontmatter.Post(default_content, **default_frontmatter)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(frontmatter.dumps(post_data))
    
    slug = filename.rsplit('.', 1)[0]
    flash("新文章已创建，请完善内容。", "success")
    return redirect(url_for('blog.edit_post', slug=slug))




@blog_bp.route('/preview', methods=['POST'])
@editor_required
def preview_markdown():
    html = render_markdown(request.form.get('content', ''))
    return jsonify({'html': str(html)})


@blog_bp.route('/<slug>/edit', methods=['GET', 'POST'])
@editor_required
def edit_post(slug):
    path, ext = _locate_post(slug)
    if not path:
        abort(404, description="Post not found")

    metadata, body, raw = _split_post(path, ext)
    if request.method == 'POST':
        if ext == 'md':
            metadata['title'] = (request.form.get('title') or slug).strip() or slug
            summary = (request.form.get('summary') or '').strip()
            if summary:
                metadata['summary'] = summary
            elif 'summary' in metadata:
                metadata.pop('summary')
            tags = [tag.strip() for tag in (request.form.get('tags') or '').split(',') if tag.strip()]
            if tags:
                metadata['tags'] = tags
            elif 'tags' in metadata:
                metadata.pop('tags')
            cover = (request.form.get('cover') or '').strip()
            if cover:
                metadata['cover'] = cover
            elif 'cover' in metadata:
                metadata.pop('cover')
            status = (request.form.get('status') or 'published').strip().lower()
            metadata['status'] = 'draft' if status == 'draft' else 'published'
            new_body = request.form.get('content', '')
            written = frontmatter.dumps(frontmatter.Post(new_body, **metadata))
        else:
            written = request.form.get('content', '')
        with open(path, 'w', encoding='utf-8') as handle:
            handle.write(written)
        flash("内容已保存", "success")
        return redirect(url_for('blog.show_post', slug=slug))

    tags = metadata.get('tags') or []
    if isinstance(tags, (list, tuple)):
        tags_text = ', '.join(str(tag) for tag in tags)
    else:
        tags_text = str(tags)
    return render_template(
        'blog_edit.html',
        slug=slug,
        is_markdown=ext == 'md',
        title_value=metadata.get('title') or slug,
        summary_value=metadata.get('summary') or metadata.get('description') or '',
        tags_value=tags_text,
        cover_value=metadata.get('cover') or '',
        status_value='draft' if is_draft(metadata) else 'published',
        content=body if ext == 'md' else raw,
        preview_url=url_for('blog.preview_markdown'),
    )

@blog_bp.route('/<slug>/rename', methods=['POST'])
@login_required
def rename_post(slug):
    if not safe_slug(slug):
        abort(404)
    if not (current_user.is_admin or current_user.id == 1):
        abort(403)
    new_slug = clean_slug(request.form.get('new_slug', ''))
    if not new_slug:
        flash("新名称无效。只保留字母、数字、中文、点、下划线和连字符。", "error")
        return redirect(url_for('blog.edit_post', slug=slug))
    posts_dir = _posts_dir()
    for ext in ('md', 'html'):
        old_path = os.path.join(posts_dir, f"{slug}.{ext}")
        if os.path.exists(old_path):
            new_path = os.path.join(posts_dir, f"{new_slug}.{ext}")
            if os.path.exists(new_path):
                flash("重命名失败：目标文件已存在", "error")
                return redirect(url_for('blog.edit_post', slug=slug))
            os.rename(old_path, new_path)
            flash("重命名成功", "success")
            return redirect(url_for('blog.edit_post', slug=new_slug))
    abort(404, description="Post not found")

@blog_bp.route('/<slug>/delete', methods=['POST'])
@login_required
def delete_post(slug):
    if not safe_slug(slug):
        abort(404)
    if not (current_user.is_admin or current_user.id == 1):
        abort(403)
    posts_dir = _posts_dir()
    for ext in ('md', 'html'):
        path = os.path.join(posts_dir, f"{slug}.{ext}")
        if os.path.exists(path):
            os.remove(path)
            flash("文章已删除", "success")
            return redirect(url_for('blog.manage_posts'))
    abort(404, description="Post not found")
