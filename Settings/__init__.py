from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask import render_template, request, redirect, url_for, flash # type: ignore
from Settings.models import User 
from werkzeug.security import generate_password_hash, check_password_hash 
from Settings.extensions import db, login_manager, migrate
from flask import Blueprint

# 定义蓝图对象，名称统一用小写 setting_bp，模板目录设置为当前模块下的 templates 子目录
setting_bp = Blueprint('setting', __name__, template_folder='templates')

# 导入视图模块以注册路由；此处只做简单导入，不对 views 内部内容做其它操作，避免循环引用
from . import views

def init_app(app):
    db.init_app(app)  # 绑定 SQLAlchemy 到 Flask 应用
    login_manager.init_app(app)  # 绑定 LoginManager 到 Flask 应用
    login_manager.login_view = 'setting.login'  # 指定登录视图

    migrate.init_app(app, db)

    # 定义用户加载函数
    @login_manager.user_loader
    def load_user(user_id):
        from ..Settings.models import User
        return User.query.get(int(user_id))
    