import os
import random
from flask import request, redirect, flash, render_template, abort, current_app, url_for
import frontmatter, markdown
from datetime import datetime
from . import edu_bp
from flask_login import login_required, current_user
import re
from math import ceil
from typing import Final

NOTES_DIR = os.path.join(os.path.dirname(__file__), 'notes')
PER_PAGE = 10  # 每页显示条目数
ALLOWED_EXTENSIONS = {'md', 'html'}

COVER_KEYS = ('cover', 'image', 'banner', 'thumbnail', 'hero')
BLUE_GRADIENTS = [
    ('#22d3ee', '#0ea5e9'),
    ('#38bdf8', '#2563eb'),
    ('#60a5fa', '#2563eb'),
    ('#818cf8', '#3730a3'),
    ('#5eead4', '#14b8a6')
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
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 3:
        hex_color = ''.join(c * 2 for c in hex_color)
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return f'rgba({r}, {g}, {b}, {alpha})'


def pick_gradient(key: str) -> str:
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


def load_note_card(slug: str, last_modified: datetime):
    md_path = os.path.join(NOTES_DIR, f"{slug}.md")
    html_path = os.path.join(NOTES_DIR, f"{slug}.html")

    title = slug
    summary = ''
    cover = None
    tags = []
    published = None

    if os.path.exists(md_path):
        try:
            note_data = frontmatter.load(md_path)
            metadata = note_data.metadata or {}
            title = metadata.get('title') or title
            summary = metadata.get('description') or metadata.get('summary') or create_excerpt(note_data.content)
            cover = select_cover(metadata)
            tags = normalize_tags(metadata.get('tags'))
            published = metadata.get('date')
        except Exception:
            with open(md_path, 'r', encoding='utf-8') as f:
                summary = create_excerpt(f.read())
    elif os.path.exists(html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            summary = create_excerpt(f.read())
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
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# 自定义清洗文件名，去掉路径、非法字符
def sanitize_filename(filename: str) -> str:
    # 1. 只取 basename，去除任何路径
    name = os.path.basename(filename)
    # 2. 非字母数字、下划线、连字符、点的都替换为下划线
    return re.sub(r'[^A-Za-z0-9._-]', '_', name)

@edu_bp.route('/upload', methods=['POST'])
@login_required
def upload_note():
    # 权限检查
    if not (current_user.is_admin or current_user.id == 1):
        abort(403)

    # 确保 field 存在
    if 'note_file' not in request.files:
        flash("未选择文件", "error")
        return redirect(url_for('edu.list_notes'))

    file = request.files['note_file']
    # 用户没选文件
    if file.filename == '':
        flash("未选择文件", "error")
        return redirect(url_for('edu.list_notes'))

    # 后缀校验
    if not allowed_file(file.filename):
        flash("只能上传 .md 或 .html 文件", "error")
        return redirect(url_for('edu.list_notes'))

    # 清洗文件名，防止目录穿越和非法字符
    filename = sanitize_filename(file.filename)
    save_path = os.path.join(os.path.dirname(__file__), 'notes', filename)

    # 保存到 NOTES_DIR
    file.save(save_path)

    flash("上传成功！", "success")
    return redirect(url_for('edu.list_notes'))

@edu_bp.route('/')
def list_notes():
    os.makedirs(NOTES_DIR, exist_ok=True)

    """分页列出所有文档，按最后修改时间倒序。"""
    try:
        page = int(request.args.get('page', 1))
    except ValueError:
        page = 1

    # 读取所有笔记
    all_notes = []
    if not os.path.exists(NOTES_DIR):
        abort(500, description=f"Notes directory not found: {NOTES_DIR}")
    for filename in os.listdir(NOTES_DIR):
        if filename.endswith(('.md', '.html')):
            filepath = os.path.join(NOTES_DIR, filename)
            lm = datetime.fromtimestamp(os.path.getmtime(filepath))
            slug, ext = filename.rsplit('.', 1)
            all_notes.append({'slug': slug, 'last_modified': lm})
    all_notes.sort(key=lambda x: x['last_modified'], reverse=True)
    random_slug = random.choice(all_notes)['slug'] if all_notes else None

    # 计算分页
    total = len(all_notes)
    total_pages = ceil(total / PER_PAGE) if total else 1
    page = max(1, min(page, total_pages))
    start = (page - 1) * PER_PAGE
    end = start + PER_PAGE
    page_entries = all_notes[start:end]
    card_items = []
    for entry in page_entries:
        card = load_note_card(entry['slug'], entry['last_modified'])
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
        card['url'] = url_for('edu.show_note', slug=entry['slug'])
        card_items.append(card)

    can_edit = current_user.is_authenticated and (getattr(current_user, 'is_admin', False) or current_user.id == 1)
    random_url = url_for('edu.show_note', slug=random_slug) if (random_slug and not can_edit) else None

    return render_template(
        'edu_index.html',
        title="Education Notes",
        cards=card_items,
        page=page,
        total_pages=total_pages,
        can_edit=can_edit,
        random_url=random_url
    )


@edu_bp.route('/<slug>')
def show_note(slug):
    """显示单个笔记，支持 .md 和 .html 文件"""
    md_path = os.path.join(NOTES_DIR, f"{slug}.md")
    html_path = os.path.join(NOTES_DIR, f"{slug}.html")

    if os.path.exists(md_path):
        note_data = frontmatter.load(md_path)
        title = note_data.get('title', 'Untitled')
        content_md = note_data.content
        metadata = note_data.metadata or {}
        note_summary = metadata.get('description') or metadata.get('summary')
        content_html = markdown.markdown(
            content_md,
            extensions=MARKDOWN_EXTENSIONS,
            extension_configs=MARKDOWN_EXTENSION_CONFIGS
        )
        return render_template(
            'edu_note.html',
            title=title,
            note_title=title,
            note_summary=note_summary or '',
            note_content=content_html,
            note_date=note_data.get('date', ''),
            frontmatter=metadata
        )

    elif os.path.exists(html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        return render_template(
            'edu_note.html',
            title=slug,
            note_title=slug,
            note_summary='',
            note_content=html_content,
            note_date='',
            frontmatter={}
        )

    else:
        abort(404)






















@edu_bp.route('/manage_notes')
@login_required
def manage_notes():
    """管理员笔记管理页面：列出所有 Markdown 和 HTML 文件"""
    if not (current_user.is_admin or current_user.id == 1):
        flash("无权限访问笔记管理页面", "error")
        return redirect(url_for('index.home'))

    if not os.path.exists(NOTES_DIR):
        abort(500, description=f"Notes directory not found: {NOTES_DIR}")

    notes = []
    for filename in os.listdir(NOTES_DIR):
        if filename.endswith(('.md', '.html')):
            filepath = os.path.join(NOTES_DIR, filename)
            last_modified = datetime.fromtimestamp(os.path.getmtime(filepath))
            slug, ext = filename.rsplit('.', 1)
            notes.append({
                'filename': filename,
                'slug': slug,
                'ext': ext,
                'last_modified': last_modified
            })

    notes.sort(key=lambda x: x['last_modified'], reverse=True)
    return render_template('edu_manage_notes.html', notes=notes)

@edu_bp.route('/new', methods=['POST'])
@login_required
def new_note():
    if not (current_user.is_admin or current_user.id == 1):
        abort(403)
    # 生成新文件名，格式例如 note_20250408123045.md %H:%M:%S
    timestamp = datetime.now().strftime('%Y%m%d')
    filename = f"note_{timestamp}.md"
    filepath = os.path.join(NOTES_DIR, filename)
    
    # 定义默认 frontmatter 与内容 %H:%M:%S
    default_frontmatter = {
        'title': 'New Note',
        'date': datetime.now().strftime("%Y-%m-%d"),
        'tags': ['study', 'note'],
        'cover': 'https://images.unsplash.com/photo-1498050108023-c5249f4df085',
        'summary': '记录你的学习收获……',
        'status': 'draft'
    }
    default_content = "在此处编辑内容..."
    note_data = frontmatter.Post(default_content, **default_frontmatter)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(frontmatter.dumps(note_data))
   
    slug = filename.rsplit('.', 1)[0]
    flash("新文档已创建，请完善内容。", "success")
    return redirect(url_for('edu.edit_note', slug=slug))


@edu_bp.route('/<slug>/edit', methods=['GET', 'POST'])
@login_required
def edit_note(slug):
    # 定位文件
    filepath = None
    for ext in ('md', 'html'):
        p = os.path.join(NOTES_DIR, f"{slug}.{ext}")
        if os.path.exists(p):
            filepath = p
            break
    if filepath is None:
        abort(404, description="Note not found")

    if request.method == 'POST':
        # 仅保存正文内容
        new_content = request.form.get('content', '')
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        flash("内容已保存", "success")
        return redirect(url_for('edu.show_note', slug=slug))

    # GET：读取内容并渲染编辑页面
    with open(filepath, 'r', encoding='utf-8') as f:
        file_text = f.read()
    return render_template('edu_edit.html', slug=slug, content=file_text)


@edu_bp.route('/<slug>/rename', methods=['POST'])
@login_required
def rename_note(slug):
    if not (current_user.is_admin or current_user.id == 1):
        abort(403)

    new_slug = request.form.get('new_slug', '').strip()
    if not new_slug:
        flash("新名称不能为空", "error")
        return redirect(url_for('edu.edit_note', slug=slug))

    # 查找并重命名
    for ext in ('md', 'html'):
        old_path = os.path.join(NOTES_DIR, f"{slug}.{ext}")
        if os.path.exists(old_path):
            new_path = os.path.join(NOTES_DIR, f"{new_slug}.{ext}")
            if os.path.exists(new_path):
                flash("重命名失败：目标文件已存在", "error")
                return redirect(url_for('edu.edit_note', slug=slug))
            os.rename(old_path, new_path)
            flash("重命名成功", "success")
            return redirect(url_for('edu.edit_note', slug=new_slug))

    abort(404, description="Note not found")


@edu_bp.route('/<slug>/delete', methods=['POST'])
@login_required
def delete_note(slug):
    if not (current_user.is_admin or current_user.id == 1):
        abort(403)

    # 删除文件
    for ext in ('md', 'html'):
        path = os.path.join(NOTES_DIR, f"{slug}.{ext}")
        if os.path.exists(path):
            os.remove(path)
            flash("文档已删除", "success")
            return redirect(url_for('edu.list_notes'))

    abort(404, description="Note not found")
