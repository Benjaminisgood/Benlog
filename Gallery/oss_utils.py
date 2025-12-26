# Gallery/oss_utils.py
import oss2
from flask import current_app
from typing import Optional

def _base_prefix() -> str:
    """
    从配置读取基础前缀，规范化为 '' 或 'path/'（末尾带斜杠、无前导斜杠）
    """
    prefix = (current_app.config.get('OSS_BASE_PREFIX') or '').strip('/')
    if prefix:
        return prefix + '/'
    return ''

def _with_base(key: Optional[str]) -> str:
    """
    拼接基础前缀，让所有对象操作都落在指定子目录下
    """
    base = _base_prefix()
    if key is None:
        return base
    key = key.lstrip('/')
    if base and key.startswith(base):
        return key
    return f"{base}{key}" if base else key

def _strip_base(key: Optional[str]) -> Optional[str]:
    """
    去掉返回 key 中的基础前缀，便于页面显示和分页参数传递
    """
    if key is None:
        return None
    base = _base_prefix()
    if base and key.startswith(base):
        return key[len(base):]
    return key

def _get_bucket():
    ak = current_app.config['OSS_ACCESS_KEY_ID']
    sk = current_app.config['OSS_ACCESS_KEY_SECRET']
    bucket_name = current_app.config['OSS_BUCKET_NAME']

    # 根据配置动态选择 endpoint
    if current_app.config.get('USE_OSS_INTERNAL', False):
        endpoint = current_app.config['OSS_ENDPOINT_INTERNAL']
    else:
        endpoint = current_app.config['OSS_ENDPOINT_PUBLIC']

    if not all([ak, sk, endpoint, bucket_name]):
        raise RuntimeError('Missing OSS config values')

    auth = oss2.Auth(ak, sk)
    return oss2.Bucket(auth, endpoint, bucket_name)


def list_albums(prefix: str = '') -> list[str]:
    """
    列举指定前缀下的“相册”——使用 delimiter 分组得到的公共前缀列表
    """
    bucket = _get_bucket()
    base = _base_prefix()
    # 使用 list_objects 接口的 delimiter 参数模拟目录
    result = bucket.list_objects(prefix=_with_base(prefix), delimiter='/', max_keys=1000)
    # OSS SDK 在返回值中通过 prefix_list 提供公共前缀
    prefixes = result.prefix_list or []  # e.g. ['album1/', 'album2/']
    if base:
        prefixes = [p[len(base):] for p in prefixes if p.startswith(base)]
    return prefixes


def list_objects(prefix: str = '', marker: str = None, max_keys: int = 100) -> tuple[list[str], Optional[str]]:
    """
    列举指定前缀下的对象 key 列表，支持分页。
    返回 (keys, next_marker)
    """
    bucket = _get_bucket()
    iterator = oss2.ObjectIterator(
        bucket,
        prefix=_with_base(prefix),
        marker=_with_base(marker) if marker else None,
        max_keys=max_keys
    )
    keys = [_strip_base(obj.key) for obj in iterator]
    next_marker = _strip_base(iterator.next_marker) if iterator.next_marker else None
    return keys, next_marker


def delete_object(key: str):
    """
    删除指定 key 的对象。
    """
    bucket = _get_bucket()
    bucket.delete_object(_with_base(key))


def generate_signed_url(key: str, expires: int = 3600, style: str = None) -> str:
    bucket = _get_bucket()
    params = None
    if style == 'thumb':
        # 推荐的缩略图处理方式 + 模糊占位图
        params = {
            'x-oss-process': 'image/resize,w_300/quality,q_70/format,jpg/blur,r_5,s_2'
        }
    return bucket.sign_url('GET', _with_base(key), expires, params=params)


import os
import json

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
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False)
    # 修复空文件导致的JSONDecodeError
    with open(path, 'r+', encoding='utf-8') as f:
        content = f.read().strip()
        if not content:
            f.seek(0)
            json.dump({}, f, ensure_ascii=False)
            f.truncate()
            return {}
        try:
            return json.loads(content)
        except Exception:
            # 如果内容无效，重置为空对象
            f.seek(0)
            json.dump({}, f, ensure_ascii=False)
            f.truncate()
            return {}
    
    
def save_visible_albums(data):
    path = _visible_albums_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
