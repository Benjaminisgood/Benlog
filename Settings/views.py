from . import setting_bp
from flask import request, send_from_directory
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










































#BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

GALLERY_PATH = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', 'Benlog', 'static', 'gallery')
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
    return render_template('manage_folder.html', folder_name=folder_name, files=files)

# File download route
@setting_bp.route('/download/<folder_name>/<filename>')
@login_required
def download_file(folder_name, filename):
    folder_path = os.path.join(GALLERY_PATH, folder_name)
    return send_from_directory(folder_path, filename, as_attachment=True)


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

# 管理动态页面的路由
@setting_bp.route('/manage_dynamic_page', methods=['GET'])
@login_required
def manage_dynamic_page():
    """
    读取 dynamic_pages 目录中的所有 JSON 文件，并为每个页面生成编辑链接。
    """
    editable_pages = []

    # 确保目录存在并打印文件列表
    for filename in os.listdir(DYNAMIC_PAGES_FOLDER):
        if filename.endswith('.json'):
            page_name = filename.rsplit('.', 1)[0]
            page_data = None

            try:
                # 读取每个 JSON 文件，加载页面数据
                with open(os.path.join(DYNAMIC_PAGES_FOLDER, filename), 'r', encoding='utf-8') as file:
                    page_data = json.load(file)
            except Exception as e:
                continue

            if page_data:
                editable_pages.append({
                    'page_name': page_name,
                    'title': page_data.get('title', '无标题'),
                    'edit_url': url_for('setting.edit_dynamic_page', page=page_name),  
                    'view_url': url_for('index.dynamic_page',        page=page_name,  _external=True)
                })

    if not editable_pages:
        print("没有可编辑的页面。")

    return render_template('manage_dynamic_pages.html', editable_pages=editable_pages)

if not os.path.exists(DYNAMIC_PAGES_FOLDER):
    os.makedirs(DYNAMIC_PAGES_FOLDER)


@setting_bp.route('/<page>/delete', methods=['POST'])
@login_required
def delete_dynamic_page(page):
    # 仅管理员或 user.id==1 可以删除
    if not (current_user.is_admin or current_user.id == 1):
        abort(403)

    file_path = os.path.join(DYNAMIC_PAGES_FOLDER, f"{page}.json")
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            flash(f'页面 “{page}” 已删除！', 'success')
        except Exception as e:
            flash(f'删除失败：{e}', 'danger')
    else:
        flash('页面不存在或已被删除', 'warning')

    return redirect(url_for('setting.manage_dynamic_page'))



@setting_bp.route('/<page>/edit', methods=['GET', 'POST'])
@login_required
def edit_dynamic_page(page):
    # 权限检查：仅管理员或 user.id==1 可编辑
    if not (current_user.is_admin or current_user.id == 1):
        abort(403)

    json_path = os.path.join(DYNAMIC_PAGES_FOLDER, f"{page}.json")
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            page_data = json.load(f)
    except FileNotFoundError:
        abort(404, description="dynamic页面不存在")
    except json.JSONDecodeError:
        abort(500, description="页面数据错误")

    if request.method == 'POST':
        # 更新 title 和 content
        title   = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()

        # 如果用户改了文件名，就重命名 JSON
        if title and title != page:
            # 简单文件名清洗：只保留字母数字下划线和中划线
            safe = re.sub(r'[^0-9A-Za-z_-]', '_', title)
            old_path = json_path
            new_path = os.path.join(DYNAMIC_PAGES_FOLDER, f"{safe}.json")
            if os.path.exists(new_path):
                flash("目标文件名已存在，请换一个", "danger")
                return redirect(url_for('setting.edit_dynamic_page', page=page))
            os.rename(old_path, new_path)
            page = safe
            json_path = new_path

        # 重组 page_data
        page_data['title']   = title
        page_data['content'] = content

        new_components = [
            {'type': 'title',   'content': title},
            {'type': 'content', 'content': content}
        ]
        count = int(request.form.get('elements_count', 0))
        for idx in range(count):
            ctype = request.form.get(f'elements-{idx}-type')
            raw   = request.form.get(f'elements-{idx}-content', '').strip()
            if not ctype:
                continue
            if ctype == 'text':
                new_components.append({'type': 'text', 'content': raw})
            elif ctype == 'image':
                src = request.form.get(f'elements-{idx}-src', '').strip()
                new_components.append({
                    'type': 'image', 'src': src,
                    'alt': page_data.get('alt', '')
                })
            elif ctype == 'link':
                new_components.append({
                    'type': 'link', 'href': raw, 'text': raw
                })
            elif ctype == 'quote':
                new_components.append({'type': 'quote', 'content': raw})
            elif ctype == 'code':
                new_components.append({'type': 'code', 'content': raw})
        page_data['components'] = new_components

        # 保存回 JSON
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(page_data, f, ensure_ascii=False, indent=4)

        flash(f"页面 “{title}” 更新成功！", 'success')
        return redirect(url_for('index.dynamic_page', page=page))

    # GET 时渲染编辑表单
    return render_template('edit_dynamic_page.html',
                           page=page, page_data=page_data)


@setting_bp.route('/new_dynamic_page', methods=['GET', 'POST'])
@login_required
def new_dynamic_page():
    # 权限检查
    if not (current_user.is_admin or current_user.id == 1):
        abort(403)

    if request.method == 'GET':
        # 显示让用户输入“文件名”的表单
        return render_template('new_dynamic_page.html')

    # POST：从表单读取 title 并创建 JSON
    title = request.form.get('title', '').strip()
    if not title:
        flash("文件名不能为空", 'danger')
        return redirect(url_for('setting.new_dynamic_page'))

    # 简单清洗，保证文件系统安全
    safe = re.sub(r'[^0-9A-Za-z_-]', '_', title)
    filename = f"{safe}.json"
    fullpath = os.path.join(DYNAMIC_PAGES_FOLDER, filename)

    if os.path.exists(fullpath):
        flash("该文件名已存在，请换一个", 'danger')
        return redirect(url_for('setting.new_dynamic_page'))

    # 构造初始内容
    new_page_data = {
        'title':   title,
        'content': '这里输入页面主内容…',
        'components': []
    }

    # 确保目录存在
    os.makedirs(DYNAMIC_PAGES_FOLDER, exist_ok=True)

    try:
        with open(fullpath, 'w', encoding='utf-8') as f:
            json.dump(new_page_data, f, ensure_ascii=False, indent=4)
        flash(f'新建页面 “{title}” 成功！', 'success')
    except Exception as e:
        flash(f'新建页面失败：{e}', 'danger')
        return redirect(url_for('setting.new_dynamic_page'))

    # 创建完毕后，跳转到编辑该页面，以便添加组件
    return redirect(url_for('setting.edit_dynamic_page', page=safe))



























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