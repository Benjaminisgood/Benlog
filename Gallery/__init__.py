# ------------------- Gallery/__init__.py -------------------
from flask import Blueprint

# 定义 Blueprint，只处理注册，不包含视图逻辑
gallery_bp = Blueprint('gallery', __name__, template_folder='templates')

# 导入视图模块，触发路由注册
from . import routes
