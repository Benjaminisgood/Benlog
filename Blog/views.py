import os, math
import re
import random
from flask import request, redirect, flash, render_template, abort, current_app, url_for
import frontmatter, markdown
from datetime import datetime
from . import blog_bp
from flask_login import login_required, current_user
from typing import Final

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

MARKDOWN_EXTENSIONS: Final[list[str]] = [
    'extra',
    'admonition',
    'codehilite',
    'pymdownx.highlight',
    'pymdownx.inlinehilite',
    'pymdownx.superfences',
    'pymdownx.tilde',
    'pymdownx.tasklist',
    'pymdownx.arithmatex',
]

MARKDOWN_EXTENSION_CONFIGS: Final[dict[str, dict]] = {
    'codehilite': {
        'guess_lang': False,
        'linenums': False,
        'noclasses': True,
    },
    'pymdownx.highlight': {
        'guess_lang': False,
        'anchor_linenums': True,
    },
    'pymdownx.superfences': {
        'custom_fences': [
            {
                'name': 'mermaid',
                'class': 'mermaid',
                'format': '!!python/name:pymdownx.superfences.fence_code_format'
            }
        ]
    },
    'pymdownx.arithmatex': {'generic': True},
}


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

def get_all_posts():
    """返回按时间倒序排列的所有文章元信息列表"""
    posts = []
    posts_dir = _posts_dir()
    if not os.path.exists(posts_dir):
        abort(500, description=f"POSTS_DIR 不存在：{posts_dir}")
    for filename in os.listdir(posts_dir):
        if filename.endswith(('.md', '.html')):
            filepath = os.path.join(posts_dir, filename)
            lm = datetime.fromtimestamp(os.path.getmtime(filepath))
            slug = filename.rsplit('.', 1)[0]
            posts.append({'slug': slug, 'last_modified': lm})
    posts.sort(key=lambda x: x['last_modified'], reverse=True)
    return posts

def allowed_file(filename: str) -> bool:
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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

    # 2. 拿到所有文章
    all_posts = get_all_posts()  # 之前定义的函数
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

    can_edit = current_user.is_authenticated and (getattr(current_user, 'is_admin', False) or current_user.id == 1)
    random_url = url_for('blog.show_post', slug=random_slug) if (random_slug and not can_edit) else None

    return render_template(
        'blog_index.html',
        title="Blog",
        cards=card_items,
        page=page,
        total_pages=total_pages,
        can_edit=can_edit,
        random_url=random_url
    )

@blog_bp.route('/<slug>')
def show_post(slug):
    """支持显示 .md 或 .html 文件的文章"""
    posts_dir = _posts_dir()
    md_path = os.path.join(posts_dir, f"{slug}.md")
    html_path = os.path.join(posts_dir, f"{slug}.html")

    if os.path.exists(md_path):
        # 解析 Markdown 文件
        post_data = frontmatter.load(md_path)
        content_md = post_data.content
        metadata = post_data.metadata or {}
        post_title = metadata.get('title') or slug
        post_summary = metadata.get('description') or metadata.get('summary')
        content_html = markdown.markdown(
            content_md,
            extensions=MARKDOWN_EXTENSIONS,
            extension_configs=MARKDOWN_EXTENSION_CONFIGS
        )
        return render_template(
            'blog_post.html',
            post_content=content_html,
            post_date=post_data.get('date', ''),
            frontmatter=metadata,
            post_title=post_title,
            post_summary=post_summary or ''
        )

    elif os.path.exists(html_path):
        # 直接读取 .html 文件内容并原样渲染
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        return render_template(
            'blog_post.html',
            post_content=html_content,
            post_date='',  # 或者你可以用某种方式提取日期
            frontmatter={},
            post_title=slug,
            post_summary=''
        )

    else:
        abort(404, description="没有找到该文章")


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

    # 生成新文件名，采用时间戳确保唯一性
    timestamp = datetime.now().strftime('%Y%m%d')
    filename = f"post_{timestamp}.md"
    posts_dir = _posts_dir()
    filepath = os.path.join(posts_dir, filename)
    
    # 定义默认 frontmatter 与内容 %H:%M:%S
    default_frontmatter = {
        'title': 'New Post',
        'date': datetime.now().strftime("%Y-%m-%d"),
        'tags': ['life', 'note'],
        'cover': 'https://images.unsplash.com/photo-1521737604893-d14cc237f11d',
        'summary': '写下你的想法……',
        'status': 'draft'
    }
    default_content = "在此处编辑内容..."
    post_data = frontmatter.Post(default_content, **default_frontmatter)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(frontmatter.dumps(post_data))
    
    slug = filename.rsplit('.', 1)[0]
    flash("新文章已创建，请完善内容。", "success")
    return redirect(url_for('blog.edit_post', slug=slug))




@blog_bp.route('/<slug>/edit', methods=['GET', 'POST'])
@login_required
def edit_post(slug):
    # 定位文件
    filepath = None
    posts_dir = _posts_dir()
    for ext in ('md', 'html'):
        p = os.path.join(posts_dir, f"{slug}.{ext}")
        if os.path.exists(p):
            filepath = p
            break
    if filepath is None:
        abort(404, description="Post not found")

    if request.method == 'POST':
        # 仅保存正文内容
        new_content = request.form.get('content', '')
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        flash("内容已保存", "success")
        return redirect(url_for('blog.show_post', slug=slug))

    # GET：读取内容并渲染编辑页面
    with open(filepath, 'r', encoding='utf-8') as f:
        file_text = f.read()
    return render_template('blog_edit.html', slug=slug, content=file_text)

@blog_bp.route('/<slug>/rename', methods=['POST'])
@login_required
def rename_post(slug):
    if not (current_user.is_admin or current_user.id == 1):
        abort(403)
    new_slug = request.form.get('new_slug', '').strip()
    if not new_slug:
        flash("新名称不能为空", "error")
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
