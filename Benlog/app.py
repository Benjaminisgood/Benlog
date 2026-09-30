import logging
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import click
from flask import Flask, flash, redirect, request, url_for
from flask_wtf.csrf import CSRFProtect, generate_csrf
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.middleware.proxy_fix import ProxyFix

from Benlog.config import apply_config, instance_path
from Benlog.render import safe_href
from Benlog.security import hash_password, password_is_acceptable

csrf = CSRFProtect()
_FORM_OPEN = re.compile(
    r'<form\b[^>]*\bmethod\s*=\s*["\']post["\'][^>]*>',
    re.IGNORECASE,
)


def create_app():
    app = Flask(
        __name__,
        instance_path=instance_path(),
        instance_relative_config=True,
        template_folder=os.path.join(os.path.dirname(__file__), 'templates'),
        static_folder=os.path.join(os.path.dirname(__file__), 'static'),
    )
    apply_config(app)
    csrf.init_app(app)

    if app.config.get('BEHIND_PROXY'):
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    from Blog import blog_bp
    from Edu import edu_bp
    from Gallery import gallery_bp
    from Index import index_bp
    from Neibr import neibr_bp
    from Neibr import init_app as neibr_init_app
    from Settings import init_app as settings_init_app
    from Settings import setting_bp

    app.register_blueprint(index_bp)
    app.register_blueprint(blog_bp, url_prefix='/blog')
    app.register_blueprint(edu_bp, url_prefix='/edu')
    app.register_blueprint(neibr_bp, url_prefix='/neibr')
    app.register_blueprint(setting_bp, url_prefix='/setting')
    app.register_blueprint(gallery_bp, url_prefix='/gallery')

    settings_init_app(app)
    neibr_init_app(app)

    from Settings.extensions import db
    from Settings.models import User
    import Neibr.models  # noqa: F401  (registers Post)

    with app.app_context():
        db.create_all()
        _bootstrap_admin(app, db, User)

    @app.context_processor
    def inject_globals():
        needs_setup = False
        try:
            needs_setup = db.session.query(User.id).first() is None
        except Exception:
            app.logger.exception('无法检查是否需要初始化管理员')
        return {
            'allow_registration': app.config.get('ALLOW_REGISTRATION', False),
            'needs_setup': needs_setup,
        }

    @app.template_filter('safe_href')
    def safe_href_filter(url):
        return safe_href(url)

    @app.after_request
    def inject_csrf_field(response):
        content_type = response.content_type or ''
        if response.direct_passthrough or not content_type.startswith('text/html'):
            return response
        html = response.get_data(as_text=True)
        if '<form' not in html.lower():
            return response
        token = generate_csrf()
        field = f'<input type="hidden" name="csrf_token" value="{token}">'
        updated = _FORM_OPEN.sub(lambda match: match.group(0) + field, html)
        if updated != html:
            response.set_data(updated)
        return response

    @app.errorhandler(RequestEntityTooLarge)
    def handle_request_too_large(_error):
        flash('提交内容过大，请分批上传或缩小内容后重试。', 'error')
        return redirect(request.referrer or url_for('index.home'))

    @app.cli.command('create-admin')
    def create_admin_command():
        """创建管理员。优先读取 ADMIN_EMAIL / ADMIN_USERNAME / ADMIN_PASSWORD。"""
        email = (os.environ.get('ADMIN_EMAIL') or '').strip() or click.prompt('管理员邮箱')
        username = (os.environ.get('ADMIN_USERNAME') or '').strip() or click.prompt('用户名')
        password = os.environ.get('ADMIN_PASSWORD') or click.prompt(
            '密码', hide_input=True, confirmation_prompt=True
        )
        with app.app_context():
            message = _create_admin(db, User, email, username, password, allow_existing=False)
        click.echo(message)

    log_level = logging.DEBUG if app.debug else logging.INFO
    app.logger.setLevel(log_level)
    logging.basicConfig(level=log_level)
    return app


def _create_admin(db, user_model, email, username, password, allow_existing=True):
    email = (email or '').strip()
    username = (username or '').strip()
    if not email or not username or not password:
        return '未创建管理员：邮箱、用户名和密码都要提供。'
    if not password_is_acceptable(password, username):
        return f'未创建管理员：密码至少 8 位，且不能与用户名相同。'
    existing = user_model.query.filter(
        (user_model.email == email) | (user_model.username == username)
    ).first()
    if existing:
        if allow_existing:
            return '已有用户，跳过自动创建管理员。'
        return '未创建管理员：邮箱或用户名已存在。'
    if user_model.query.first() and allow_existing:
        return '已有用户，跳过自动创建管理员。'
    user = user_model(
        email=email,
        username=username,
        password=hash_password(password),
        is_admin=True,
    )
    db.session.add(user)
    db.session.commit()
    return f'已创建管理员 {username}（{email}）。请用这个账号登录。'


def _bootstrap_admin(app, db, user_model):
    email = (os.environ.get('ADMIN_EMAIL') or '').strip()
    username = (os.environ.get('ADMIN_USERNAME') or '').strip()
    password = os.environ.get('ADMIN_PASSWORD') or ''
    if not (email and username and password):
        return
    if user_model.query.first():
        return
    message = _create_admin(db, user_model, email, username, password)
    app.logger.info(message)


def main():
    app = create_app()
    host = os.environ.get('HOST') or '127.0.0.1'
    port = int(os.environ.get('PORT') or 5000)
    app.run(host=host, port=port, debug=app.config.get('DEBUG', False))


if __name__ == '__main__':
    main()
