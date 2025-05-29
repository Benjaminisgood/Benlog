import os
from flask import request, redirect, flash, render_template, abort, current_app, url_for
import frontmatter, markdown
from datetime import datetime
from . import edu_bp
from flask_login import login_required, current_user
import re

NOTES_DIR = os.path.join(os.path.dirname(__file__), 'notes')
# 允许的后缀
ALLOWED_EXTENSIONS = {'md', 'html'}
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
    """列出所有文章，显示文件名和最后修改时间（由近到远排序）。"""
    #NOTES_DIR = os.path.join(current_app.static_folder, 'notes/notes')
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
    # 按最后修改时间由近到远排序
    notes.sort(key=lambda x: x['last_modified'], reverse=True)
    return render_template('edu_index.html', title="Education Notes", notes=notes)

@edu_bp.route('/<slug>')
def show_note(slug):
    """显示单个笔记，支持 .md 和 .html 文件"""
    md_path = os.path.join(NOTES_DIR, f"{slug}.md")
    html_path = os.path.join(NOTES_DIR, f"{slug}.html")

    if os.path.exists(md_path):
        note_data = frontmatter.load(md_path)
        title = note_data.get('title', 'Untitled')
        content_md = note_data.content
        content_html = markdown.markdown(
            content_md,
            extensions=['extra', 'pymdownx.tilde', 'pymdownx.tasklist', 'pymdownx.arithmatex'],
            extension_configs={'pymdownx.arithmatex': {'generic': True}}
        )
        return render_template('edu_note.html', title=title, note_title=title, note_content=content_html, note_date=note_data.get('date', ''), frontmatter=note_data.metadata)

    elif os.path.exists(html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        return render_template('edu_note.html', title=slug, note_title=slug, note_content=html_content, note_date='', frontmatter={})

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
        'date': datetime.now().strftime("%Y-%m-%d")
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