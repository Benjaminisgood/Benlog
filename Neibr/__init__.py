# Neibr/__init__.py
from flask import Blueprint
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate

# 定义 Neibr 蓝图
neibr_bp = Blueprint('neibr', __name__, template_folder='templates')

# 定义数据库和登录管理器（仅限 Neibr 模块使用）
db = SQLAlchemy()
login_manager = LoginManager()

migrate = Migrate()



# 初始化函数，绑定 db 和 login_manager 到 app
def init_app(app):
    db.init_app(app)  # 绑定 SQLAlchemy 到 Flask 应用
    login_manager.init_app(app)  # 绑定 LoginManager 到 Flask 应用
    login_manager.login_view = 'neibr.login'  # 指定登录视图

    migrate.init_app(app, db)

    
    # 定义用户加载函数
    @login_manager.user_loader
    def load_user(user_id):
        from .models import User
        return User.query.get(int(user_id))
    
    # 不再在应用启动时自动创建数据库表
    # 推荐使用 Flask-Migrate 管理数据库迁移：
    # 1. 使用 "flask db init" 初始化迁移目录；
    # 2. 使用 "flask db migrate -m 'Initial migration'" 生成迁移脚本；
    # 3. 使用 "flask db upgrade" 应用迁移更新。
    # with app.app_context():
    #     db.create_all()  # 已注释：使用迁移工具管理数据库更新

# 导入 views 和 models
from . import views
from . import models