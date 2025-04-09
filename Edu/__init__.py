# Edu/__init__.py
from flask import Blueprint

# Initialize the Edu blueprint
edu_bp = Blueprint('edu', __name__, template_folder='templates')

# Import views to register routes
from . import views
