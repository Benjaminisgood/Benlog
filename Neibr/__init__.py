# Neibr/__init__.py
from flask import Blueprint
from Settings.extensions import db

neibr_bp = Blueprint('neibr', __name__, template_folder='templates')


def init_app(app):
    """Models are imported so SQLAlchemy registers the Post table."""
    from . import models  # noqa: F401
    from . import views  # noqa: F401


from . import views  # noqa: E402,F401
from . import models  # noqa: E402,F401
