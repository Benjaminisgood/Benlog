import os
from flask import request, redirect, flash, render_template, abort, current_app, url_for
import frontmatter, markdown
from datetime import datetime
from . import blog_bp
from flask_login import login_required, current_user

# POSTS_DIR 存放 blog 模块的 Markdown 文件
POSTS_DIR = os.path.join(os.path.dirname(__file__), 'posts')

@blog_bp.route('/')
def list_posts():
    """列出所有文章，显示文件名和最后修改时间（由近到远排序）。"""
    if not os.path.exists(POSTS_DIR):
        abort(500, description=f"POSTS_DIR 不存在：{POSTS_DIR}")

    posts = []
    for filename in os.listdir(POSTS_DIR):
        if filename.endswith(('.md', '.html')):
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
    """支持显示 .md 或 .html 文件的文章"""
    md_path = os.path.join(POSTS_DIR, f"{slug}.md")
    html_path = os.path.join(POSTS_DIR, f"{slug}.html")

    if os.path.exists(md_path):
        # 解析 Markdown 文件
        post_data = frontmatter.load(md_path)
        content_md = post_data.content
        content_html = markdown.markdown(
            content_md,
            extensions=[
                'extra',
                'pymdownx.tilde',
                'pymdownx.tasklist',
                'pymdownx.arithmatex'
            ],
            extension_configs={
                'pymdownx.arithmatex': {'generic': True}
            }
        )
        return render_template(
            'blog_post.html',
            post_content=content_html,
            post_date=post_data.get('date', ''),
            frontmatter=post_data.metadata
        )

    elif os.path.exists(html_path):
        # 直接读取 .html 文件内容并原样渲染
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        return render_template(
            'blog_post.html',
            post_content=html_content,
            post_date='',  # 或者你可以用某种方式提取日期
            frontmatter={}
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

    if not os.path.exists(POSTS_DIR):
        abort(500, description=f"Posts directory not found: {POSTS_DIR}")

    posts = []
    for filename in os.listdir(POSTS_DIR):
        if filename.endswith(('.md', '.html')):  # ✅ 支持两种后缀
            filepath = os.path.join(POSTS_DIR, filename)
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
    filepath = os.path.join(POSTS_DIR, filename)
    
    # 定义默认 frontmatter 与内容 %H:%M:%S
    default_frontmatter = {
        'title': 'New Post',
        'date': datetime.now().strftime("%Y-%m-%d")
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
    if not (current_user.is_admin or current_user.id == 1):
        abort(403)

    # 自动检测支持的文件扩展名
    for ext in ['.md', '.html']:
        filename = f"{slug}{ext}"
        filepath = os.path.join(POSTS_DIR, filename)
        if os.path.exists(filepath):
            file_ext = ext
            break
    else:
        abort(404, description="未找到对应的 .md 或 .html 文件")

    # POST 提交编辑内容
    if request.method == 'POST':
        # 删除逻辑（适用于所有扩展名）
        if 'delete' in request.form:
            os.remove(filepath)
            flash("文件已删除", "success")
            return redirect(url_for('blog.list_posts'))

        # 更新内容
        new_content = request.form.get('content', '')
        new_slug = request.form.get('new_slug', '').strip() or slug
        new_filename = f"{new_slug}{file_ext}"
        new_filepath = os.path.join(POSTS_DIR, new_filename)

        # 若重命名了
        if new_slug != slug:
            if os.path.exists(new_filepath):
                flash("重命名失败：文件已存在", "error")
                return redirect(url_for('blog.edit_post', slug=slug))
            os.rename(filepath, new_filepath)
            filepath = new_filepath
            slug = new_slug

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)

        flash("保存成功", "success")
        return redirect(url_for('blog.show_post', slug=slug))

    # GET：读取文件内容用于编辑
    with open(filepath, 'r', encoding='utf-8') as f:
        file_text = f.read()

    return render_template('blog_edit.html', content=file_text, slug=slug)