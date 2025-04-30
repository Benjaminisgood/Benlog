from Settings.extensions import db
from Settings.models import User
#from slugify import slugify
#from sqlalchemy import event  # 记得导入 event

class Post(db.Model):
    """
    帖子模型，表示用户创建的帖子。
    """
    id            = db.Column(db.Integer, primary_key=True)
    user_id       = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(255), unique=True, nullable=False)
#    slug          = db.Column(db.String(140), unique=True, nullable=False)
    tags          = db.Column(db.String(255), nullable=True)
    creation_time = db.Column(db.DateTime, default=db.func.current_timestamp())
    is_hidden     = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f'<Post {self.title}>'

