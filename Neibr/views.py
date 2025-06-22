# Neibr/views.py
from flask import render_template, request, redirect, url_for, flash # type: ignore
from . import neibr_bp, db  # 从 Neibr/__init__.py 导入蓝图和本地数据库实例
from flask_login import login_required, current_user, login_user  # type: ignore # Flask-Login 用于用户会话管理
from .models import User, Post  # 从本地 models.py 导入 User 和 Post 模型
from werkzeug.security import generate_password_hash, check_password_hash  # type: ignore # 用于密码加密和验证
import os
import io
from PIL import Image
from werkzeug.utils import secure_filename # type: ignore
import yaml
from datetime import datetime
from flask import send_from_directory, abort # type: ignore
from flask import session
from flask import jsonify, request
from math import ceil

# 项目根目录下的 static/neibr 路径
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
UPLOAD_BASE_PATH = os.path.join(BASE_DIR, 'Neibr', 'neibr')
IMAGE_QUALITY = 22

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'webm', 'mp3', 'wav', 'nef','mov','MOV'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def compress_and_save_image(file_storage, save_path):
    """
    使用 Pillow 压缩并保存图片到磁盘
    - file_storage: Flask 的 FileStorage 对象
    - save_path: 最终保存路径
    """
    img = Image.open(file_storage.stream)
    # 如果有透明通道或调色板模式，先转为 RGB
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    # 将压缩后的二进制写入内存
    img_io = io.BytesIO()
    img.save(
        img_io,
        format='JPEG',        # 统一保存为 JPEG
        quality=IMAGE_QUALITY,
        optimize=True
    )
    img_io.seek(0)
    # 写入磁盘
    with open(save_path, 'wb') as out_f:
        out_f.write(img_io.read())
        
@neibr_bp.route('/')
def index():
    """
    Neibr 模块的主页，展示最新的 10 个帖子和随机选择的 10 个帖子。
    返回值：渲染 neibr_index.html 模板，传入帖子数据。
    """
    if not current_user.is_authenticated:
        flash('请先登录以查看内容。', 'login')
        return redirect(url_for('setting.login'))

    latest_posts = Post.query.filter(
       (Post.is_hidden == False) | (Post.user_id == current_user.id)
    ). order_by(Post.creation_time.desc()).limit(10).all()

    random_posts = Post.query.filter(
       (Post.is_hidden == False) | (Post.user_id == current_user.id)
    ). order_by(db.func.random()).limit(10).all()

    my_posts = Post.query.filter_by(user_id=current_user.id).order_by(Post.creation_time.desc()).limit(10).all()

    all_posts = latest_posts + random_posts + my_posts
    session['neibr_seq_latest'] = [p.id for p in latest_posts]
    session['neibr_seq_random'] = [p.id for p in random_posts]
    session['neibr_seq_my']     = [p.id for p in my_posts]
 
    user_ids = {p.user_id for p in all_posts}
    users = User.query.filter(User.id.in_(user_ids)).all()
    user_map = {u.id: u.username for u in users}

    return render_template('neibr_index.html', latest_posts=latest_posts, random_posts=random_posts, my_posts=my_posts, user_map=user_map)

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
                ext = filename.rsplit('.', 1)[1].lower()
                file_path = os.path.join(folder_path, filename)

                if ext in {'png', 'jpg', 'jpeg', 'gif'}:
                    compress_and_save_image(file, file_path)
                else:
                    file.save(file_path)

        # 保存帖子文案到 post.txt
        with open(os.path.join(folder_path, 'post.txt'), 'w') as f:
            f.write(post_text)

        db.session.commit()
        flash('帖子创建成功。', 'create_post')
        return redirect(url_for('neibr.post_detail', title=post.title))
    
    return render_template('create_post.html', title='创建帖子')

@neibr_bp.route('/post/<string:title>', methods=['GET', 'POST'])
@login_required
def post_detail(title):
    """
    显示特定帖子的详情，包括文案、多媒体文件、导航链接和评论。
    参数：
        post_id - 帖子 ID。
    返回值：
        渲染 post_detail.html 模板，传入帖子数据。
    """
    post = Post.query.filter_by(title=title).first_or_404()
    user_id = post.user_id
    author = User.query.get(user_id).username

    # 构建帖子文件夹路径：static/neibr/user_id/post_id
    folder_path = os.path.join(UPLOAD_BASE_PATH, str(user_id), str(post.id))

    # 读取帖子文案
    with open(os.path.join(folder_path, 'post.txt'), 'r') as f:
        post_text = f.read()

    # 获取媒体文件列表，排除 post.txt 和 comments.yaml
    media_files = [f for f in os.listdir(folder_path) if f not in ['post.txt', 'comments.yaml']]

    # 获取所有帖子以支持上下导航
    all_posts = Post.query.order_by(Post.creation_time.desc()).all()

    current_index = all_posts.index(post)

    # 动态上一条/下一条：根据用户来自哪个列表(src)和索引(idx)
    src = request.args.get('src', 'latest')   # 'latest', 'random', 'my'
    try:
        idx = int(request.args.get('idx', 0))
    except ValueError:
        idx = 0

    seq = session.get(f'neibr_seq_{src}', [])  # 可能是长度为 10 的列表，或更多

    previous_post = None
    next_post     = None
    # 只有当 idx 落在 [0, len(seq)-1] 范围内时，才尝试访问 seq
    if seq and 0 <= idx < len(seq):
        if idx > 0:
            previous_id = seq[idx - 1]
            previous_post = Post.query.get(previous_id)
        if idx < len(seq) - 1:
            next_id = seq[idx + 1]
            next_post = Post.query.get(next_id)
            
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
        return redirect(url_for('neibr.post_detail', title=post.title))

    return render_template(
        'post_detail.html',
        post=post,
        author=author,
        post_text=post_text,
        media_files=media_files,
        comments=comments,
        previous_post=previous_post,
        next_post=next_post,
        src=src,
        idx=idx
    )


@neibr_bp.route('/edit_post/<string:title>', methods=['GET', 'POST'])
@login_required
def edit_post(title):
    post = Post.query.filter_by(title=title).first_or_404()

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
                    ext = filename.rsplit('.', 1)[1].lower()
                    file_path = os.path.join(folder_path, filename)

                    if ext in {'png', 'jpg', 'jpeg', 'gif'}:
                        compress_and_save_image(file, file_path)
                    else:
                        file.save(file_path)

        # 处理删除媒体文件请求
        delete_files = request.form.getlist('delete_files')
        for filename in delete_files:
            file_path = os.path.join(folder_path, filename)
            if os.path.exists(file_path):
                os.remove(file_path)

        db.session.commit()
        flash('帖子已更新。', 'success')
        return redirect(url_for('neibr.post_detail', title=post.title))

    # 读取帖子文案
    folder_path = os.path.join(UPLOAD_BASE_PATH, str(current_user.id), str(post.id))
    with open(os.path.join(folder_path, 'post.txt'), 'r') as f:
        post_text = f.read()

    # 获取媒体文件列表
    media_files = [f for f in os.listdir(folder_path) if f != 'post.txt']

    return render_template('edit_post.html', post=post, post_text=post_text, media_files=media_files)



@neibr_bp.route('/media/<user_id>/<post_id>/<path:filename>')
def media_file(user_id, post_id, filename):
    # 1) 校验后缀
    if not allowed_file(filename):
        abort(403)  # Forbidden，不在白名单里的类型一律拒绝

    # 2) 计算真实路径
    base = os.path.join(BASE_DIR, 'Neibr', 'neibr')
    folder = os.path.join(base, user_id, post_id)
    full_path = os.path.join(folder, filename)

    # 3) 文件存在性检查
    if not os.path.isfile(full_path):
        abort(404)

    # 4) 安全地发送文件
    return send_from_directory(folder, filename)




@neibr_bp.route('/api/posts')
@login_required
def api_posts():
    src  = request.args.get('src', 'latest')
    page = int(request.args.get('page', 1))
    per_page = 10

    # 基础查询：公开或本人的帖子
    base_q = Post.query.filter(
      (Post.is_hidden == False) | (Post.user_id == current_user.id)
    )

    if src == 'latest':
        q = base_q.order_by(Post.creation_time.desc())
    elif src == 'random':
        q = base_q.order_by(db.func.random())
    elif src == 'my':
        q = base_q.filter_by(user_id=current_user.id) \
                  .order_by(Post.creation_time.desc())
    else:
        q = base_q.order_by(Post.creation_time.desc())

    total = q.count()
    posts = q.offset((page-1)*per_page).limit(per_page).all()

    items = []
    for p in posts:
        detail_url = url_for('neibr.post_detail',
                             title=p.title,
                             src=src,
                             idx=(page-1)*per_page + posts.index(p))
        if src == 'my':
            edit_url = url_for('neibr.edit_post', title=p.title)
        else:
            edit_url = None

        items.append({
            'title': p.title,
            'author': User.query.get(p.user_id).username,
            'date': p.creation_time.strftime('%Y-%m-%d %H:%M'),
            'tags': [t.strip() for t in p.tags.split(',')],
            'url': detail_url,
            'edit_url': edit_url
        })

    return jsonify({
        'posts': items,
        'has_more': page * per_page < total
    })