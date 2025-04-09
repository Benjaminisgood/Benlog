import os
from flask import request, redirect, flash, render_template, abort, current_app, abort, url_for
import frontmatter, markdown
from datetime import datetime
from . import edu_bp

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


@edu_bp.route('/new', methods=['POST'])
def new_note():
    """处理新建文档请求：验证密码并创建一个默认的 Markdown 文件，然后跳转到编辑页面"""
    password = request.form.get('password')
    # 获取认证密码，可以配置在 app.config 中，也可以直接写死（这里示例使用 app.config）
    expected_password = current_app.config.get('DOC_CREATION_PASSWORD', 'mysecret')
    if password != expected_password:
        flash("密码错误，无法创建新文档。", "error")
        return redirect(url_for('edu.list_notes'))
    
    # 生成新文件名，格式例如 note_20250408123045.md
    timestamp = datetime.now().strftime('%Y%m%d')
    filename = f"note_{timestamp}.md"
    filepath = os.path.join(NOTES_DIR, filename)
    
    # 定义默认 frontmatter 与内容
    default_frontmatter = {
        'title': 'New Note',
        'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    default_content = "在此处编辑内容..."
    note_data = frontmatter.Post(default_content, **default_frontmatter)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(frontmatter.dumps(note_data))
   
    slug = filename.rsplit('.', 1)[0]
    flash("新文档已创建，请完善内容。", "success")
    return redirect(url_for('edu.edit_note', slug=slug))

@edu_bp.route('/<slug>/edit_auth', methods=['POST'])
def edit_auth(slug):
    """验证编辑前的密码。正确则重定向到实际编辑页面"""
    password = request.form.get('password')
    expected_password = current_app.config.get('DOC_CREATION_PASSWORD', 'mysecret')
    if password != expected_password:
        flash("密码错误，无法编辑文档。", "error")
        return redirect(url_for('edu.list_notes'))
    return redirect(url_for('edu.edit_note', slug=slug))

@edu_bp.route('/<slug>/edit', methods=['GET', 'POST'])
def edit_note(slug):
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
