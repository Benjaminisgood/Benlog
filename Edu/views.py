import os
from flask import request, redirect, flash, render_template, abort, current_app, abort, url_for
import frontmatter, markdown
from datetime import datetime
from . import edu_bp
from flask_login import login_required, current_user

NOTES_DIR = os.path.join(os.path.dirname(__file__), 'notes')

@edu_bp.route('/')
def list_notes():
    """列出所有文章，显示文件名和最后修改时间（由近到远排序）。"""
    #NOTES_DIR = os.path.join(current_app.static_folder, 'notes/notes')
    if not os.path.exists(NOTES_DIR):
        abort(500, description=f"Notes directory not found: {NOTES_DIR}")
    
    notes = []
    for filename in os.listdir(NOTES_DIR):
        if filename.endswith('.md'):
            filepath = os.path.join(NOTES_DIR, filename)
            # 获取文件最后修改时间
            last_modified_timestamp = os.path.getmtime(filepath)
            last_modified_time = datetime.fromtimestamp(last_modified_timestamp)
            # 使用文件名（不含扩展名）作为 slug
            slug = filename.rsplit('.', 1)[0]
            notes.append({
                'filename': filename,
                'slug': slug,
                'last_modified': last_modified_time
            })
    # 按最后修改时间由近到远排序
    notes.sort(key=lambda x: x['last_modified'], reverse=True)
    return render_template('edu_index.html', title="Education Notes", notes=notes)

@edu_bp.route('/<slug>')
def show_note(slug):
    """显示单个笔记，使用 slug（文件名去除 .md 部分）标识。"""
    #NOTES_DIR = os.path.join(current_app.static_folder, 'notes/notes')

    filename = f"{slug}.md"
    filepath = os.path.join(NOTES_DIR, filename)
    if not os.path.exists(filepath):
        abort(404)
    # 加载并解析 Markdown 文件（包括 frontmatter 数据）
    note_data = frontmatter.load(filepath)
    title = note_data.get('title', 'Untitled')
    content_md = note_data.content  # Markdown 内容（不包含 frontmatter）
    # 将 Markdown 转为 HTML
    content_html = markdown.markdown(
    content_md,
    extensions=[
        'extra',                  # Markdown Extra 增强功能（表格、脚注、定义列表、缩写、属性列表）
        'pymdownx.tilde',         # 删除线支持：使用 ~~删除线~~
        'pymdownx.tasklist',      # 任务列表支持：- [ ] 和 - [x]
        'pymdownx.arithmatex'     # 数学公式支持（支持 $...$ 和 $$...$$）
    ],
    extension_configs={
        'pymdownx.arithmatex': {
            'generic': True      # 开启通用模式，方便 MathJax 渲染
        }
    }
)

    # 将 frontmatter 中所有数据传递给模板
    return render_template(
        'edu_note.html',
        title=title,
        note_title=title,
        note_content=content_html,
        note_date=note_data.get('date', ''),
        frontmatter=note_data.metadata
    )






















@edu_bp.route('/manage_notes')
@login_required
def manage_notes():
    """管理员笔记管理页面：列出所有 Markdown 文件"""
    if not (current_user.is_admin or current_user.id == 1):
        flash("无权限访问笔记管理页面", "error")
        return redirect(url_for('index.home'))

    if not os.path.exists(NOTES_DIR):
        abort(500, description=f"Notes directory not found: {NOTES_DIR}")
    
    notes = []
    for filename in os.listdir(NOTES_DIR):
        if filename.endswith('.md'):
            filepath = os.path.join(NOTES_DIR, filename)
            last_modified = datetime.fromtimestamp(os.path.getmtime(filepath))
            slug = filename.rsplit('.', 1)[0]
            notes.append({
                'filename': filename,
                'slug': slug,
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
    if not (current_user.is_admin or current_user.id == 1):
        abort(403)
    """编辑指定笔记，直接读取和保存整个 .md 文件的内容"""
    filename = f"{slug}.md"
    filepath = os.path.join(NOTES_DIR, filename)
    if not os.path.exists(filepath):
        abort(404)
    
    if request.method == 'POST':
        # 检查是否点击了删除按钮
        if 'delete' in request.form:
            try:
                os.remove(filepath)
            except Exception as e:
                flash("删除失败：" + str(e), "error")
                return redirect(url_for('edu.show_note', slug=slug))
            flash("文档已成功删除。", "success")
            # 删除后重定向到首页或其他适合的页面
            return redirect(url_for('edu.list_notes'))
        
        # 如果不是删除操作，执行更新（包括重命名）流程
        new_content = request.form.get('content', '')
        # 获取用户提交的新文档名称，若为空则保持当前名称
        new_slug = request.form.get('new_slug', '').strip() or slug
        
        # 若新名称与原名称不同，执行重命名操作
        if new_slug != slug:
            new_filename = f"{new_slug}.md"
            new_filepath = os.path.join(NOTES_DIR, new_filename)
            if os.path.exists(new_filepath):
                flash("重命名失败：文档名称已存在。", "error")
                return redirect(url_for('edu.edit_note', slug=slug))
            try:
                os.rename(filepath, new_filepath)
            except Exception as e:
                flash("重命名失败：" + str(e), "error")
                return redirect(url_for('edu.edit_note', slug=slug))
            # 更新文件路径和 slug 为新值
            filepath = new_filepath
            slug = new_slug

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        flash("文档已成功更新。", "success")
        return redirect(url_for('edu.show_note', slug=slug))
    
    # GET 请求：读取整个 Markdown 文件内容
    with open(filepath, 'r', encoding='utf-8') as f:
        file_text = f.read()
    
    return render_template('edu_edit.html', content=file_text, slug=slug)
