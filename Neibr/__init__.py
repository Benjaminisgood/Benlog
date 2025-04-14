# Neibr/__init__.py
from flask import Blueprint
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from Settings.extensions import db, login_manager, migrate

# 定义 Neibr 蓝图
neibr_bp = Blueprint('neibr', __name__, template_folder='templates')

login_manager = LoginManager()
migrate = Migrate()

# 初始化函数，绑定 db 和 login_manager 到 app
def init_app(app):
    login_manager.init_app(app)  # 绑定 LoginManager 到 Flask 应用
    login_manager.login_view = 'setting.login'  # 指定登录视图

    migrate.init_app(app, db)

    # 定义用户加载函数
    @login_manager.user_loader
    def load_user(user_id):
        from .models import User
        return User.query.get(int(user_id))
    
# 导入 views 和 models
from . import views
from . import models