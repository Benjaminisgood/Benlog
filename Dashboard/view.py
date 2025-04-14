import os
from flask import render_template, request, redirect, url_for, flash, abort, jsonify
from werkzeug.utils import secure_filename
from . import dashboard_bp  # 从当前包中获取 dashboard_bp

@dashboard_bp.route('/')
def index():
    """后台管理首页"""
    return render_template('dashboard_index.html')
