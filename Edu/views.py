import os
import random
from flask import request, redirect, flash, render_template, abort, current_app, url_for, jsonify
import frontmatter
from datetime import datetime
from . import edu_bp
from flask_login import login_required, current_user
import re
from math import ceil
from Benlog.render import clean_html, is_draft, render_markdown
from Benlog.security import clean_slug, editor_required, safe_slug

def _notes_dir() -> str:
    return current_app.config.get('EDU_NOTES_DIR') or os.path.join(
        current_app.instance_path,
        'Edu',
        'notes'
    )

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


def _can_edit():
    return current_user.is_authenticated and (getattr(current_user, 'is_admin', False) or current_user.id == 1)


def _locate_note(slug):
    slug = safe_slug(slug)
    if not slug:
        abort(404)
    for ext in ('md', 'html'):
        path = os.path.join(_notes_dir(), f'{slug}.{ext}')
        if os.path.isfile(path):
            return path, ext
    return None, None


def _split_note(path, ext):
    with open(path, 'r', encoding='utf-8') as handle:
        raw = handle.read()
    if ext != 'md':
        return {}, raw, raw
    try:
        parsed = frontmatter.loads(raw)
    except Exception:
        return {}, raw, raw
    return dict(parsed.metadata or {}), parsed.content or '', raw


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
    md_path = os.path.join(_notes_dir(), f"{slug}.md")
    html_path = os.path.join(_notes_dir(), f"{slug}.html")

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
    save_path = os.path.join(_notes_dir(), filename)

    # 保存到笔记目录
    file.save(save_path)

    flash("上传成功！", "success")
    return redirect(url_for('edu.list_notes'))

@edu_bp.route('/')
def list_notes():
    """分页列出所有文档，支持顺序、倒序与随机排序。"""
    os.makedirs(_notes_dir(), exist_ok=True)
    try:
        page = int(request.args.get('page', 1))
    except ValueError:
        page = 1

    order = request.args.get('order', 'desc').lower()
    if order not in ('asc', 'desc', 'random'):
        order = 'desc'

    # 读取所有笔记
    all_notes = []
    if not os.path.exists(_notes_dir()):
        abort(500, description=f"Notes directory not found: {_notes_dir()}")
    for filename in os.listdir(_notes_dir()):
        if filename.endswith(('.md', '.html')):
            filepath = os.path.join(_notes_dir(), filename)
            lm = datetime.fromtimestamp(os.path.getmtime(filepath))
            slug, ext = filename.rsplit('.', 1)
            if not safe_slug(slug):
                continue
            metadata = {}
            if ext == 'md':
                try:
                    metadata = frontmatter.load(filepath).metadata or {}
                except Exception:
                    metadata = {}
            if is_draft(metadata) and not _can_edit():
                continue
            all_notes.append({'slug': slug, 'last_modified': lm})
    if order == 'asc':
        all_notes.sort(key=lambda x: x['last_modified'])
    elif order == 'random':
        random.shuffle(all_notes)
    else:
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
        random_url=random_url,
        current_order=order
    )


@edu_bp.route('/<slug>')
def show_note(slug):
    """显示单个笔记，支持 .md 和 .html 文件"""
    path, ext = _locate_note(slug)
    if not path:
        abort(404)

    metadata, body, raw = _split_note(path, ext)
    if is_draft(metadata) and not _can_edit():
        abort(404)

    if ext == 'md':
        title = metadata.get('title') or slug
        note_summary = metadata.get('description') or metadata.get('summary') or ''
        return render_template(
            'edu_note.html',
            title=title,
            note_title=title,
            note_summary=note_summary,
            note_content=render_markdown(body),
            note_date=metadata.get('date', ''),
            frontmatter=metadata,
            needs_math=True,
        )

    return render_template(
        'edu_note.html',
        title=slug,
        note_title=slug,
        note_summary='',
        note_content=clean_html(raw),
        note_date='',
        frontmatter={},
        needs_math=True,
    )






















@edu_bp.route('/manage_notes')
@login_required
def manage_notes():
    """管理员笔记管理页面：列出所有 Markdown 和 HTML 文件"""
    if not (current_user.is_admin or current_user.id == 1):
        flash("无权限访问笔记管理页面", "error")
        return redirect(url_for('index.home'))

    if not os.path.exists(_notes_dir()):
        abort(500, description=f"Notes directory not found: {_notes_dir()}")

    notes = []
    for filename in os.listdir(_notes_dir()):
        if filename.endswith(('.md', '.html')):
            filepath = os.path.join(_notes_dir(), filename)
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
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    filename = f"note_{timestamp}.md"
    filepath = os.path.join(_notes_dir(), filename)
    
    default_frontmatter = {
        'title': '新笔记',
        'date': datetime.now().strftime("%Y-%m-%d"),
        'tags': ['study'],
        'summary': '',
        'status': 'published'
    }
    default_content = "在这里写 Markdown。"
    note_data = frontmatter.Post(default_content, **default_frontmatter)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(frontmatter.dumps(note_data))
   
    slug = filename.rsplit('.', 1)[0]
    flash("新文档已创建，请完善内容。", "success")
    return redirect(url_for('edu.edit_note', slug=slug))


@edu_bp.route('/preview', methods=['POST'])
@editor_required
def preview_markdown():
    return jsonify({'html': str(render_markdown(request.form.get('content', '')))})


@edu_bp.route('/<slug>/edit', methods=['GET', 'POST'])
@editor_required
def edit_note(slug):
    path, ext = _locate_note(slug)
    if not path:
        abort(404, description="Note not found")

    metadata, body, raw = _split_note(path, ext)
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
            written = frontmatter.dumps(frontmatter.Post(request.form.get('content', ''), **metadata))
        else:
            written = request.form.get('content', '')
        with open(path, 'w', encoding='utf-8') as handle:
            handle.write(written)
        flash("内容已保存", "success")
        return redirect(url_for('edu.show_note', slug=slug))

    tags = metadata.get('tags') or []
    tags_text = ', '.join(str(tag) for tag in tags) if isinstance(tags, (list, tuple)) else str(tags)
    return render_template(
        'edu_edit.html',
        slug=slug,
        is_markdown=ext == 'md',
        title_value=metadata.get('title') or slug,
        summary_value=metadata.get('summary') or metadata.get('description') or '',
        tags_value=tags_text,
        cover_value=metadata.get('cover') or '',
        status_value='draft' if is_draft(metadata) else 'published',
        content=body if ext == 'md' else raw,
        preview_url=url_for('edu.preview_markdown'),
    )


@edu_bp.route('/<slug>/rename', methods=['POST'])
@login_required
def rename_note(slug):
    if not (current_user.is_admin or current_user.id == 1):
        abort(403)

    new_slug = clean_slug(request.form.get('new_slug', ''))
    if not new_slug:
        flash("新名称无效。只保留字母、数字、中文、点、下划线和连字符。", "error")
        return redirect(url_for('edu.edit_note', slug=slug))

    # 查找并重命名
    for ext in ('md', 'html'):
        old_path = os.path.join(_notes_dir(), f"{slug}.{ext}")
        if os.path.exists(old_path):
            new_path = os.path.join(_notes_dir(), f"{new_slug}.{ext}")
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
        path = os.path.join(_notes_dir(), f"{slug}.{ext}")
        if os.path.exists(path):
            os.remove(path)
            flash("文档已删除", "success")
            return redirect(url_for('edu.list_notes'))

    abort(404, description="Note not found")
