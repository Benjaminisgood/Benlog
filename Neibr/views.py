# Neibr/views.py
from flask import render_template, request, redirect, url_for, flash # type: ignore
from . import neibr_bp, db  # 从 Neibr/__init__.py 导入蓝图和本地数据库实例
from flask_login import login_required, current_user, login_user  # type: ignore # Flask-Login 用于用户会话管理
from .models import User, Post  # 从本地 models.py 导入 User 和 Post 模型
from werkzeug.security import generate_password_hash, check_password_hash  # type: ignore # 用于密码加密和验证
import os
from werkzeug.utils import secure_filename # type: ignore
import yaml
from datetime import datetime


# 项目根目录下的 static/neibr 路径
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
UPLOAD_BASE_PATH = os.path.join(BASE_DIR, 'Benlog', 'static', 'neibr')  # static/neibr
def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'webm', 'mp3', 'wav', 'nef','mov','MOV'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@neibr_bp.route('/')
def index():
    """
    Neibr 模块的主页，展示最新的 10 个帖子和随机选择的 10 个帖子。
    返回值：渲染 neibr_index.html 模板，传入帖子数据。
    """
    if not current_user.is_authenticated:
        flash('请先登录以查看内容。', 'login')
        return redirect(url_for('neibr.login'))

    latest_posts = Post.query.filter(
       (Post.is_hidden == False) | (Post.user_id == current_user.id)
    ). order_by(Post.creation_time.desc()).limit(10).all()

    random_posts = Post.query.filter(
       (Post.is_hidden == False) | (Post.user_id == current_user.id)
    ). order_by(db.func.random()).limit(10).all()

    my_posts = Post.query.filter_by(user_id=current_user.id).order_by(Post.creation_time.desc()).all()
    return render_template('neibr_index.html', latest_posts=latest_posts, random_posts=random_posts, my_posts=my_posts)

@neibr_bp.route('/register', methods=['GET', 'POST'])
def register():
    """
    处理用户注册请求，提供注册表单并保存新用户。
    方法：
        GET - 显示注册页面。
        POST - 处理表单提交，验证并创建用户。
    返回值：
        GET - 渲染 register.html 模板。
        POST - 成功则重定向到登录页面，失败则重新渲染表单。
    """
    if request.method == 'POST':
        email = request.form.get('email')
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if not all([email, username, password, confirm_password]):
            flash('所有字段均为必填项。', 'error')
            return render_template('register.html')
        if password != confirm_password:
            flash('密码不匹配。', 'error')
            return render_template('register.html')
        if User.query.filter_by(email=email).first() or User.query.filter_by(username=username).first():
            flash('邮箱或用户名已存在。', 'error')
            return render_template('register.html')

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        user = User(email=email, username=username, password=hashed_password)
        db.session.add(user)
        db.session.commit()
        flash('您的账户已创建！现在可以登录。', 'success')
        return redirect(url_for('neibr.login'))
    
    return render_template('register.html')

@neibr_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    处理用户登录请求，验证凭据并登录用户。
    方法：
        GET - 显示登录页面。
        POST - 验证邮箱和密码，登录成功则重定向到主页。
    返回值：
        GET - 渲染 login.html 模板。
        POST - 成功则重定向到主页，失败则重新渲染登录页面。
    """
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('neibr.index'))
        flash('邮箱或密码错误。', 'error')
    
    return render_template('login.html')

@neibr_bp.route('/create_post', methods=['GET', 'POST'])
@login_required
def create_post():
    """
    允许登录用户创建新帖子，上传多媒体文件并保存到文件系统。
    方法：
        GET - 显示创建帖子页面。
        POST - 处理表单数据，保存帖子和文件到 static/neibr/user_id/post_id。
    返回值：
        GET - 渲染 create_post.html 模板。
        POST - 成功则重定向到帖子详情页。
    """
    if request.method == 'POST':
        title = request.form['title']
        tags = request.form['tags']
        post_text = request.form['post_text']
        files = request.files.getlist('files')

        is_hidden = request.form.get('is_hidden')

        # 创建帖子记录
        post = Post(title=title, tags=tags, user_id=current_user.id)
        post.is_hidden = True if is_hidden else False

        db.session.add(post)
        db.session.flush()  # 获取 post.id

        # 构建帖子文件夹路径：static/neibr/user_id/post_id
        folder_path = os.path.join(UPLOAD_BASE_PATH, str(current_user.id), str(post.id))
        os.makedirs(folder_path, exist_ok=True)

        # 保存上传的媒体文件
        for file in files:
            if file and file.filename:
                filename = secure_filename(file.filename)
                file_path = os.path.join(folder_path, filename)
                file.save(file_path)

        # 保存帖子文案到 post.txt
        with open(os.path.join(folder_path, 'post.txt'), 'w') as f:
            f.write(post_text)

        db.session.commit()
        flash('帖子创建成功。', 'create_post')
        return redirect(url_for('neibr.post_detail', post_id=post.id))
    
    return render_template('create_post.html', title='创建帖子')

@neibr_bp.route('/post/<int:post_id>', methods=['GET', 'POST'])
@login_required
def post_detail(post_id):
    """
    显示特定帖子的详情，包括文案、多媒体文件、导航链接和评论。
    参数：
        post_id - 帖子 ID。
    返回值：
        渲染 post_detail.html 模板，传入帖子数据。
    """
    post = Post.query.get_or_404(post_id)
    user_id = post.user_id

    # 构建帖子文件夹路径：static/neibr/user_id/post_id
    folder_path = os.path.join(UPLOAD_BASE_PATH, str(user_id), str(post_id))

    # 读取帖子文案
    with open(os.path.join(folder_path, 'post.txt'), 'r') as f:
        post_text = f.read()

    # 获取媒体文件列表，排除 post.txt 和 comments.yaml
    media_files = [f for f in os.listdir(folder_path) if f not in ['post.txt', 'comments.yaml']]

    # 获取所有帖子以支持上下导航
    all_posts = Post.query.order_by(Post.creation_time.desc()).all()
    current_index = all_posts.index(post)
    previous_post = all_posts[current_index - 1] if current_index > 0 else None
    next_post = all_posts[current_index + 1] if current_index < len(all_posts) - 1 else None

    # 读取评论
    comments_file = os.path.join(folder_path, 'comments.yaml')
    if os.path.exists(comments_file):
        with open(comments_file, 'r') as f:
            comments = yaml.safe_load(f) or []
    else:
        comments = []

    # 处理评论提交
    if request.method == 'POST':
        new_comment = {
            'username': current_user.username,
            'content': request.form['comment'],
            'timestamp': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        }
        comments.append(new_comment)

        # 写入评论到 YAML 文件
        with open(comments_file, 'w') as f:
            yaml.safe_dump(comments, f)

        flash('评论已提交！', 'success')
        return redirect(url_for('neibr.post_detail', post_id=post_id))

    return render_template(
        'post_detail.html',
        post=post,
        post_text=post_text,
        media_files=media_files,
        comments=comments,
        previous_post=previous_post,
        next_post=next_post
    )
@neibr_bp.route('/edit_post/<int:post_id>', methods=['GET', 'POST'])
@login_required
def edit_post(post_id):
    post = Post.query.get_or_404(post_id)

    # 确保当前用户是帖子作者
    if post.user_id != current_user.id:
        flash('您无权编辑此帖子。', 'error')
        return redirect(url_for('neibr.index'))

    folder_path = os.path.join(UPLOAD_BASE_PATH, str(current_user.id), str(post.id))

    if request.method == 'POST':
        # 更新标题和正文内容
        post.title = request.form['title']
        post.tags = request.form['tags']  # 添加更新标签

        post_text = request.form['post_text']

        is_hidden = request.form.get('is_hidden')
        post.is_hidden = True if is_hidden else False

        # 更新帖子文案
        folder_path = os.path.join(UPLOAD_BASE_PATH, str(current_user.id), str(post.id))
        with open(os.path.join(folder_path, 'post.txt'), 'w') as f:
            f.write(post_text)

        # 处理媒体文件上传
        if 'media_files' in request.files:
            for file in request.files.getlist('media_files'):
                if file and allowed_file(file.filename): # type: ignore
                    filename = secure_filename(file.filename)
                    file.save(os.path.join(folder_path, filename))

        # 处理删除媒体文件请求
        delete_files = request.form.getlist('delete_files')
        for filename in delete_files:
            file_path = os.path.join(folder_path, filename)
            if os.path.exists(file_path):
                os.remove(file_path)

        db.session.commit()
        flash('帖子已更新。', 'success')
        return redirect(url_for('neibr.post_detail', post_id=post.id))

    # 读取帖子文案
    folder_path = os.path.join(UPLOAD_BASE_PATH, str(current_user.id), str(post.id))
    with open(os.path.join(folder_path, 'post.txt'), 'r') as f:
        post_text = f.read()

    # 获取媒体文件列表
    media_files = [f for f in os.listdir(folder_path) if f != 'post.txt']

    return render_template('edit_post.html', post=post, post_text=post_text, media_files=media_files)