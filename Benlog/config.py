"""Load Benlog settings from the environment or a .env file."""

import os
import secrets
from datetime import timedelta

from dotenv import load_dotenv


def _as_bool(value, default=False):
    if value is None or str(value).strip() == '':
        return default
    return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}


def _project_root():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def load_environment():
    """Load project-root .env without overriding real environment variables."""
    load_dotenv(os.path.join(_project_root(), '.env'), override=False)


def instance_path():
    configured = (os.environ.get('BENLOG_INSTANCE_PATH') or '').strip()
    if configured:
        return os.path.abspath(configured)
    return os.path.join(_project_root(), 'instance')


def _secret_key(path):
    configured = (os.environ.get('SECRET_KEY') or '').strip()
    if configured and configured != 'default-secret-key':
        return configured

    key_file = os.path.join(path, '.secret_key')
    if os.path.isfile(key_file):
        with open(key_file, 'r', encoding='utf-8') as handle:
            stored = handle.read().strip()
        if stored:
            return stored

    os.makedirs(path, exist_ok=True)
    generated = secrets.token_hex(32)
    with open(key_file, 'w', encoding='utf-8') as handle:
        handle.write(generated)
    try:
        os.chmod(key_file, 0o600)
    except OSError:
        pass
    return generated


def _database_uri(path):
    configured = (os.environ.get('DATABASE_URL') or '').strip()
    if configured:
        if configured.startswith('postgres://'):
            configured = 'postgresql://' + configured[len('postgres://'):]
        return configured
    return 'sqlite:///' + os.path.join(path, 'site.db')


def apply_config(app):
    load_environment()
    data_root = app.instance_path
    os.makedirs(data_root, exist_ok=True)

    debug = _as_bool(os.environ.get('FLASK_DEBUG'), default=False)
    try:
        max_mb = int(os.environ.get('MAX_CONTENT_LENGTH_MB') or 256)
    except ValueError:
        max_mb = 256
    max_mb = max(1, min(max_mb, 1024))

    app.config.update(
        SECRET_KEY=_secret_key(data_root),
        SQLALCHEMY_DATABASE_URI=_database_uri(data_root),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        DEBUG=debug,
        ALLOW_REGISTRATION=_as_bool(os.environ.get('ALLOW_REGISTRATION'), default=False),
        REMEMBER_COOKIE_DURATION=timedelta(days=30),
        REMEMBER_COOKIE_HTTPONLY=True,
        REMEMBER_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        WTF_CSRF_TIME_LIMIT=60 * 60 * 12,
        MAX_CONTENT_LENGTH=max_mb * 1024 * 1024,
        MAX_FORM_MEMORY_SIZE=64 * 1024 * 1024,
        MAX_FORM_PARTS=2000,
        STORAGE_BACKEND=(os.environ.get('STORAGE_BACKEND') or 'local').strip().lower(),
        OSS_ACCESS_KEY_ID=(os.environ.get('OSS_ACCESS_KEY_ID') or '').strip(),
        OSS_ACCESS_KEY_SECRET=(os.environ.get('OSS_ACCESS_KEY_SECRET') or '').strip(),
        OSS_BUCKET_NAME=(os.environ.get('OSS_BUCKET_NAME') or '').strip(),
        OSS_ENDPOINT_PUBLIC=(os.environ.get('OSS_ENDPOINT_PUBLIC') or os.environ.get('OSS_ENDPOINT') or '').strip(),
        OSS_ENDPOINT_INTERNAL=(os.environ.get('OSS_ENDPOINT_INTERNAL') or '').strip(),
        USE_OSS_INTERNAL=_as_bool(os.environ.get('USE_OSS_INTERNAL'), default=False),
        OSS_BASE_PREFIX=(os.environ.get('OSS_BASE_PREFIX') or '').strip(),
        OPENAI_API_KEY=(os.environ.get('OPENAI_API_KEY') or '').strip(),
        OPENAI_BASE_URL=(os.environ.get('OPENAI_BASE_URL') or 'https://api.openai.com/v1').strip().rstrip('/'),
        OPENAI_MODEL=(os.environ.get('OPENAI_MODEL') or 'gpt-4o-mini').strip(),
        BEHIND_PROXY=_as_bool(os.environ.get('BEHIND_PROXY'), default=False),
        NEIBR_COMPRESS_MAX_FILES=12,
        NEIBR_IMAGE_MAX_EDGE=2560,
        NEIBR_IMAGE_QUALITY=22,
        NEIBR_IMAGE_OPTIMIZE=False,
        BLOG_POSTS_DIR=os.path.join(data_root, 'Blog', 'posts'),
        EDU_NOTES_DIR=os.path.join(data_root, 'Edu', 'notes'),
        NEIBR_STORAGE_DIR=os.path.join(data_root, 'Neibr', 'neibr'),
        DYNAMIC_PAGES_DIR=os.path.join(data_root, 'Index', 'dynamic_pages'),
        DYNAMIC_LINKS_DIR=os.path.join(data_root, 'Index', 'dynamic_links'),
        VISIBLE_ALBUMS_PATH=os.path.join(data_root, 'Settings', 'visible_albums.json'),
        GALLERY_LOCAL_DIR=os.path.join(data_root, 'Gallery', 'media'),
    )

    for folder in (
        app.config['BLOG_POSTS_DIR'],
        app.config['EDU_NOTES_DIR'],
        app.config['NEIBR_STORAGE_DIR'],
        app.config['DYNAMIC_PAGES_DIR'],
        app.config['DYNAMIC_LINKS_DIR'],
        app.config['GALLERY_LOCAL_DIR'],
        os.path.dirname(app.config['VISIBLE_ALBUMS_PATH']),
    ):
        os.makedirs(folder, exist_ok=True)
