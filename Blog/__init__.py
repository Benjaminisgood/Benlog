# Blog/__init__.py
from flask import Blueprint

# Initialize the Blog blueprint
blog_bp = Blueprint('blog', __name__, template_folder='templates')

# Import the views to register the routes
from . import views
