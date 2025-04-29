from . import setting_bp
from flask import app, request, send_from_directory
from Settings.models import User
from flask import Blueprint, request, render_template, redirect, url_for, flash
from flask_login import login_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
from Settings.models import User
from Settings.extensions import db
from flask_login import login_required, current_user
import os
import shutil
from werkzeug.utils import secure_filename
import json
from flask import session
import time
import re
from datetime import timedelta



@setting_bp.route('/')
@login_required
def index():
    """后台管理首页：管理员和ID为1的用户显示额外功能"""
    
    # 判断是否为管理员，是否为超级管理员
    is_admin = current_user.is_admin  # 普通管理员
    is_user1 = current_user.id == 1  # 超级管理员

    # 定义是否显示额外的内容
    extra_for_admin = is_admin  # 只有管理员能看到管理员的内容
    extra_for_user1 = is_user1  # 只有ID为1的用户能看到超级管理员的内容

    # 渲染模板，传递是否显示额外内容的标志
    return render_template(
        'setting_index.html',
                       notes_count=10,
                       posts_count=25,
                       users_count=5,
                       media_files_count=50,
        extra_for_admin=extra_for_admin,
        extra_for_user1=extra_for_user1
    )


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
        return redirect(url_for('setting.index'))

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
        return redirect(url_for('setting.index'))

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
#app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=30)

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
            remember = request.form.get('remember') == 'on'

            login_user(user, remember=remember)
            session.permanent = True

            next_page = request.args.get('next')  # 获取 next 参数
            return redirect(next_page or url_for('setting.index'))  # 如果 next 存在就重定向到 next 页面，否则跳转到后台首页
        flash('邮箱或密码错误。', 'error')
    
    return render_template('login.html')  # 确保使用的是 login.html 页面，而不是 index.html

@setting_bp.route('/logout')
@login_required
def logout():
    logout_user()  # 登出用户
    session.clear()  # 清除会话数据
    return redirect(url_for('setting.login'))
###########################################################









































BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
#BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
GALLERY_PATH = os.path.join(BASE_DIR, 'Gallery', 'galleries')
#GALLERY_PATH = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', 'Benlog', 'static', 'gallery')
# List all folders in the gallery directory
@setting_bp.route('/manage_gallery')
@login_required
def manage_gallery():
    # Get a list of all folders in the gallery directory
    folders = [f for f in os.listdir(GALLERY_PATH) if os.path.isdir(os.path.join(GALLERY_PATH, f))]
    return render_template('manage_gallery.html', folders=folders)

@setting_bp.route('/manage_gallery/create', methods=['POST'])
@login_required
def create_folder():
    # 1. 获取并清理用户输入
    folder_name = request.form.get('folder_name', '').strip()
    
    # 2. 安全校验：禁止路径穿越
    if not folder_name or '..' in folder_name or '/' in folder_name:
        flash('非法的文件夹名称', 'error')
        return redirect(url_for('setting.manage_gallery'))
    
    # 3. 创建目录
    folder_path = os.path.join(GALLERY_PATH, folder_name)
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)  # 会自动创建多层目录 Google: [Python os.makedirs](https://www.google.com/search?q=Python+os.makedirs)
        flash(f'文件夹 "{folder_name}" 创建成功', 'success')
    else:
        flash(f'文件夹 "{folder_name}" 已存在', 'warning')
    
    return redirect(url_for('setting.manage_gallery'))

@setting_bp.route('/manage_gallery/delete/<folder_name>', methods=['POST'])
@login_required
def delete_folder(folder_name):
    # 1. 安全校验同上
    if '..' in folder_name or '/' in folder_name:
        flash('非法的文件夹名称', 'error')
        return redirect(url_for('setting.manage_gallery'))

    # 2. 删除目录及其所有内容
    folder_path = os.path.join(GALLERY_PATH, folder_name)
    if os.path.isdir(folder_path):
        shutil.rmtree(folder_path)  # 递归删除目录 Google: [Python shutil.rmtree](https://www.google.com/search?q=Python+shutil.rmtree)
        flash(f'文件夹 "{folder_name}" 已删除', 'success')
    else:
        flash(f'文件夹 "{folder_name}" 不存在', 'error')
    
    return redirect(url_for('setting.manage_gallery'))





















#BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
#DYNAMIC_PAGES_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', 'Index', 'dynamic_pages')
#DYNAMIC_PAGES_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'Index', 'dynamic_pages')
# 动态页面 JSON 文件所在目录
DYNAMIC_PAGES_FOLDER = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'Index', 'dynamic_pages')
)
if not os.path.exists(DYNAMIC_PAGES_FOLDER):
    raise FileNotFoundError(f"目录 {DYNAMIC_PAGES_FOLDER} 不存在！")

DYNAMIC_PAGES_FOLDER = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'Index', 'dynamic_pages')
)
if not os.path.exists(DYNAMIC_PAGES_FOLDER):
    raise FileNotFoundError(f"目录 {DYNAMIC_PAGES_FOLDER} 不存在！")

@setting_bp.route('/manage_dynamic_page', methods=['GET'])
@login_required
def manage_dynamic_page():
    """
    列出 dynamic_pages 目录下的所有 JSON 页面，
    并生成：
      - edit_url: 跳转至 index 蓝图的编辑界面
      - view_url: 跳转至 index 蓝图的预览界面
    """
    editable_pages = []
    for filename in os.listdir(DYNAMIC_PAGES_FOLDER):
        if not filename.endswith('.json'):
            continue
        page = filename[:-5]
        path = os.path.join(DYNAMIC_PAGES_FOLDER, filename)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            continue
        editable_pages.append({
            'page_name': page,
            'edit_url': url_for('index.edit_dynamic_page', page=page),
            'view_url': url_for('index.dynamic_page',    page=page, _external=True)
        })
    return render_template('manage_dynamic_pages.html', editable_pages=editable_pages)

@setting_bp.route('/<page>/delete', methods=['POST'])
@login_required
def delete_dynamic_page(page):
    """
    删除 JSON 页面文件，仅管理员或 id==1 用户可操作
    """
    if not (current_user.is_admin or current_user.id == 1):
        abort(403)
    file_path = os.path.join(DYNAMIC_PAGES_FOLDER, f"{page}.json")
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            flash(f'页面 "{page}" 已删除！', 'success')
        except Exception as e:
            flash(f'删除失败：{e}', 'danger')
    else:
        flash('页面不存在或已被删除', 'warning')
    return redirect(url_for('setting.manage_dynamic_page'))

@setting_bp.route('/new_dynamic_page', methods=['GET', 'POST'])
@login_required
def new_dynamic_page():
    """
    创建新动态页面：
      GET  渲染文件名输入表单
      POST 使用 filename 生成初始 JSON 并跳转到编辑
    """
    if not (current_user.is_admin or current_user.id == 1):
        abort(403)

    if request.method == 'GET':
        # 仅显示一个让用户输入 filename（不包含 .json）的表单
        return render_template('new_dynamic_page.html')

    # POST：读取 filename 字段
    filename_input = request.form.get('filename', '').strip()
    if not filename_input:
        flash("文件名不能为空", 'danger')
        return redirect(url_for('setting.new_dynamic_page'))

    # 清洗为安全文件名（不含扩展名）
    safe = re.sub(r'[^0-9A-Za-z_-]', '_', filename_input)
    json_filename = f"{safe}.json"
    full_path = os.path.join(DYNAMIC_PAGES_FOLDER, json_filename)

    if os.path.exists(full_path):
        flash("该文件名已存在，请换一个", 'danger')
        return redirect(url_for('setting.new_dynamic_page'))

    # 初始 JSON 只需 filename 顶级字段，组件由编辑器中添加
    initial_data = {
        "filename": safe
    }

    try:
        os.makedirs(DYNAMIC_PAGES_FOLDER, exist_ok=True)
        with open(full_path, 'w', encoding='utf-8') as f:
            json.dump(initial_data, f, ensure_ascii=False, indent=4)
        flash(f'新建页面 "{safe}" 成功！', 'success')
    except Exception as e:
        flash(f'新建页面失败：{e}', 'danger')
        return redirect(url_for('setting.new_dynamic_page'))

    # 跳转到编辑路由，由编辑器负责后续组件添加
    return redirect(url_for('index.edit_dynamic_page', page=safe))


























# Path to the JSON file
cards_file_path = os.path.join(os.path.dirname(__file__), '..', 'Index', 'dynamic_links', 'quick-links.json')

# Load the existing quick links from the JSON file
def load_quick_links():
    if not os.path.exists(cards_file_path):
        return []  # Return an empty list if the file doesn't exist
    with open(cards_file_path, 'r', encoding='utf-8') as file:
        return json.load(file)

# Save the updated list of quick links to the JSON file
def save_quick_links(links):
    with open(cards_file_path, 'w', encoding='utf-8') as file:
        json.dump(links, file, ensure_ascii=False, indent=4)

# 显示所有快捷链接，并支持删除和添加
@setting_bp.route('/quick-links', methods=['GET', 'POST'])
def manage_quick_links():
    quick_links = load_quick_links()  # Load the quick links

    # Handle form submission for adding or deleting quick links
    if request.method == 'POST':
        action = request.form.get('action')
        index = request.form.get('index')
        url = request.form.get('url')
        label = request.form.get('label')
        icon = request.form.get('icon')

        if action == 'delete' and index is not None:  # Handle delete
            index = int(index)
            if 0 <= index < len(quick_links):
                quick_links.pop(index)  # Remove the link at the specified index
                save_quick_links(quick_links)  # Save the updated list

        elif url and label:  # Handle add
            quick_links.append({"url": url, "label": label, "icon": icon})
            save_quick_links(quick_links)  # Save the updated list

        return redirect(url_for('setting.manage_quick_links'))  # Redirect to avoid resubmission

    return render_template('manage_quick_links.html', quick_links=quick_links)
















# Path to the JSON file
links_file_path = os.path.join(os.path.dirname(__file__), '..', 'Index', 'dynamic_links', 'friend-links.json')

# Load the existing friend links from the JSON file
def load_friend_links():
    if not os.path.exists(links_file_path):
        return []  # Return an empty list if the file doesn't exist
    with open(links_file_path, 'r', encoding='utf-8') as file:
        return json.load(file)

# Save the updated list of friend links to the JSON file
def save_friend_links(links):
    with open(links_file_path, 'w', encoding='utf-8') as file:
        json.dump(links, file, ensure_ascii=False, indent=4)

# 显示所有友链，并支持删除和添加
@setting_bp.route('/friend-links', methods=['GET', 'POST'])
def manage_friend_links():
    friend_links = load_friend_links()  # Load the friend links

    # Handle form submission for adding or deleting links
    if request.method == 'POST':
        action = request.form.get('action')
        index = request.form.get('index')
        url = request.form.get('url')
        label = request.form.get('label')

        if action == 'delete' and index is not None:  # Handle delete
            index = int(index)
            if 0 <= index < len(friend_links):
                friend_links.pop(index)  # Remove the link at the specified index
                save_friend_links(friend_links)  # Save the updated list

        elif url and label:  # Handle add (adding a new link)
            friend_links.append({"url": url, "label": label})
            save_friend_links(friend_links)  # Save the updated list

        return redirect(url_for('setting.manage_friend_links'))  # Redirect to avoid resubmission

    return render_template('manage_friend_links.html', friend_links=friend_links)