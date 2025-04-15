from . import setting_bp
from flask import request
from Settings.models import User
from flask import Blueprint, request, render_template, redirect, url_for, flash
from flask_login import login_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
from Settings.models import User
from Settings.extensions import db
from flask_login import login_required, current_user
import os
from werkzeug.utils import secure_filename
import json
from flask import session


@setting_bp.route('/')
@login_required
def index():
    """后台管理首页：仅管理员可见，ID为1的用户显示额外功能"""
    is_admin = current_user.is_admin or current_user.id == 1
    extra_for_user1 = current_user.id == 1

    # 非管理员直接拒绝访问
    if not is_admin:
        flash("您没有权限访问后台管理页面。", "error")
        return redirect(url_for('setting.logout'))
    
    # 管理员访问正常渲染
    extra_for_user1 = False
    if current_user.id == 1:
        # 预留给 ID 为 1 的用户的特殊功能区域
        extra_for_user1 = True

    return render_template('setting_index.html', extra_for_user1=extra_for_user1)


@setting_bp.route('/manage_users')
@login_required
def manage_users():
    """仅限超级管理员（ID=1）访问的用户管理页面"""
    if current_user.id != 1:
        flash("您无权限访问用户管理页面。", "error")
        return redirect(url_for('setting.index'))

    users = User.query.all()
    return render_template('manage_users.html', users=users)

@setting_bp.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    """编辑指定用户信息（仅限超级管理员）"""
    if current_user.id != 1:
        flash("您无权限访问此页面。", "error")
        return redirect(url_for('setting.manage_users'))

    user = User.query.get_or_404(user_id)

    if request.method == 'POST':
        user.username = request.form.get('username')
        user.email = request.form.get('email')
        user.is_admin = True if request.form.get('is_admin') == 'on' else False
        db.session.commit()
        flash("用户信息已更新！", "success")
        return redirect(url_for('setting.manage_users'))

    return render_template('edit_user.html', user=user)


@setting_bp.route('/add_user', methods=['GET', 'POST'])
@login_required
def add_user():
    """新增用户，仅超级管理员"""
    if current_user.id != 1:
        flash("无权限访问", "error")
        return redirect(url_for('setting.manage_users'))

    if request.method == 'POST':
        email = request.form.get('email')
        username = request.form.get('username')
        password = request.form.get('password')
        is_admin = request.form.get('is_admin') == 'on'

        # 校验字段是否完整
        if not all([email, username, password]):
            flash("所有字段均为必填", "error")
            return render_template('add_user.html')

        # 校验用户名和邮箱是否已存在
        if User.query.filter_by(email=email).first() or User.query.filter_by(username=username).first():
            flash("用户名或邮箱已存在", "error")
            return render_template('add_user.html')

        # 创建 User 对象
        user = User(email=email, username=username, is_admin=is_admin)

        # 对密码进行哈希化
        if password:
            user.password = generate_password_hash(password, method='pbkdf2:sha256')

        # 将用户对象添加到数据库
        db.session.add(user)
        db.session.commit()

        flash("用户已创建", "success")
        return redirect(url_for('setting.manage_users'))

    return render_template('add_user.html')

@setting_bp.route('/delete_user/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    """删除用户，仅超级管理员"""
    if current_user.id != 1:
        flash("无权限", "error")
        return redirect(url_for('setting.index'))

    user = User.query.get_or_404(user_id)

    if user.id == 1:
        flash("禁止删除超级管理员", "error")
        return redirect(url_for('setting.manage_users'))

    db.session.delete(user)
    db.session.commit()
    flash(f"已删除用户 {user.username}", "success")
    return redirect(url_for('setting.manage_users'))

















































#########################################################################################
@setting_bp.route('/register', methods=['GET', 'POST'])
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
        return redirect(url_for('setting.login'))
    
    return render_template('register.html')
@setting_bp.route('/login', methods=['GET', 'POST'])
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
            return redirect(url_for('index.home'))
        flash('邮箱或密码错误。', 'error')
    
    return render_template('setting_index.html')

@setting_bp.route('/logout')
@login_required
def logout():
    logout_user()  # 登出用户
    session.clear()  # 清除会话数据
    return redirect(url_for('setting.login'))
###########################################################










































#BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

GALLERY_PATH = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', 'Benlog', 'static', 'gallery')
# List all folders in the gallery directory
@setting_bp.route('/manage_gallery')
@login_required
def manage_gallery():
    # Get a list of all folders in the gallery directory
    folders = [f for f in os.listdir(GALLERY_PATH) if os.path.isdir(os.path.join(GALLERY_PATH, f))]
    return render_template('manage_gallery.html', folders=folders)

# List files in a folder and allow operations
@setting_bp.route('/gallery/<folder_name>')
@login_required
def view_folder(folder_name):
    folder_path = os.path.join(GALLERY_PATH, folder_name)
    # List all files in the folder
    if os.path.exists(folder_path):
        files = [f for f in os.listdir(folder_path) if not f.startswith('.')]
    else:
        files = []
    return render_template('view_folder.html', folder_name=folder_name, files=files)

# File download route
@setting_bp.route('/download/<folder_name>/<filename>')
@login_required
def download_file(folder_name, filename):
    folder_path = os.path.join(GALLERY_PATH, folder_name)
    return send_from_directory(folder_path, filename)

# File deletion route
@setting_bp.route('/delete_file/<folder_name>/<filename>', methods=['POST'])
@login_required
def delete_file(folder_name, filename):
    file_path = os.path.join(GALLERY_PATH, folder_name, filename)
    if os.path.exists(file_path):
        os.remove(file_path)
    return redirect(url_for('setting.view_folder', folder_name=folder_name))

@setting_bp.route('/upload/<folder_name>', methods=['POST'])
@login_required
def upload_file(folder_name):
    folder_path = os.path.join(GALLERY_PATH, folder_name)
    
    # Ensure the folder exists
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    # Handle single file upload (standard form or Dropzone)
    file = request.files.get('file')  # Dropzone sends files with the "file" name
    if file:
        filename = secure_filename(file.filename)
        file.save(os.path.join(folder_path, filename))

    return redirect(url_for('setting.view_folder', folder_name=folder_name))


@setting_bp.route('/rename_file', methods=['POST'])
@login_required
def rename_file():
    folder_name = request.form['folder-name']
    old_filename = request.form['old-filename']
    new_filename = request.form['new-filename']
    
    folder_path = os.path.join(GALLERY_PATH, folder_name)
    old_file_path = os.path.join(folder_path, old_filename)
    new_file_path = os.path.join(folder_path, new_filename)

    # Ensure the new filename is secure
    new_filename = secure_filename(new_filename)

    if os.path.exists(old_file_path):
        os.rename(old_file_path, new_file_path)  # Rename the file
        flash('File renamed successfully!', 'success')
    else:
        flash('File does not exist!', 'danger')
    
    return redirect(url_for('setting.view_folder', folder_name=folder_name))



















#BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
#DYNAMIC_PAGES_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', 'Index', 'dynamic_pages')
#DYNAMIC_PAGES_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'Index', 'dynamic_pages')
DYNAMIC_PAGES_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', 'Index', 'dynamic_pages')
DYNAMIC_PAGES_FOLDER = os.path.abspath(DYNAMIC_PAGES_FOLDER)
if not os.path.exists(DYNAMIC_PAGES_FOLDER):
    raise FileNotFoundError(f"目录 {DYNAMIC_PAGES_FOLDER} 不存在！")

#print(DYNAMIC_PAGES_FOLDER)
#DYNAMIC_PAGES_FOLDER = 'Index/dynamic_pages'
# 管理动态页面的路由
@setting_bp.route('/manage_dynamic_page', methods=['GET'])
@login_required
def manage_dynamic_page():
    """
    读取 dynamic_pages 目录中的所有 JSON 文件，并为每个页面生成编辑链接。
    """
    editable_pages = []

    # 确保目录存在并打印文件列表
    print(f"读取目录: {DYNAMIC_PAGES_FOLDER}")
    for filename in os.listdir(DYNAMIC_PAGES_FOLDER):
        print(f"检查文件: {filename}")
        if filename.endswith('.json'):
            page_name = filename.rsplit('.', 1)[0]
            page_data = None

            try:
                # 读取每个 JSON 文件，加载页面数据
                with open(os.path.join(DYNAMIC_PAGES_FOLDER, filename), 'r', encoding='utf-8') as file:
                    page_data = json.load(file)
                print(f"成功加载页面: {page_name}")
            except Exception as e:
                print(f"读取 {filename} 时出错: {e}")
                continue

            if page_data:
                editable_pages.append({
                    'page_name': page_name,
                    'title': page_data.get('title', '无标题'),
                    'edit_url': url_for('index.edit_dynamic_page', page=page_name)  # 生成编辑页面的链接
                })

    if not editable_pages:
        print("没有可编辑的页面。")

    return render_template('manage_dynamic_pages.html', editable_pages=editable_pages)

if not os.path.exists(DYNAMIC_PAGES_FOLDER):
    os.makedirs(DYNAMIC_PAGES_FOLDER)

@setting_bp.route('/new_dynamic_page', methods=['GET', 'POST'])
@login_required
def new_dynamic_page():
    """
    创建新的动态网页，并保存为新的 JSON 文件
    """
    if request.method == 'POST':
        page_title = request.form['title']
        page_content = request.form['content']
        elements = []

        # 获取页面元素
        for i in range(int(request.form['elements_count'])):
            element_type = request.form.get(f'element_{i}_type')
            element_content = request.form.get(f'element_{i}_content')

            if element_type == 'text':
                elements.append({'type': 'text', 'content': element_content})
            elif element_type == 'image':
                elements.append({'type': 'image', 'src': element_content})
            elif element_type == 'link':
                elements.append({'type': 'link', 'href': element_content, 'text': element_content})

        # 新建页面的数据
        new_page_data = {
            'title': page_title,
            'content': page_content,
            'elements': elements
        }

        # 保存为 JSON 文件
        new_page_filename = os.path.join(DYNAMIC_PAGES_FOLDER, f'{page_title}.json')
        with open(new_page_filename, 'w', encoding='utf-8') as file:
            json.dump(new_page_data, file, ensure_ascii=False, indent=4)

        flash(f'新建页面 "{page_title}" 成功！', 'success')
        return redirect(url_for('setting.manage_dynamic_page'))  # 重定向回页面列表

    return render_template('new_dynamic_page.html')  # 显示创建页面的表单