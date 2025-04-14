from flask import render_template
from . import setting_bp  # 从当前包中获取 setting_bp

@setting_bp.route('/')
def index():
    """后台管理首页"""
    return render_template('setting_index.html')
