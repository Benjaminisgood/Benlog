from . import setting_bp
from flask import request
from Settings.models import User
from flask import Blueprint, request, render_template, redirect, url_for, flash
from flask_login import login_user
from werkzeug.security import generate_password_hash, check_password_hash
from Settings.models import User
from Settings.extensions import db
from flask_login import login_required, current_user



@setting_bp.route('/')
@login_required
def index():
    """后台管理首页：仅管理员可见，ID为1的用户显示额外功能"""
    is_admin = current_user.is_admin or current_user.id == 1
    extra_for_user1 = current_user.id == 1

    # 非管理员直接拒绝访问
    if not is_admin:
        flash("您没有权限访问后台管理页面。", "error")
        return redirect(url_for('index.home'))  # 假设主页 endpoint 是 'index'
    
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
        new_password = request.form.get('password')
        if new_password:
            user.password = generate_password_hash(new_password)
 
        if not all([email, username, password]):
            flash("所有字段均为必填", "error")
            return render_template('add_user.html')

        if User.query.filter_by(email=email).first() or User.query.filter_by(username=username).first():
            flash("用户名或邮箱已存在", "error")
            return render_template('add_user.html')

        hashed_pw = generate_password_hash(password)
        new_user = User(email=email, username=username, password=hashed_pw, is_admin=is_admin)
        db.session.add(new_user)
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
    
    return render_template('login.html')


