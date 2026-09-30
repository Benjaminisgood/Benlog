"""Small helpers shared by the blueprints."""

import os
import re
from functools import wraps

from flask import abort, request
from flask_login import current_user, login_required
from werkzeug.security import generate_password_hash

MIN_PASSWORD_LENGTH = 8
_SLUG_BAD = re.compile(r'[/\\\x00]')


def hash_password(password):
    return generate_password_hash(password)


def password_is_acceptable(password, username=''):
    if not password or len(password) < MIN_PASSWORD_LENGTH:
        return False
    if username and password == username:
        return False
    return True


def safe_next_url(target):
    if not target:
        return None
    target = target.strip()
    if not target.startswith('/') or target.startswith('//') or '\\' in target:
        return None
    return target


def safe_slug(slug):
    """Return a filename stem that cannot escape its directory, or None."""
    if slug is None:
        return None
    slug = str(slug).strip()
    if not slug or slug in {'.', '..'} or '..' in slug or _SLUG_BAD.search(slug):
        return None
    if len(slug) > 120:
        return None
    return slug


def clean_slug(raw):
    raw = (raw or '').strip().replace(' ', '-')
    raw = re.sub(r'[^\w.-]+', '_', raw, flags=re.UNICODE)
    raw = raw.strip('._')
    if '..' in raw:
        raw = raw.replace('..', '_')
    return safe_slug(raw[:80])


def contained_path(root, *parts):
    """Join parts under root and reject paths that climb out."""
    root_real = os.path.realpath(root)
    candidate = os.path.realpath(os.path.join(root_real, *parts))
    if candidate != root_real and not candidate.startswith(root_real + os.sep):
        return None
    return candidate


def editor_required(view):
    """Blog and notes are edited by admins. User id 1 stays the super admin."""

    @login_required
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not (getattr(current_user, 'is_admin', False) or current_user.id == 1):
            abort(403)
        return view(*args, **kwargs)

    return wrapped


def wants_json():
    return request.accept_mimetypes.best == 'application/json' or request.is_json
