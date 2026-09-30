"""Gallery storage.

Local files under instance/Gallery/media are the default.
Aliyun OSS is used only when STORAGE_BACKEND=oss and credentials are set.
"""

import json
import os
from typing import Optional

from flask import current_app, url_for
from werkzeug.utils import secure_filename

IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
VIDEO_EXTENSIONS = {'mp4', 'webm', 'mov'}
AUDIO_EXTENSIONS = {'mp3', 'm4a', 'ogg'}
ALLOWED_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS | AUDIO_EXTENSIONS


def _base_prefix() -> str:
    prefix = (current_app.config.get('OSS_BASE_PREFIX') or '').strip('/')
    if prefix:
        return prefix + '/'
    return ''


def _with_base(key: Optional[str]) -> str:
    base = _base_prefix()
    if key is None:
        return base
    key = key.lstrip('/')
    if base and key.startswith(base):
        return key
    return f'{base}{key}' if base else key


def _strip_base(key: Optional[str]) -> Optional[str]:
    if key is None:
        return None
    base = _base_prefix()
    if base and key.startswith(base):
        return key[len(base):]
    return key


def using_oss() -> bool:
    if (current_app.config.get('STORAGE_BACKEND') or 'local') != 'oss':
        return False
    required = (
        current_app.config.get('OSS_ACCESS_KEY_ID'),
        current_app.config.get('OSS_ACCESS_KEY_SECRET'),
        current_app.config.get('OSS_BUCKET_NAME'),
        current_app.config.get('OSS_ENDPOINT_PUBLIC') or current_app.config.get('OSS_ENDPOINT_INTERNAL'),
    )
    return all(required)


def _local_root() -> str:
    path = current_app.config.get('GALLERY_LOCAL_DIR') or os.path.join(
        current_app.instance_path, 'Gallery', 'media'
    )
    os.makedirs(path, exist_ok=True)
    return path


def _safe_key(key: str) -> str:
    key = (key or '').replace('\\', '/').lstrip('/')
    parts = [part for part in key.split('/') if part not in {'', '.', '..'}]
    return '/'.join(parts)


def _local_path(key: str) -> str:
    root = os.path.realpath(_local_root())
    relative = _safe_key(key)
    full = os.path.realpath(os.path.join(root, relative))
    if full != root and not full.startswith(root + os.sep):
        raise ValueError('路径超出图库目录')
    return full


def _get_bucket():
    import oss2

    ak = current_app.config['OSS_ACCESS_KEY_ID']
    sk = current_app.config['OSS_ACCESS_KEY_SECRET']
    bucket_name = current_app.config['OSS_BUCKET_NAME']
    if current_app.config.get('USE_OSS_INTERNAL', False):
        endpoint = current_app.config.get('OSS_ENDPOINT_INTERNAL')
    else:
        endpoint = current_app.config.get('OSS_ENDPOINT_PUBLIC')
    if not all([ak, sk, endpoint, bucket_name]):
        raise RuntimeError('OSS 配置不完整')
    if not endpoint.startswith('http'):
        endpoint = 'https://' + endpoint
    auth = oss2.Auth(ak, sk)
    return oss2.Bucket(auth, endpoint, bucket_name)


def list_albums(prefix: str = '') -> list:
    if not using_oss():
        root = _local_path(prefix)
        if not os.path.isdir(root):
            return []
        names = []
        for name in sorted(os.listdir(root)):
            if os.path.isdir(os.path.join(root, name)):
                album = _safe_key(os.path.join(prefix, name))
                names.append(album + '/')
        return names

    import oss2  # noqa: F401
    bucket = _get_bucket()
    base = _base_prefix()
    result = bucket.list_objects(prefix=_with_base(prefix), delimiter='/', max_keys=1000)
    prefixes = result.prefix_list or []
    if base:
        prefixes = [item[len(base):] for item in prefixes if item.startswith(base)]
    return prefixes


def list_objects(prefix: str = '', marker: str = None, max_keys: int = 100):
    prefix = _safe_key(prefix)
    if prefix and not prefix.endswith('/') and os.path.isdir(_local_path(prefix)) and not using_oss():
        prefix = prefix + '/'

    if not using_oss():
        root = _local_root()
        start = _local_path(prefix) if prefix else root
        if not os.path.isdir(start):
            return [], None
        keys = []
        for dirpath, _, filenames in os.walk(start):
            for filename in filenames:
                full = os.path.join(dirpath, filename)
                rel = os.path.relpath(full, root).replace('\\', '/')
                keys.append(rel)
        keys.sort()
        if marker:
            keys = [key for key in keys if key > marker]
        next_marker = keys[max_keys] if len(keys) > max_keys else None
        return keys[:max_keys], next_marker

    import oss2
    bucket = _get_bucket()
    iterator = oss2.ObjectIterator(
        bucket,
        prefix=_with_base(prefix),
        marker=_with_base(marker) if marker else None,
        max_keys=max_keys,
    )
    keys = [_strip_base(obj.key) for obj in iterator]
    next_marker = _strip_base(iterator.next_marker) if iterator.next_marker else None
    return keys, next_marker


def delete_object(key: str):
    key = _safe_key(key)
    if not key:
        raise ValueError('无效的文件名')
    if not using_oss():
        path = _local_path(key)
        if os.path.isfile(path):
            os.remove(path)
        return
    bucket = _get_bucket()
    bucket.delete_object(_with_base(key))


def generate_signed_url(key: str, expires: int = 3600, style: str = None) -> str:
    key = _safe_key(key)
    if not using_oss():
        return url_for('gallery.media', key=key)
    bucket = _get_bucket()
    params = None
    if style == 'thumb':
        params = {'x-oss-process': 'image/resize,w_300/quality,q_70/format,jpg'}
    return bucket.sign_url('GET', _with_base(key), expires, params=params)


def save_upload(prefix: str, file_storage) -> str:
    filename = secure_filename(file_storage.filename or '')
    if not filename or '.' not in filename:
        raise ValueError('文件名无效')
    ext = filename.rsplit('.', 1)[-1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f'不允许的文件类型：.{ext}')
    folder = _safe_key(prefix)
    key = f'{folder}/{filename}' if folder else filename
    if not using_oss():
        dest = _local_path(key)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        file_storage.save(dest)
        return key
    bucket = _get_bucket()
    bucket.put_object(_with_base(key), file_storage.stream)
    return key


def local_file(key: str):
    path = _local_path(key)
    if not os.path.isfile(path):
        return None
    return path


def _visible_albums_path() -> str:
    try:
        configured = current_app.config.get('VISIBLE_ALBUMS_PATH')
    except RuntimeError:
        configured = None
    if configured:
        return configured
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    return os.path.join(base_dir, 'instance', 'Settings', 'visible_albums.json')


def load_visible_albums():
    path = os.path.abspath(_visible_albums_path())
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        with open(path, 'w', encoding='utf-8') as handle:
            json.dump({}, handle, ensure_ascii=False)
    with open(path, 'r+', encoding='utf-8') as handle:
        content = handle.read().strip()
        if not content:
            handle.seek(0)
            json.dump({}, handle, ensure_ascii=False)
            handle.truncate()
            return {}
        try:
            return json.loads(content)
        except Exception:
            handle.seek(0)
            json.dump({}, handle, ensure_ascii=False)
            handle.truncate()
            return {}


def save_visible_albums(data):
    path = _visible_albums_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
