from flask import Blueprint

# 定义蓝图对象，名称统一用小写 dashboard_bp，模板目录设置为当前模块下的 templates 子目录
dashboard_bp = Blueprint('dashboard', __name__, template_folder='templates')

# 导入视图模块以注册路由；此处只做简单导入，不对 views 内部内容做其它操作，避免循环引用
from . import views
