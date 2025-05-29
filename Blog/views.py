import os, math
import re
from flask import request, redirect, flash, render_template, abort, current_app, url_for
import frontmatter, markdown
from datetime import datetime
from . import blog_bp
from flask_login import login_required, current_user

# POSTS_DIR 存放 blog 模块的 Markdown 文件
POSTS_DIR = os.path.join(os.path.dirname(__file__), 'posts')
ALLOWED_EXTENSIONS = {'md', 'html'}
PER_PAGE = 10  # 每页显示条数

def get_all_posts():
    """返回按时间倒序排列的所有文章元信息列表"""
    posts = []
    if not os.path.exists(POSTS_DIR):
        abort(500, description=f"POSTS_DIR 不存在：{POSTS_DIR}")
    for filename in os.listdir(POSTS_DIR):
        if filename.endswith(('.md', '.html')):
            filepath = os.path.join(POSTS_DIR, filename)
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
    save_path = os.path.join(POSTS_DIR, filename)

    # 保存文件
    file.save(save_path)

    flash("上传成功！", "success")
    return redirect(url_for('blog.list_posts'))

@blog_bp.route('/')
def list_posts():
    # 1. 获取 page 参数
    try:
        page = int(request.args.get('page', 1))
    except ValueError:
        page = 1

    # 2. 拿到所有文章
    all_posts = get_all_posts()  # 之前定义的函数

    # 3. 计算总页数，并确保 page 在合理范围
    total = len(all_posts)
    total_pages = math.ceil(total / PER_PAGE) if total else 1
    page = max(1, min(page, total_pages))

    # 4. 切片出当前页的文章
    start = (page - 1) * PER_PAGE
    end   = start + PER_PAGE
    page_posts = all_posts[start:end]

    # 5. 渲染，传入 page 和 total_pages
    return render_template(
        'blog_index.html',
        title="Blog",
        posts=page_posts,
        page=page,
        total_pages=total_pages
    )

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
    # 定位文件
    filepath = None
    for ext in ('md', 'html'):
        p = os.path.join(POSTS_DIR, f"{slug}.{ext}")
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
    for ext in ('md', 'html'):
        old_path = os.path.join(POSTS_DIR, f"{slug}.{ext}")
        if os.path.exists(old_path):
            new_path = os.path.join(POSTS_DIR, f"{new_slug}.{ext}")
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
    for ext in ('md', 'html'):
        path = os.path.join(POSTS_DIR, f"{slug}.{ext}")
        if os.path.exists(path):
            os.remove(path)
            flash("文章已删除", "success")
            return redirect(url_for('blog.manage_posts'))
    abort(404, description="Post not found")