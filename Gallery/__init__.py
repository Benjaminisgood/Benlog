# Gallery/__init__.py
from flask import Blueprint

gallery_bp = Blueprint('gallery', __name__, template_folder='templates',   static_folder='galleries')


from . import views
