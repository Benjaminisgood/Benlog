import os
from flask import request, redirect, flash, render_template, abort, current_app, url_for
import frontmatter, markdown
from datetime import datetime
from . import blog_bp

# POSTS_DIR 存放 blog 模块的 Markdown 文件
POSTS_DIR = os.path.join(os.path.dirname(__file__), 'posts')

@blog_bp.route('/')
def list_posts():
    """列出所有文章，显示文件名和最后修改时间（由近到远排序）。"""
    if not os.path.exists(POSTS_DIR):
        abort(500, description=f"POSTS_DIR 不存在：{POSTS_DIR}")

    posts = []
    for filename in os.listdir(POSTS_DIR):
        if filename.endswith('.md'):
            filepath = os.path.join(POSTS_DIR, filename)
            # 获取文件最后修改时间
            last_modified_timestamp = os.path.getmtime(filepath)
            last_modified_time = datetime.fromtimestamp(last_modified_timestamp)
            # 使用文件名（不含扩展名）作为 slug
            slug = filename.rsplit('.', 1)[0]
            posts.append({
                'filename': filename,
                'slug': slug,
                'last_modified': last_modified_time
            })
    # 按最后修改时间由近到远排序
    posts.sort(key=lambda x: x['last_modified'], reverse=True)
    return render_template('blog_index.html', title="Blog", posts=posts)


@blog_bp.route('/<slug>')
def show_post(slug):
    """显示单个文章，使用 slug（文件名去除 .md 部分）标识。"""
    filename = f"{slug}.md"
    filepath = os.path.join(POSTS_DIR, filename)
    if not os.path.exists(filepath):
        abort(404)
    # 加载并解析 Markdown 文件（包括 frontmatter 数据）
    post_data = frontmatter.load(filepath)
    title = post_data.get('title', 'Untitled')
    content_md = post_data.content  # Markdown 内容（不包含 frontmatter）
    # 将 Markdown 转为 HTML
    content_html = markdown.markdown(
        content_md,
        extensions=[
            'extra',                  # Markdown Extra 增强功能
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
    return render_template(
        'blog_post.html',
        title=title,
        post_title=title,
        post_content=content_html,
        post_date=post_data.get('date', ''),
        frontmatter=post_data.metadata
    )


@blog_bp.route('/new', methods=['POST'])
def new_post():
    """处理新建文章请求：验证密码并创建一个默认的 Markdown 文件，然后跳转到编辑页面"""
    password = request.form.get('password')
    # 从 app.config 中获取认证密码（如未配置则默认 'mysecret'）
    expected_password = current_app.config.get('DOC_CREATION_PASSWORD', 'mysecret')
    if password != expected_password:
        flash("密码错误，无法创建新文章。", "error")
        return redirect(url_for('blog.list_posts'))
    
    # 生成新文件名，采用时间戳确保唯一性
    timestamp = datetime.now().strftime('%Y%m%d')
    filename = f"post_{timestamp}.md"
    filepath = os.path.join(POSTS_DIR, filename)
    
    # 定义默认 frontmatter 与内容
    default_frontmatter = {
        'title': 'New Post',
        'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    default_content = "在此处编辑内容..."
    post_data = frontmatter.Post(default_content, **default_frontmatter)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(frontmatter.dumps(post_data))
    
    slug = filename.rsplit('.', 1)[0]
    flash("新文章已创建，请完善内容。", "success")
    return redirect(url_for('blog.edit_post', slug=slug))


@blog_bp.route('/<slug>/edit_auth', methods=['POST'])
def edit_auth(slug):
    """验证编辑前的密码。正确则重定向到实际编辑页面"""
    password = request.form.get('password')
    expected_password = current_app.config.get('DOC_CREATION_PASSWORD', 'mysecret')
    if password != expected_password:
        flash("密码错误，无法编辑文章。", "error")
        return redirect(url_for('blog.list_posts'))
    return redirect(url_for('blog.edit_post', slug=slug))


@blog_bp.route('/<slug>/edit', methods=['GET', 'POST'])
def edit_post(slug):
    """编辑指定文章，直接读取和保存整个 .md 文件的内容"""
    filename = f"{slug}.md"
    filepath = os.path.join(POSTS_DIR, filename)
    if not os.path.exists(filepath):
        abort(404)
    
    if request.method == 'POST':
        # 检查是否点击了删除按钮
        if 'delete' in request.form:
            try:
                os.remove(filepath)
            except Exception as e:
                flash("删除失败：" + str(e), "error")
                return redirect(url_for('blog.show_post', slug=slug))
            flash("文章已成功删除。", "success")
            # 删除后重定向到博客首页或其他合适的页面
            return redirect(url_for('blog.list_posts'))
        
        # 如果不是删除操作，则按更新处理
        new_content = request.form.get('content', '')
        new_slug = request.form.get('new_slug', '').strip() or slug

        # 如果新名称不等于原来的名称，则执行重命名逻辑
        if new_slug != slug:
            new_filename = f"{new_slug}.md"
            new_filepath = os.path.join(POSTS_DIR, new_filename)
            # 如果新名称已经存在则提示错误
            if os.path.exists(new_filepath):
                flash("重命名失败：文档名称已存在。", "error")
                return redirect(url_for('edu.edit_note', slug=slug))
            try:
                os.rename(filepath, new_filepath)
            except Exception as e:
                flash("重命名失败：" + str(e), "error")
                return redirect(url_for('edu.edit_note', slug=slug))
            # 更新文件路径与 slug 为新名称
            filepath = new_filepath
            slug = new_slug

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        flash("文章已成功更新。", "success")
        return redirect(url_for('blog.show_post', slug=slug))
    
    with open(filepath, 'r', encoding='utf-8') as f:
        file_text = f.read()
    
    return render_template('blog_edit.html', content=file_text, slug=slug)
