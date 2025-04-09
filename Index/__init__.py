# Index/__init__.py
from flask import Blueprint
import os

# Initialize the Index blueprint
index_bp = Blueprint('index', __name__, template_folder='templates')

# Import the views to register routes
from . import views
