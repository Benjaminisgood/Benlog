# Neibr/models.py
from . import db  # 从 Neibr/__init__.py 导入本地 db
from flask_login import UserMixin  # 导入 UserMixin 以支持 Flask-Login

class User(db.Model, UserMixin):
    """
    用户模型，表示系统中注册的用户。
    继承 UserMixin 以提供 Flask-Login 所需的属性和方法。
    """
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    username = db.Column(db.String(60), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)

    def __repr__(self):
        return f'<User {self.username}>'

class Post(db.Model):
    """
    帖子模型，表示用户创建的帖子。
    """
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    tags = db.Column(db.String(255), nullable=True)
    creation_time = db.Column(db.DateTime, default=db.func.current_timestamp())
    is_hidden = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f'<Post {self.title}>'